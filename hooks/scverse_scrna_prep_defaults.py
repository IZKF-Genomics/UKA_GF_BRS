"""
Pre-render hook to populate scverse_scrna_prep params from project defaults when missing.
"""

from __future__ import annotations

from pathlib import Path
import yaml


def _needs_fill(val) -> bool:
    return val is None or (isinstance(val, str) and val.strip() == "")


def _load_project_yaml(ctx) -> dict:
    if not getattr(ctx, "project", None):
        return {}
    proj_dir = Path(ctx.materialize(ctx.project.project_path))
    project_yaml = proj_dir / "project.yaml"
    if not project_yaml.exists():
        return {}
    data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _find_template_entry(project_data: dict, template_id: str):
    templates = project_data.get("templates")
    if not isinstance(templates, list):
        return None
    for entry in reversed(templates):
        if isinstance(entry, dict) and str(entry.get("id", "")).strip() == template_id:
            return entry
    return None


def _find_any_template_param(project_data: dict, param_name: str):
    templates = project_data.get("templates")
    if not isinstance(templates, list):
        return None
    for entry in reversed(templates):
        if not isinstance(entry, dict):
            continue
        params = entry.get("params")
        if not isinstance(params, dict):
            continue
        value = params.get(param_name)
        if isinstance(value, str):
            value = value.strip()
        if value not in (None, ""):
            return value
    return None


def populate(ctx) -> None:
    params = ctx.params
    project_data = _load_project_yaml(ctx)

    input_h5ad_missing = _needs_fill(params.get("input_h5ad"))
    input_matrix_missing = _needs_fill(params.get("input_matrix"))

    if input_h5ad_missing and input_matrix_missing:
        upstream = _find_template_entry(project_data, "nfcore_scrnaseq")
        published = upstream.get("published") if isinstance(upstream, dict) else {}
        candidate = published.get("nfcore_scrnaseq_res_mt") if isinstance(published, dict) else None
        if candidate:
            try:
                params["input_h5ad"] = ctx.materialize(candidate)
            except Exception:
                params["input_h5ad"] = str(candidate)
        elif not getattr(ctx, "project", None):
            raise RuntimeError("input_h5ad is required in ad-hoc mode")
        else:
            raise RuntimeError(
                "Neither input_h5ad nor input_matrix was provided, and no published nfcore_scrnaseq_res_mt was found in project.yaml"
            )

    if _needs_fill(params.get("input_matrix")):
        params["input_matrix"] = ""

    if _needs_fill(params.get("input_format")):
        params["input_format"] = "auto"

    if _needs_fill(params.get("sample_metadata")):
        params["sample_metadata"] = ""

    if _needs_fill(params.get("organism")):
        organism = _find_any_template_param(project_data, "organism")
        if organism is not None:
            params["organism"] = str(organism)
            print(f"[hook:scverse_scrna_prep_defaults] organism <- {params['organism']}")
        else:
            params["organism"] = ""
            print("[hook:scverse_scrna_prep_defaults] organism not found in project.yaml; leaving empty")
