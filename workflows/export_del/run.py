#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

def load_ctx() -> dict:
    """Load BPM ctx JSON if provided."""
    ctx_path = os.environ.get("BPM_CTX_PATH")
    if not ctx_path or not Path(ctx_path).is_file():
        return {}
    with open(ctx_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def normalize_status_endpoint(base_url: str, job_id: str) -> str:
    api_clean = base_url.rstrip("/")
    root = api_clean if api_clean.endswith("/export") else f"{api_clean}/export"
    return f"{root}/status/{job_id}"


def normalize_delete_endpoint(base_url: str, project_id: str) -> str:
    api_clean = base_url.rstrip("/")
    root = api_clean if api_clean.endswith("/export") else f"{api_clean}/export"
    return f"{root}/{project_id}"


def project_id_from_status(api_url: str, job_id: str) -> str:
    endpoint = normalize_status_endpoint(api_url, job_id)
    req = Request(endpoint, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(req, timeout=15) as resp:
            resp_body = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise SystemExit(f"Status API request failed: {exc.code} {detail}")
    except URLError as exc:
        raise SystemExit(f"Status API request failed: {exc.reason}")

    try:
        parsed = json.loads(resp_body)
    except json.JSONDecodeError:
        return ""

    for key in ("project_id", "project_name", "project"):
        val = parsed.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def main() -> None:
    ctx = load_ctx()
    params = ctx.get("params") or {}

    project_id = str(params.get("project_id") or "").strip()
    job_id = str(params.get("job_id") or "").strip()

    api_url = str(params.get("api_url") or "").strip()
    if not api_url:
        api_url = "http://genomics.rwth-aachen.de:9500/export"

    if not project_id and job_id:
        project_id = project_id_from_status(api_url, job_id)

    if not project_id:
        raise SystemExit("No project_id provided and none could be derived from job_id.")

    endpoint = normalize_delete_endpoint(api_url, project_id)
    req = Request(endpoint, headers={"Accept": "application/json"}, method="DELETE")

    try:
        with urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise SystemExit(f"Delete API request failed: {exc.code} {detail}")
    except URLError as exc:
        raise SystemExit(f"Delete API request failed: {exc.reason}")

    print(f"[export_del] DELETE {endpoint}")
    print(f"[export_del] Response: {resp_body}")

    try:
        parsed = json.loads(resp_body)
    except json.JSONDecodeError:
        return
    print(json.dumps(parsed, indent=2))


if __name__ == "__main__":
    main()
