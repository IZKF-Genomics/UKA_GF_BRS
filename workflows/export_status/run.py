#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


def load_ctx():
    """Load BPM ctx JSON if provided."""
    ctx_path = os.environ.get("BPM_CTX_PATH")
    if not ctx_path or not Path(ctx_path).is_file():
        return {}
    with open(ctx_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_project(project_dir: Path) -> dict:
    proj_file = project_dir / "project.yaml"
    if not proj_file.exists():
        raise SystemExit(f"project.yaml not found at {proj_file}")
    return yaml.safe_load(proj_file.read_text())


def get_export_job_id(project: dict) -> str:
    for entry in project.get("templates") or []:
        if entry.get("id") == "export":
            pub = entry.get("published") or {}
            jid = pub.get("export_job_id")
            if isinstance(jid, str) and jid.strip():
                return jid.strip()
    return ""


def get_export_api_url(project: dict, default: str) -> str:
    for entry in project.get("templates") or []:
        if entry.get("id") == "export":
            params = entry.get("params") or {}
            val = params.get("export_engine_api_url")
            if isinstance(val, str) and val.strip():
                return val.strip()
    return default


def normalize_status_endpoint(base_url: str, job_id: str) -> str:
    api_clean = base_url.rstrip("/")
    root = api_clean if api_clean.endswith("/export") else f"{api_clean}/export"
    return f"{root}/status/{job_id}"


def main() -> None:
    ctx = load_ctx()
    params = ctx.get("params") or {}

    # Resolve project directory if present in ctx
    project_dir = None
    if ctx.get("project_dir"):
        project_dir = Path(ctx["project_dir"]).resolve()

    # job_id precedence: CLI param -> project.yaml published
    job_id = str(params.get("job_id") or "").strip()
    project_data = None
    if not job_id and project_dir:
        project_data = load_project(project_dir)
        job_id = get_export_job_id(project_data)

    if not job_id:
        raise SystemExit("No job_id provided and none found in project.yaml (published.export_job_id).")

    # API URL precedence: CLI param -> project param -> default
    api_url = str(params.get("api_url") or "").strip()
    if not api_url:
        if project_data is None and project_dir:
            project_data = load_project(project_dir)
        if project_data:
            api_url = get_export_api_url(project_data, api_url)
    if not api_url:
        api_url = "http://genomics.rwth-aachen.de:9500/export"

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

    print(f"[export_status] GET {endpoint}")
    print(f"[export_status] Response: {resp_body}")

    # Best-effort JSON pretty print
    try:
        parsed = json.loads(resp_body)
    except json.JSONDecodeError:
        return
    print(json.dumps(parsed, indent=2))


if __name__ == "__main__":
    main()
