#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

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

    print("[export] export_job_spec.json exists and is valid JSON.")


if __name__ == "__main__":
    main()
