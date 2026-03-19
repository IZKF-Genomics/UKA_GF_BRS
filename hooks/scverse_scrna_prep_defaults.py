"""
Pre-render hook to populate scverse_scrna_prep params from project defaults when missing.
"""

from __future__ import annotations

from pathlib import Path
import yaml

GENOME_TO_ORGANISM = {
    "grch38": "hsapiens",
    "hg38": "hsapiens",
    "grcm39": "mmusculus",
    "grcm38": "mmusculus",
    "mm10": "mmusculus",
    "mratbn7.2": "rnorvegicus",
    "rn7": "rnorvegicus",
}


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

    if not _needs_fill(params.get("input_h5ad")):
        try:
            params["input_h5ad"] = str(ctx.materialize(str(params["input_h5ad"]).strip()))
        except Exception:
            params["input_h5ad"] = str(params["input_h5ad"]).strip()

    if not _needs_fill(params.get("input_matrix")):
        try:
            params["input_matrix"] = str(ctx.materialize(str(params["input_matrix"]).strip()))
        except Exception:
            params["input_matrix"] = str(params["input_matrix"]).strip()

    input_h5ad_missing = _needs_fill(params.get("input_h5ad"))
    input_matrix_missing = _needs_fill(params.get("input_matrix"))

    if input_h5ad_missing and input_matrix_missing:
        candidate = None
        source_template = ""
        ambient_applied = False
        ambient_method = "none"

        cellbender_upstream = _find_template_entry(project_data, "cellbender_remove_background")
        cellbender_published = cellbender_upstream.get("published") if isinstance(cellbender_upstream, dict) else {}
        candidate = (
            cellbender_published.get("cellbender_corrected_matrix")
            if isinstance(cellbender_published, dict)
            else None
        )
        if candidate:
            source_template = "cellbender_remove_background"
            ambient_applied = True
            ambient_method = "cellbender"
        else:
            upstream = _find_template_entry(project_data, "nfcore_scrnaseq")
            published = upstream.get("published") if isinstance(upstream, dict) else {}
            candidate = published.get("nfcore_scrnaseq_res_mt") if isinstance(published, dict) else None
            if candidate:
                source_template = "nfcore_scrnaseq"

        if candidate:
            try:
                params["input_h5ad"] = ctx.materialize(candidate)
            except Exception:
                params["input_h5ad"] = str(candidate)
            params["input_source_template"] = source_template
            params["ambient_correction_applied"] = ambient_applied
            params["ambient_correction_method"] = ambient_method
        elif not getattr(ctx, "project", None):
            raise RuntimeError("input_h5ad is required in ad-hoc mode")
        else:
            raise RuntimeError(
                "Neither input_h5ad nor input_matrix was provided, and no published cellbender_corrected_matrix or nfcore_scrnaseq_res_mt was found in project.yaml"
            )

    if _needs_fill(params.get("input_matrix")):
        params["input_matrix"] = ""

    if _needs_fill(params.get("input_source_template")):
        params["input_source_template"] = "manual"

    if params.get("ambient_correction_applied") is None:
        params["ambient_correction_applied"] = False

    if _needs_fill(params.get("ambient_correction_method")):
        params["ambient_correction_method"] = "none"

    if _needs_fill(params.get("input_format")):
        params["input_format"] = "auto"

    if _needs_fill(params.get("sample_metadata")):
        params["sample_metadata"] = ""
    elif not _needs_fill(params.get("sample_metadata")):
        try:
            params["sample_metadata"] = str(ctx.materialize(str(params["sample_metadata"]).strip()))
        except Exception:
            params["sample_metadata"] = str(params["sample_metadata"]).strip()

    if _needs_fill(params.get("organism")):
        organism = _find_any_template_param(project_data, "organism")
        if organism is not None:
            params["organism"] = str(organism)
            print(f"[hook:scverse_scrna_prep_defaults] organism <- {params['organism']}")
        else:
            genome = _find_any_template_param(project_data, "genome")
            mapped = GENOME_TO_ORGANISM.get(str(genome).strip().lower(), "") if genome is not None else ""
            params["organism"] = mapped
            if mapped:
                print(f"[hook:scverse_scrna_prep_defaults] organism <- {mapped} (from genome={genome})")
            else:
                print("[hook:scverse_scrna_prep_defaults] organism not found in project.yaml; leaving empty")
