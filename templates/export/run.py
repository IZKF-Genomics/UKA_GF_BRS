#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bpm.io.yamlio import safe_dump_yaml, safe_load_yaml

def main() -> None:
    spec = Path("export_job_spec.json")
    if not spec.exists():
        raise SystemExit("export_job_spec.json not found; render the template first")

    data = spec.read_text().strip()
    if not data:
        raise SystemExit("export_job_spec.json is empty")

    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"export_job_spec.json is not valid JSON: {exc}") from exc

    required_keys = {
        "project_name",
        "export_list",
        "backend",
        "username",
        "password",
        "authors",
        "expiry_days",
    }
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

    # Show full API response for visibility/debugging
    print("[export] API response JSON:")
    print(json.dumps(response_json, indent=2, sort_keys=True))

    job_id = response_json.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise SystemExit("Export API response missing job_id")

    published = export_entry.get("published") or {}
    published["export_job_id"] = job_id
    published["export_response"] = response_json
    export_entry["published"] = published
    safe_dump_yaml(project_path, project_data)

    print(f"[export] project.yaml updated with published export_job_id={job_id}.")

    # Fetch final message for the job, with a short retry for "too early" responses.
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
                print(f"[export] Final message not ready (HTTP {exc.code}); retrying in {wait}s...")
                time.sleep(wait)
                continue
            detail = exc.read().decode("utf-8") if exc.fp else str(exc)
            print(f"[export] Unable to fetch final message: {exc.code} {detail}")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"[export] Unable to fetch final message: {exc}")
            break
        else:
            # Print key human-readable fields with nicer layout.
            formatted_message = (final_json.get("formatted_message") or "").strip()
            plain_message = (final_json.get("message") or "").strip()
            status = (final_json.get("status") or final_json.get("type") or "").strip()
            job_line = f"job_id: {final_json['job_id']}" if final_json.get("job_id") else ""
            report_line = (
                f"main_report: {final_json['main_report']}" if final_json.get("main_report") else ""
            )

            lines = ["=" * 60, "[export] Final Export Summary"]
            if status:
                lines.append(f"Status: {status}")
            lines.append("-" * 60)
            if formatted_message:
                lines.append(formatted_message)
            if plain_message:
                if formatted_message:
                    lines.append("")
                    lines.append("[export] Raw message:")
                lines.append(plain_message)
            if job_line or report_line:
                lines.append("-" * 60)
                if job_line:
                    lines.append(job_line)
                if report_line:
                    lines.append(report_line)
            lines.append("=" * 60)

            print("\n".join(lines))
            published["export_final_message"] = final_json
            safe_dump_yaml(project_path, project_data)
            break


if __name__ == "__main__":
    main()
