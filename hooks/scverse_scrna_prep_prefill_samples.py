from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml


FIELDS = ["sample_id", "sample_label", "batch", "condition", "patient_id", "notes"]


def _read_project_yaml(project_dir: Path) -> dict[str, Any]:
    project_yaml = project_dir / "project.yaml"
    if not project_yaml.exists():
        return {}
    data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _find_published_samplesheet(project_data: dict[str, Any]) -> str:
    templates = project_data.get("templates")
    if not isinstance(templates, list):
        return ""
    for entry in reversed(templates):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("id", "")).strip() != "nfcore_scrnaseq":
            continue
        published = entry.get("published")
        if not isinstance(published, dict):
            continue
        value = published.get("nfcore_samplesheet")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _read_samplesheet(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if "sample" not in (reader.fieldnames or []):
            raise RuntimeError(f"nfcore_samplesheet missing required 'sample' column: {path}")
        sample_ids: list[str] = []
        seen: set[str] = set()
        for row in reader:
            sample_id = str(row.get("sample", "")).strip()
            if not sample_id or sample_id in seen:
                continue
            seen.add(sample_id)
            sample_ids.append(sample_id)
    return sample_ids


def _read_existing_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return FIELDS, []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [{k: str(v or "") for k, v in row.items()} for row in reader]
    return fieldnames or FIELDS, rows


def _infer_sample_ids_from_input_params(ctx: Any) -> list[str]:
    params = getattr(ctx, "params", {}) or {}
    raw = str(params.get("input_matrix") or params.get("input_h5ad") or "").strip()
    if not raw:
        return []

    local_path = Path(ctx.materialize(raw))
    name = local_path.name
    lower = name.lower()

    if local_path.is_dir():
        if name == "per_sample_outs":
            sample_ids: list[str] = []
            for child in sorted(local_path.iterdir()):
                if not child.is_dir():
                    continue
                count_dir = child / "count"
                if count_dir.is_dir():
                    sample_ids.append(child.name)
            if sample_ids:
                return sample_ids
        if name in {"filtered_feature_bc_matrix", "raw_feature_bc_matrix"} and local_path.parent.name:
            return [local_path.parent.name]
        return [name]

    for suffix in (".h5ad", ".h5", ".mtx.gz", ".mtx"):
        if lower.endswith(suffix):
            name = name[: -len(suffix)]
            break

    for stem in ("_filtered_feature_bc_matrix", "_raw_feature_bc_matrix", "filtered_feature_bc_matrix", "raw_feature_bc_matrix"):
        if name.endswith(stem):
            trimmed = name[: -len(stem)].rstrip("._-")
            if trimmed:
                name = trimmed
            break

    return [name] if name else []


def main(ctx: Any) -> str:
    if not getattr(ctx, "project", None):
        return "[hook:scverse_scrna_prep_prefill_samples] skipped (no project context)"

    project_dir = Path(ctx.project_dir)
    render_dir = project_dir / ctx.template.id
    samples_csv = render_dir / "config" / "samples.csv"
    samples_csv.parent.mkdir(parents=True, exist_ok=True)

    project_data = _read_project_yaml(project_dir)
    published_samplesheet = _find_published_samplesheet(project_data)
    sample_ids: list[str]
    source_label: str
    if published_samplesheet:
        samplesheet_path = Path(ctx.materialize(published_samplesheet))
        if not samplesheet_path.exists():
            raise RuntimeError(f"Published nfcore_samplesheet does not exist: {samplesheet_path}")
        sample_ids = _read_samplesheet(samplesheet_path)
        source_label = str(samplesheet_path)
    else:
        sample_ids = _infer_sample_ids_from_input_params(ctx)
        if not sample_ids:
            return "[hook:scverse_scrna_prep_prefill_samples] skipped (no published nfcore_samplesheet or direct input path found)"
        source_label = "input_matrix_or_h5ad"
    existing_fields, existing_rows = _read_existing_rows(samples_csv)
    fieldnames = FIELDS + [f for f in existing_fields if f and f not in FIELDS]

    by_id: dict[str, dict[str, str]] = {}
    for row in existing_rows:
        sample_id = str(row.get("sample_id", "")).strip()
        if sample_id:
            by_id[sample_id] = {k: str(row.get(k, "")) for k in fieldnames}

    added = 0
    for sample_id in sample_ids:
        if sample_id in by_id:
            continue
        row = {k: "" for k in fieldnames}
        row["sample_id"] = sample_id
        row["sample_label"] = sample_id
        by_id[sample_id] = row
        added += 1

    rows_out = [by_id[sid] for sid in sorted(by_id)]
    with samples_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    return (
        "[hook:scverse_scrna_prep_prefill_samples] wrote "
        f"{samples_csv} (source={source_label}, total_rows={len(rows_out)}, added={added})"
    )
