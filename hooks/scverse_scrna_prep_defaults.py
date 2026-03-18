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


def populate(ctx) -> None:
    params = ctx.params
    project_data = _load_project_yaml(ctx)

    if _needs_fill(params.get("input_h5ad")):
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
                "input_h5ad not provided and no published nfcore_scrnaseq_res_mt found in project.yaml"
            )

    if _needs_fill(params.get("sample_metadata")):
        params["sample_metadata"] = ""
