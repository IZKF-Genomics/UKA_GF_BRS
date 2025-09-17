from __future__ import annotations
import http
import os
from pathlib import Path


API_BASE = "https://genomics.rwth-aachen.de/api/get/samplesheet/flowcell/"


def _get_creds_from_params_or_env(ctx) -> tuple[str | None, str | None]:
    """Prefer params (gf_api_name/gf_api_pass), fallback to env (GF_API_NAME/GF_API_PASS)."""
    user = (ctx.params or {}).get("gf_api_name") or os.getenv("GF_API_NAME")
    pw = (ctx.params or {}).get("gf_api_pass") or os.getenv("GF_API_PASS")
    user = str(user).strip() if user is not None else None
    pw = str(pw).strip() if pw is not None else None
    return user or None, pw or None


def _parse_flowcell_id(bcl_dir: str) -> str | None:
    base = os.path.basename(os.path.normpath(bcl_dir or ""))
    if not base:
        return None
    parts = base.split("_")
    last = parts[-1] if parts else ""
    if not last:
        return None
    return last[1:] if len(last) >= 2 and last[0].isalpha() else last


def main(ctx) -> None:
    """
    Post-render hook: fetch samplesheet.csv from API into the run directory.

    Controls:
      - use_api_samplesheet (bool, default true): toggle on/off.
      - gf_api_name/gf_api_pass (params) or GF_API_NAME/GF_API_PASS (env): credentials.

    Behavior: Fail-fast on any error (abort render).
    """
    use_api = bool((ctx.params or {}).get("use_api_samplesheet", True))
    if not use_api:
        print("[get_api_samplesheet] use_api_samplesheet=false; skipping")
        return

    bcl_dir = str((ctx.params or {}).get("bcl_dir") or "").strip()
    if not bcl_dir:
        raise RuntimeError("bcl_dir missing; cannot derive flowcell_id")

    # Determine run directory
    run_dir = (Path(ctx.project_dir) / ctx.template.id) if ctx.project else Path(ctx.cwd)
    run_dir.mkdir(parents=True, exist_ok=True)
    out_csv = run_dir / "samplesheet.csv"

    # Resolve flowcell id from bcl_dir
    flowcell = _parse_flowcell_id(bcl_dir) or ""
    if not flowcell:
        raise RuntimeError("Could not determine flowcell_id from bcl_dir")

    # Persist for downstream usage (optional)
    try:
        ctx.params["flowcell_id"] = flowcell
    except Exception:
        pass

    # Credentials
    user, pw = _get_creds_from_params_or_env(ctx)
    if not user or not pw:
        raise RuntimeError("Missing GF_API_NAME/GF_API_PASS (or gf_api_name/gf_api_pass param)")

    try:
        import requests
        from requests.auth import HTTPBasicAuth
    except Exception:
        raise RuntimeError("Python 'requests' package not available for hooks")

    url = f"{API_BASE}{flowcell}"
    try:
        resp = requests.get(url, auth=HTTPBasicAuth(user, pw), timeout=20)
    except Exception as e:
        raise RuntimeError(f"Network error fetching samplesheet: {e}")

    if resp.status_code != http.HTTPStatus.OK:
        raise RuntimeError(f"HTTP {resp.status_code} from API for flowcell {flowcell}")

    try:
        out_csv.write_bytes(resp.content)
        print(f"[get_api_samplesheet] Downloaded samplesheet for {flowcell} → {out_csv}")
    except Exception as e:
        raise RuntimeError(f"Failed to write samplesheet: {e}")

