#!/usr/bin/env python3
from __future__ import annotations

import json
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
        "job_id",
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

    endpoint = api_url.rstrip("/") + "/export"
    req = Request(
        endpoint,
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

    job_id = response_json.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise SystemExit("Export API response missing job_id")

    payload["job_id"] = job_id
    spec.write_text(json.dumps(payload, indent=2))

    published = export_entry.get("published") or {}
    published["export_job_id"] = job_id
    export_entry["published"] = published
    safe_dump_yaml(project_path, project_data)

    print(f"[export] export_job_spec.json updated with job_id {job_id}.")
    print("[export] project.yaml updated with published export_job_id.")


if __name__ == "__main__":
    main()
