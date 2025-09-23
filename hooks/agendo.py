from __future__ import annotations
from pathlib import Path
import json
import os
import base64
import urllib.request
import urllib.error


def fetch(ctx):
    """
    Pre-render hook: fetch Agendo request JSON and attach to ctx.params.

    - Reads ctx.params.agendo_id (int/str). If missing, skips.
    - Respects AGENDO_API_BASE/AGENDO_TOKEN env vars, or BRS settings.agendo.{base_url,token}.
    - Caches JSON under <project>/.bpm/agendo/<id>.json (or <out>/.bpm/agendo in ad-hoc).
    - Adds ctx.params["agendo"] with the JSON, plus convenience keys when available.
    """
    # Resolve configuration
    base = os.getenv("AGENDO_API_BASE")
    if not base:
        base = (
            ctx.brs.get("settings", {})
            .get("agendo", {})
            .get("base_url", "https://genomics.rwth-aachen.de/api")
        )
    token = os.getenv("AGENDO_TOKEN") or (
        ctx.brs.get("settings", {}).get("agendo", {}).get("token")
    )
    # Optional Basic auth via GF_API_NAME/GF_API_PASS
    basic_user = os.getenv("GF_API_NAME")
    basic_pass = os.getenv("GF_API_PASS")

    agendo_id = ctx.params.get("agendo_id")
    if agendo_id in (None, ""):
        return {"skipped": "no agendo_id param"}

    try:
        agendo_id_str = str(int(agendo_id))
    except Exception:
        agendo_id_str = str(agendo_id)

    # Determine cache root (project mode or ad-hoc)
    proj_root = Path(ctx.project_dir) if ctx.project else Path(str(ctx.cwd))
    cache_dir = proj_root / ".bpm" / "agendo"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{agendo_id_str}.json"

    data = None
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
        except Exception:
            data = None

    if data is None:
        url = f"{base.rstrip('/')}/get/request/{agendo_id_str}"
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif basic_user and basic_pass:
            b64 = base64.b64encode(f"{basic_user}:{basic_pass}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {b64}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                data = json.loads(text)
        except urllib.error.URLError as e:
            raise RuntimeError(f"Agendo fetch failed for id={agendo_id_str}: {e}") from e
        cache_file.write_text(json.dumps(data, indent=2))

    # Attach to params for Jinja/templates
    # ctx.params["agendo"] = data
    # Surface common fields if present (these will be persisted as template params)
    for k in (
        "organism",
        "application",
        "agendo_application",
        "sample_number",
        # additionally requested fields
        "ref",
        "created_by_name",
        "created_by_email",
        "group_name",
        "institute_name",
        "pi_name",
        "pi_email",
    ):
        v = data.get(k)
        if v is not None and k not in ctx.params:
            ctx.params[k] = v

    return {"ok": True, "id": agendo_id_str, "cached": cache_file.exists()}
