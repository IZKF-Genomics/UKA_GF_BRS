#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bpm.io.yamlio import safe_dump_yaml, safe_load_yaml


POLL_INTERVAL_SECONDS = 2
FINAL_MESSAGE_TIMEOUT_SECONDS = 3600


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
RED = _ansi("31")


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

def _strip_created_resources(value):
    if isinstance(value, dict):
        value.pop("created_resources", None)
        for v in value.values():
            _strip_created_resources(v)
    elif isinstance(value, list):
        for v in value:
            _strip_created_resources(v)


def _is_final_message_pending(exc: HTTPError, detail: str) -> bool:
    """
    Some export-engine deployments return 425 while others briefly return
    404 {"detail":"Job not found"} before the final message is materialized.
    Treat both as retryable pending states.
    """
    if exc.code == 425:
        return True
    if exc.code == 404 and "Job not found" in detail:
        return True
    return False


def main() -> None:
    spec = Path("export_job_spec.json")
    if not spec.exists():
        raise SystemExit(
            "export_job_spec.json not found; render the export template to generate it"
        )

    data = spec.read_text().strip()
    if not data:
        raise SystemExit("export_job_spec.json is empty")

    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"export_job_spec.json is not valid JSON: {exc}") from exc

    required_keys = {"project_name", "export_list", "backend"}
    missing = required_keys - payload.keys()
    if missing:
        raise SystemExit(f"export_job_spec.json missing keys: {sorted(missing)}")

    project_path = (Path.cwd().parent / "project.yaml").resolve()
    if not project_path.exists():
        raise SystemExit(f"project.yaml not found at {project_path}")

    project_data = safe_load_yaml(project_path)
    export_entry = None
    for entry in project_data.get("templates") or []:
        if entry.get("id") == "export":
            export_entry = entry
            break
    if export_entry is None:
        raise SystemExit("export template entry not found in project.yaml")

    params = export_entry.get("params") or {}
    api_url = params.get("export_engine_api_url")
    if not isinstance(api_url, str) or not api_url.strip():
        raise SystemExit("export_engine_api_url not set in export template params")

    # Accept either base (http://host:port) or full endpoint (.../export) to avoid double suffix.
    api_clean = api_url.rstrip("/")
    export_endpoint = api_clean if api_clean.endswith("/export") else f"{api_clean}/export"
    req = Request(
        export_endpoint,
        data=json.dumps(payload).encode("utf-8"),
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

    job_id = response_json.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise SystemExit("Export API response missing job_id")

    _print_section("Export Request", BLUE)
    _print_key_value("API endpoint", export_endpoint)
    _print_key_value("Project", str(payload.get("project_name", "")))

    export_dir = Path.cwd()
    published = export_entry.get("published") or {}
    published["export_job_id"] = job_id
    published.pop("export_final_path", None)
    published.pop("export_status", None)
    published.pop("export_main_report", None)
    export_entry["published"] = published
    _strip_created_resources(export_entry)
    safe_dump_yaml(project_path, project_data)

    _print_section("Job Registered", GREEN)
    _print_key_value("job_id", job_id, color=GREEN)
    _print_key_value("project.yaml", str(project_path), color=GREEN)

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
            except URLError as exc:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

    try:
        final_json = _run_with_spinner(
            "Waiting for final export status",
            _wait_for_final_message,
        )
    except KeyboardInterrupt:
        raise SystemExit(
            f"Interrupted while waiting for final export status. job_id={job_id} is already stored in project.yaml."
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
        print(formatted_message)

    if plain_message:
        print("")
        _print_section("JSON section for MS Teams Planner", YELLOW)
        print(plain_message)

    final_path = export_dir / f"export_final_{job_id}.json"
    final_path.write_text(json.dumps(final_json, indent=2, sort_keys=True))
    published["export_final_path"] = str(final_path)
    if final_json.get("status"):
        published["export_status"] = final_json.get("status")
    if final_json.get("main_report"):
        published["export_main_report"] = final_json.get("main_report")
    _strip_created_resources(export_entry)
    safe_dump_yaml(project_path, project_data)

    print("")
    _print_section("Artifacts", BLUE)
    _print_key_value("Final JSON", str(final_path))


if __name__ == "__main__":
    main()
