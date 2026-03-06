from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bpm.io.yamlio import safe_dump_yaml, safe_load_yaml


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_metadata_context(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw = safe_load_yaml(path)
    return raw if isinstance(raw, dict) else {}


def _extract_identifiers(meta_ctx: Dict[str, Any]) -> Dict[str, str]:
    mid = meta_ctx.get("metadata_identifiers") or {}
    if not isinstance(mid, dict):
        mid = {}
    ag = mid.get("agendo_id")
    fc = mid.get("flowcell_id")
    return {
        "agendo_id": str(ag).strip() if ag is not None else "",
        "flowcell_id": str(fc).strip() if fc is not None else "",
    }


def _load_file_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"metadata_file not found: {path}")
    txt = path.read_text(encoding="utf-8", errors="replace").strip()
    if not txt:
        raise ValueError(f"metadata_file is empty: {path}")
    if path.suffix.lower() in (".yaml", ".yml"):
        raw = safe_load_yaml(path)
    else:
        raw = json.loads(txt)
    if not isinstance(raw, dict):
        raise ValueError("metadata payload must be a JSON/YAML object")
    return raw


def _fetch_api_payload(
    base_url: str,
    endpoint: str,
    ids: Dict[str, str],
    timeout: int,
) -> Dict[str, Any]:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError("metadata_api_url is empty")
    ep = (endpoint or "/project-output").strip()
    if not ep.startswith("/"):
        ep = "/" + ep
    params = {}
    if ids.get("agendo_id"):
        params["agendo_id"] = ids["agendo_id"]
    if ids.get("flowcell_id"):
        params["flowcell_id"] = ids["flowcell_id"]
    query = f"?{urlencode(params)}" if params else ""
    url = f"{base}{ep}{query}"

    req = Request(url=url, headers={"Accept": "application/json"}, method="GET")
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    data = json.loads(body) if body else {}
    if not isinstance(data, dict):
        raise ValueError("API metadata response is not a JSON object")
    return data


def _mock_payload(ids: Dict[str, str]) -> Dict[str, Any]:
    return {
        "ProjectOutput": {
            "application": "unknown",
            "umi": "unknown",
            "spike_in": "unknown",
            "library_kit": "unknown",
            "index_kit": "unknown",
            "sequencer": "unknown",
            "sequencing_kit": "unknown",
            "read_type": "unknown",
            "run_date": None,
            "run_name": None,
            "flow_cell": ids.get("flowcell_id") or None,
            "agendo_id": int(ids["agendo_id"]) if ids.get("agendo_id", "").isdigit() else ids.get("agendo_id") or None,
            "organism": "unknown",
        },
        "RunMetadataDB": {
            "flowcell": ids.get("flowcell_id") or None,
            "paired": None,
            "read1_cycles": None,
            "index1_cycles": None,
            "index2_cycles": None,
            "read2_cycles": None,
        },
        "PredictionConfidence": None,
    }


def _normalize_payload(raw: Dict[str, Any], ids: Dict[str, str], source_mode: str) -> Dict[str, Any]:
    po = raw.get("ProjectOutput") if isinstance(raw.get("ProjectOutput"), dict) else {}
    rm = raw.get("RunMetadataDB") if isinstance(raw.get("RunMetadataDB"), dict) else {}
    conf = raw.get("PredictionConfidence")

    flowcell = po.get("flow_cell") or rm.get("flowcell") or ids.get("flowcell_id") or None
    agendo = po.get("agendo_id") or ids.get("agendo_id") or None
    run_name = po.get("run_name") or rm.get("project_name") or None

    return {
        "source": {
            "provider": "genomics_api",
            "mode": source_mode,
            "fetched_at": _now_utc(),
            "prediction_confidence": conf,
        },
        "identifiers": {
            "agendo_id": agendo,
            "flowcell_id": flowcell,
            "run_name": run_name,
            "run_project_name": rm.get("project_name"),
            "agendo_link": po.get("agendo_link"),
        },
        "protocol": {
            "application": po.get("application"),
            "agendo_application": po.get("agendo_application"),
            "sciebo_application": po.get("sciebo_application"),
            "library_kit": po.get("library_kit"),
            "index_kit": po.get("index_kit"),
            "umi": po.get("umi"),
            "spike_in": po.get("spike_in"),
            "organism": po.get("organism"),
        },
        "sequencing": {
            "platform": po.get("sequencer"),
            "instrument": rm.get("instrument"),
            "sequencing_kit": po.get("sequencing_kit") or rm.get("seq_kit"),
            "read_type": po.get("read_type"),
            "paired": rm.get("paired"),
            "cycles": {
                "read1": po.get("cycles_read1") or rm.get("read1_cycles"),
                "index1": po.get("cycles_index1") or rm.get("index1_cycles"),
                "index2": po.get("cycles_index2") or rm.get("index2_cycles"),
                "read2": po.get("cycles_read2") or rm.get("read2_cycles"),
            },
            "run_date": po.get("run_date") or rm.get("date"),
            "operator": po.get("operator"),
        },
        "project": {
            "project_ref": po.get("ref") or po.get("project"),
            "provider_name": po.get("provider"),
            "sample_number": po.get("sample_number"),
            "status": po.get("status"),
            "created_by_name": po.get("created_by_name"),
            "created_by_email": po.get("created_by_email"),
            "group_name": po.get("group_name") or po.get("group_"),
            "institute_name": po.get("institute_name"),
            "pi_name": po.get("pi_name"),
            "pi_email": po.get("pi_email"),
        },
    }


def main(ctx: Any) -> Dict[str, Any]:
    if not getattr(ctx, "project", None):
        return {"status": "skipped", "reason": "no_project_context"}

    out_dir = Path(ctx.project_dir) / ctx.template.id
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_ctx_path = out_dir / "metadata_context.yaml"
    meta_ctx = _read_metadata_context(meta_ctx_path)
    ids = _extract_identifiers(meta_ctx)

    mode = str(ctx.params.get("metadata_source") or "auto").strip().lower()
    api_url = str(ctx.params.get("metadata_api_url") or "https://genomics.rwth-aachen.de/api").strip()
    api_endpoint = str(ctx.params.get("metadata_api_endpoint") or "/project-output").strip()
    timeout = int(ctx.params.get("metadata_api_timeout") or 20)
    metadata_file = str(ctx.params.get("metadata_file") or "").strip()

    resolved_mode = mode
    raw: Dict[str, Any] = {}
    fetch_error = ""

    try:
        if mode == "none":
            resolved_mode = "none"
            raw = {}
        elif mode == "file":
            resolved_mode = "file"
            mf = Path(metadata_file).expanduser()
            if not mf.is_absolute():
                mf = (Path(ctx.project_dir) / mf).resolve()
            raw = _load_file_payload(mf)
        elif mode == "mock":
            resolved_mode = "mock"
            raw = _mock_payload(ids)
        elif mode == "api":
            resolved_mode = "api"
            raw = _fetch_api_payload(api_url, api_endpoint, ids, timeout)
        else:  # auto
            if metadata_file:
                mf = Path(metadata_file).expanduser()
                if not mf.is_absolute():
                    mf = (Path(ctx.project_dir) / mf).resolve()
                if mf.exists():
                    resolved_mode = "file"
                    raw = _load_file_payload(mf)
                else:
                    raise FileNotFoundError(f"metadata_file not found in auto mode: {mf}")
            elif ids.get("agendo_id") or ids.get("flowcell_id"):
                try:
                    resolved_mode = "api"
                    raw = _fetch_api_payload(api_url, api_endpoint, ids, timeout)
                except Exception as e:
                    fetch_error = str(e)
                    resolved_mode = "mock"
                    raw = _mock_payload(ids)
            else:
                resolved_mode = "mock"
                raw = _mock_payload(ids)
    except Exception as e:
        fetch_error = str(e)
        resolved_mode = "mock"
        raw = _mock_payload(ids)

    raw_path = out_dir / "metadata_raw.json"
    raw_path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")

    normalized = _normalize_payload(raw, ids, resolved_mode)
    norm_path = out_dir / "metadata_normalized.yaml"
    safe_dump_yaml(norm_path, normalized)

    merged = dict(meta_ctx)
    merged["metadata_fetch"] = {
        "mode_requested": mode,
        "mode_used": resolved_mode,
        "api_url": api_url,
        "api_endpoint": api_endpoint,
        "metadata_file": metadata_file or None,
        "error": fetch_error or None,
        "raw_path": str(raw_path),
        "normalized_path": str(norm_path),
    }
    safe_dump_yaml(meta_ctx_path, merged)

    return {
        "status": "ok",
        "mode_used": resolved_mode,
        "raw_path": str(raw_path),
        "normalized_path": str(norm_path),
        "error": fetch_error or None,
    }

