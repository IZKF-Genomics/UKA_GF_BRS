#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


POLL_INTERVAL_SECONDS = 2
FINAL_MESSAGE_TIMEOUT_SECONDS = 3600


def load_ctx() -> dict:
    """Load BPM ctx JSON if provided."""
    ctx_path = os.environ.get("BPM_CTX_PATH")
    if not ctx_path or not Path(ctx_path).is_file():
        return {}
    with open(ctx_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _split_csv(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(value)]


def _derive_username(project_name: str) -> str:
    parts = project_name.split("_")
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return project_name or "user"


def _parse_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _split_hostpath(raw: str, default_host: str) -> tuple[str, str]:
    """
    Split host:/abs/path into (host, /abs/path); fall back to default_host.
    """
    if ":" in raw:
        host, rest = raw.split(":", 1)
        if host and rest.startswith("/"):
            return host, rest
    return default_host, raw


def _load_meta(run_dir: Path) -> dict:
    meta_path = run_dir / "bpm.meta.yaml"
    if not meta_path.exists():
        return {}
    try:
        return yaml.safe_load(meta_path.read_text()) or {}
    except Exception:
        return {}


def _save_meta(run_dir: Path, payload: dict) -> None:
    meta_path = run_dir / "bpm.meta.yaml"
    meta_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _update_export_meta(
    run_dir: Path,
    workflow_id: str,
    api_url: str,
    project_name: str,
    job_spec: dict,
    response_json: dict,
    final_json: dict | None = None,
) -> None:
    meta = _load_meta(run_dir)
    export = meta.get("export") or {}
    demux = export.get("demux") or {}

    exported_at = _now_iso()
    safe_spec = json.loads(json.dumps(job_spec))
    if isinstance(safe_spec, dict) and "password" in safe_spec:
        safe_spec["password"] = "***redacted***"

    demux.update(
        {
            "last_exported_at": exported_at,
            "workflow_id": workflow_id,
            "api_url": api_url,
            "project_name": project_name,
            "job_id": response_json.get("job_id"),
            "expiry_days": job_spec.get("expiry_days"),
            "job_spec": safe_spec,
            "response": response_json,
        }
    )
    if final_json:
        demux["final_message"] = final_json

    export["last_exported_at"] = exported_at
    export["last_workflow_id"] = workflow_id
    export["last_job_id"] = response_json.get("job_id")
    export["demux"] = demux
    meta["export"] = export
    _save_meta(run_dir, meta)


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _ansi(code: str) -> str:
    return f"\033[{code}m" if _supports_color() else ""


RESET = _ansi("0")
BOLD = _ansi("1")
BLUE = _ansi("34")
CYAN = _ansi("36")
GREEN = _ansi("32")
YELLOW = _ansi("33")


def _color(text: str, color: str, *, bold: bool = False) -> str:
    prefix = f"{BOLD if bold else ''}{color}"
    return f"{prefix}{text}{RESET}" if prefix else text


def _print_section(title: str, color: str = CYAN) -> None:
    line = "=" * 72
    print(_color(line, color))
    print(_color(title, color, bold=True))
    print(_color(line, color))


def _print_key_value(label: str, value: str, *, color: str = BLUE) -> None:
    print(f"{_color(label + ':', color, bold=True)} {value}")


def _strip_markdown_formatting(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"[*_`#]+", "", cleaned)
    cleaned = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", cleaned)
    return cleaned.strip()


def _format_export_details(text: str) -> list[str]:
    cleaned = _strip_markdown_formatting(text)
    if not cleaned:
        return []

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return []

    heading_map = {
        "main report": "Main Report",
        "access credentials": "Access Credentials",
        "publisher results": "Publisher Results",
    }
    skip_lines = {"export complete", "your export has been successfully completed."}

    output: list[str] = []
    current_section = ""
    current_publisher = False

    for raw_line in lines:
        normalized = raw_line.lower().strip()
        normalized = normalized.lstrip("- ").strip()

        if normalized in skip_lines:
            continue

        if normalized in heading_map:
            if output:
                output.append("")
            current_section = heading_map[normalized]
            current_publisher = current_section == "Publisher Results"
            output.append(current_section)
            continue

        line = raw_line.lstrip("- ").strip()

        if current_section in {"Main Report", "Access Credentials"}:
            output.append(f"- {line}")
            continue

        if current_publisher:
            if re.match(r"^Publisher\s+\d+\s*:", line, flags=re.I):
                output.append(f"- {line}")
            else:
                output.append(f"  - {line}")
            continue

        output.append(line)

    while output and output[-1] == "":
        output.pop()
    return output


def _run_with_spinner(message: str, func):
    stop_event = threading.Event()
    spinner = ["|", "/", "-", "\\"]

    def _spin():
        idx = 0
        while not stop_event.is_set():
            sys.stdout.write(f"\r{message} {spinner[idx % len(spinner)]}")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.2)
        sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
        sys.stdout.flush()

    thread = threading.Thread(target=_spin, daemon=True)
    thread.start()
    try:
        return func()
    finally:
        stop_event.set()
        thread.join()


def _is_final_message_pending(exc: HTTPError, detail: str) -> bool:
    if exc.code == 425:
        return True
    if exc.code == 404 and "Job not found" in detail:
        return True
    return False


def main() -> None:
    ctx = load_ctx()
    params = ctx.get("params") or {}

    run_dir = Path(str(params.get("run_dir") or "")).expanduser()
    if not run_dir.exists():
        raise SystemExit(f"run_dir not found: {run_dir}")
    if not run_dir.is_dir():
        raise SystemExit(f"run_dir is not a directory: {run_dir}")

    meta = _load_meta(run_dir)
    published = meta.get("published") or {}

    project_name = str(params.get("project_name") or run_dir.name)

    def _resolve_path(raw: str | Path, default_host: str) -> tuple[str, Path]:
        if isinstance(raw, Path):
            return default_host, raw
        s = str(raw)
        host, s = _split_hostpath(s, default_host)
        p = Path(s)
        return host, (p if p.is_absolute() else (run_dir / p))

    fastq_dir_raw = published.get("FASTQ_dir") or (run_dir / "output")
    multiqc_report_raw = published.get("multiqc_report") or (run_dir / "multiqc" / "multiqc_report.html")

    host_default = os.uname().nodename.split(".")[0]
    fastq_host, fastq_dir = _resolve_path(fastq_dir_raw, host_default)
    multiqc_host, multiqc_report = _resolve_path(multiqc_report_raw, host_default)

    if fastq_host == host_default and not fastq_dir.exists():
        raise SystemExit(f"FASTQ dir not found: {fastq_dir}")
    if multiqc_host == host_default and not multiqc_report.exists():
        raise SystemExit(f"MultiQC report not found: {multiqc_report}")

    api_url = str(params.get("export_engine_api_url") or "").strip() or "http://genomics.rwth-aachen.de:9500/export"
    backends = _split_csv(params.get("export_engine_backends") or "apache, owncloud, sftp")
    expiry_days = int(params.get("export_expiry_days") or 0)
    username = str(params.get("export_username") or "").strip() or _derive_username(project_name)
    password = str(params.get("export_password") or "").strip() or secrets.token_urlsafe(16)
    include_default = _parse_bool(params.get("include_in_report"), True)
    include_fastq = _parse_bool(params.get("include_in_report_fastq"), include_default)
    include_multiqc = _parse_bool(params.get("include_in_report_multiqc"), include_default)

    def _auto_link_name(path: str, dest: str) -> str:
        name = Path(dest).name if path == "." else Path(path).name
        return name.replace("_", " ").strip()

    def _export_entry(
        src_path: Path,
        dest_path: str,
        export_host: str,
        mode: str,
        include_report: bool,
        description: str,
    ) -> dict:
        entry = {
            "src": str(src_path.resolve()) if src_path.is_absolute() else str(src_path),
            "dest": dest_path,
            "host": export_host,
            "project": project_name,
            "mode": mode,
        }
        if include_report:
            entry["report_links"] = [
                {
                    "path": ".",
                    "section": "raw",
                    "description": description,
                    "link_name": _auto_link_name(".", dest_path),
                }
            ]
        return entry

    export_list = [
        _export_entry(
            fastq_dir,
            "1_Raw_data/FASTQ",
            fastq_host,
            "symlink",
            include_fastq,
            "FASTQ output from demux_bclconvert",
        ),
        _export_entry(
            multiqc_report,
            "1_Raw_data/demultiplexing_multiqc_report.html",
            multiqc_host,
            "symlink",
            include_multiqc,
            "MultiQC report from demux_bclconvert",
        ),
    ]

    job_spec = {
        "project_name": project_name,
        "export_list": export_list,
        "backend": backends,
        "username": username,
        "password": password,
        "authors": [],
        "expiry_days": expiry_days,
    }

    api_clean = api_url.rstrip("/")
    export_endpoint = api_clean if api_clean.endswith("/export") else f"{api_clean}/export"
    req = Request(
        export_endpoint,
        data=json.dumps(job_spec).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        def _post_request():
            with urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")

        resp_body = _run_with_spinner(
            "Submitting export job",
            _post_request,
        )
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise SystemExit(f"Export API request failed: {exc.code} {detail}")
    except URLError as exc:
        raise SystemExit(f"Export API request failed: {exc.reason}")

    try:
        response_json = json.loads(resp_body)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Export API returned non-JSON response: {exc}") from exc

    _update_export_meta(
        run_dir=run_dir,
        workflow_id="export_demux",
        api_url=export_endpoint,
        project_name=project_name,
        job_spec=job_spec,
        response_json=response_json,
    )

    job_id = response_json.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise SystemExit("Export API response missing job_id")

    _print_section("Export Request", BLUE)
    _print_key_value("API endpoint", export_endpoint)
    _print_key_value("Project", project_name)

    _print_section("Job Registered", GREEN)
    _print_key_value("job_id", job_id, color=GREEN)
    _print_key_value("bpm.meta.yaml", str(run_dir / "bpm.meta.yaml"), color=GREEN)

    final_endpoint = (
        f"{api_clean}/final_message/{job_id}"
        if api_clean.endswith("/export")
        else f"{api_clean}/export/final_message/{job_id}"
    )
    final_req = Request(final_endpoint, method="GET")

    def _wait_for_final_message():
        start = time.monotonic()
        while True:
            if time.monotonic() - start > FINAL_MESSAGE_TIMEOUT_SECONDS:
                raise TimeoutError(
                    f"Timed out after {FINAL_MESSAGE_TIMEOUT_SECONDS}s waiting for final export status for job_id={job_id}"
                )
            try:
                with urlopen(final_req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as exc:
                detail = exc.read().decode("utf-8") if exc.fp else str(exc)
                if _is_final_message_pending(exc, detail):
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue
                raise RuntimeError(f"Unable to fetch final message: {exc.code} {detail}") from exc
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Final export message is not valid JSON: {exc}") from exc
            except URLError:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

    try:
        final_json = _run_with_spinner(
            "Waiting for final export status",
            _wait_for_final_message,
        )
    except KeyboardInterrupt:
        raise SystemExit(
            f"Interrupted while waiting for final export status. job_id={job_id} is already stored in bpm.meta.yaml."
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(str(exc)) from exc

    formatted_message = _strip_markdown_formatting((final_json.get("formatted_message") or "").strip())
    plain_message = (final_json.get("message") or "").strip()
    status = (final_json.get("status") or final_json.get("type") or "").strip()

    _print_section("Final Export Summary", GREEN)
    if status:
        _print_key_value("Status", status, color=GREEN)
    if final_json.get("job_id"):
        _print_key_value("job_id", str(final_json["job_id"]), color=GREEN)
    if final_json.get("main_report"):
        _print_key_value("Report URL", str(final_json["main_report"]), color=GREEN)

    if formatted_message:
        print("")
        _print_section("Export Details", CYAN)
        detail_lines = _format_export_details(formatted_message)
        if detail_lines:
            print("\n".join(detail_lines))
        else:
            print(formatted_message)

    if plain_message:
        print("")
        _print_section("JSON section for MS Teams Planner", YELLOW)
        print(plain_message)

    _update_export_meta(
        run_dir=run_dir,
        workflow_id="export_demux",
        api_url=export_endpoint,
        project_name=project_name,
        job_spec=job_spec,
        response_json=response_json,
        final_json=final_json,
    )


if __name__ == "__main__":
    main()
