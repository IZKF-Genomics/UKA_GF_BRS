#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import yaml


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


def _materialize_hostpath(raw: str) -> str:
    """
    Convert a host:abs/path string to a local absolute path string.
    If no host prefix, return the string unchanged.
    """
    if ":" in raw:
        _, rest = raw.split(":", 1)
        return rest if rest.startswith("/") else f"/{rest}"
    return raw


def _load_meta(run_dir: Path) -> dict:
    meta_path = run_dir / "bpm.meta.yaml"
    if not meta_path.exists():
        return {}
    try:
        return yaml.safe_load(meta_path.read_text()) or {}
    except Exception:
        return {}


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

    # Resolve FASTQ dir and MultiQC report, preferring published paths in bpm.meta.yaml
    def _resolve_path(raw: str | Path) -> Path:
        if isinstance(raw, Path):
            return raw
        s = str(raw)
        if ":" in s:
            s = _materialize_hostpath(s)
        p = Path(s)
        return p if p.is_absolute() else (run_dir / p)

    fastq_dir_raw = published.get("FASTQ_dir") or (run_dir / "output")
    multiqc_report_raw = published.get("multiqc_report") or (run_dir / "multiqc" / "multiqc_report.html")

    fastq_dir = _resolve_path(fastq_dir_raw)
    multiqc_report = _resolve_path(multiqc_report_raw)

    if not fastq_dir.exists():
        raise SystemExit(f"FASTQ dir not found: {fastq_dir}")
    if not multiqc_report.exists():
        raise SystemExit(f"MultiQC report not found: {multiqc_report}")

    api_url = str(params.get("export_engine_api_url") or "").strip() or "http://genomics.rwth-aachen.de:9500/export"
    backends = _split_csv(params.get("export_engine_backends") or "apache, owncloud, sftp")
    expiry_days = int(params.get("export_expiry_days") or 0)
    username = str(params.get("export_username") or "").strip() or _derive_username(project_name)
    password = str(params.get("export_password") or "").strip() or secrets.token_urlsafe(16)

    host = os.uname().nodename.split(".")[0]

    export_list = [
        {
            "src": str(fastq_dir.resolve()),
            "dest": "1_Raw_data/FASTQ",
            "host": host,
            "project": project_name,
            "mode": "symlink",
            "include_in_report": True,
            "report_section": "raw",
            "description": "FASTQ output from demux_bclconvert",
        },
        {
            "src": str(multiqc_report.resolve()),
            "dest": "1_Raw_data/demultiplexing_multiqc_report.html",
            "host": host,
            "project": project_name,
            "mode": "copy",
            "include_in_report": True,
            "report_section": "raw",
            "description": "MultiQC report from demux_bclconvert",
        },
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

    spec_path = run_dir / "export_job_spec.json"
    spec_path.write_text(json.dumps(job_spec, indent=2))
    print(f"[export_demux] Wrote spec -> {spec_path}")

    api_clean = api_url.rstrip("/")
    export_endpoint = api_clean if api_clean.endswith("/export") else f"{api_clean}/export"
    req = Request(
        export_endpoint,
        data=json.dumps(job_spec).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise SystemExit(f"Export API request failed: {exc.code} {detail}")
    except URLError as exc:
        raise SystemExit(f"Export API request failed: {exc.reason}")

    try:
        response_json = json.loads(resp_body)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Export API returned non-JSON response: {exc}") from exc

    print("[export_demux] API response JSON:")
    print(json.dumps(response_json, indent=2, sort_keys=True))

    (run_dir / "export_response.json").write_text(json.dumps(response_json, indent=2))

    job_id = response_json.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise SystemExit("Export API response missing job_id")

    final_endpoint = (
        f"{api_clean}/final_message/{job_id}"
        if api_clean.endswith("/export")
        else f"{api_clean}/export/final_message/{job_id}"
    )
    final_req = Request(final_endpoint, method="GET")

    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen(final_req, timeout=30) as resp:
                final_body = resp.read().decode("utf-8")
            final_json = json.loads(final_body)
        except HTTPError as exc:
            if exc.code == 425 and attempt < max_attempts:
                wait = attempt * 5
                print(f"[export_demux] Final message not ready (HTTP {exc.code}); retrying in {wait}s...")
                time.sleep(wait)
                continue
            detail = exc.read().decode("utf-8") if exc.fp else str(exc)
            print(f"[export_demux] Unable to fetch final message: {exc.code} {detail}")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"[export_demux] Unable to fetch final message: {exc}")
            break
        else:
            formatted = (final_json.get("formatted_message") or "").strip()
            plain = (final_json.get("message") or "").strip()
            status = (final_json.get("status") or final_json.get("type") or "").strip()
            job_line = f"job_id: {final_json['job_id']}" if final_json.get("job_id") else ""
            report_line = (
                f"main_report: {final_json['main_report']}" if final_json.get("main_report") else ""
            )

            lines = ["=" * 60, "[export_demux] Final Export Summary"]
            if status:
                lines.append(f"Status: {status}")
            lines.append("-" * 60)
            if formatted:
                lines.append(formatted)
            if plain:
                if formatted:
                    lines.append("")
                    lines.append("[export_demux] Raw message:")
                lines.append(plain)
            if job_line or report_line:
                lines.append("-" * 60)
                if job_line:
                    lines.append(job_line)
                if report_line:
                    lines.append(report_line)
            lines.append("=" * 60)
            print("\n".join(lines))
            (run_dir / "export_final_message.json").write_text(json.dumps(final_json, indent=2))
            break


if __name__ == "__main__":
    main()
