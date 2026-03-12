from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml


RDS_CANDIDATES = ("adjustedset.rds", "filteredset.rds", "normset.rds", "rgset.rds")


def _read_project_yaml(project_dir: Path) -> dict[str, Any]:
    p = project_dir / "project.yaml"
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _read_existing_registry(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    if not path.exists():
        return [], {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [dict(r) for r in reader]
        by_run = {str(r.get("run_id", "")).strip(): r for r in rows if str(r.get("run_id", "")).strip()}
        return list(reader.fieldnames or []), by_run


def _has_rds_artifact(results_rds: Path) -> bool:
    return any((results_rds / nm).exists() for nm in RDS_CANDIDATES)


def main(ctx: Any) -> str:
    auto_flag = str((ctx.params or {}).get("auto_discover_inputs", "true")).strip().lower()
    if auto_flag in {"false", "0", "no", "n"}:
        return "[hook:compare_autodiscover_registry] skipped (auto_discover_inputs=false)"

    if not getattr(ctx, "project", None):
        return "[hook:compare_autodiscover_registry] skipped (no project context)"

    project_dir = Path(ctx.project_dir)
    compare_dir = project_dir / ctx.template.id
    compare_dir.mkdir(parents=True, exist_ok=True)
    out_csv = compare_dir / "config" / "input_registry.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    project = _read_project_yaml(project_dir)
    templates = project.get("templates") if isinstance(project.get("templates"), list) else []

    base_fields = [
        "run_id",
        "dataset_id",
        "process_template",
        "array_type",
        "genome_build",
        "processed_results_dir",
        "samples_file",
        "enabled",
        "include_samples",
        "exclude_samples",
    ]
    existing_fields, existing_by_run = _read_existing_registry(out_csv)
    fieldnames = base_fields + [f for f in existing_fields if f and f not in base_fields]

    discovered_rows: list[dict[str, str]] = []
    for entry in templates:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("source_template", "")).strip() != "illumina_methylation_process":
            continue
        if str(entry.get("status", "active")).strip().lower() != "active":
            continue

        run_id = str(entry.get("id", "")).strip()
        if not run_id:
            continue

        params = entry.get("params") if isinstance(entry.get("params"), dict) else {}
        process_dir = project_dir / run_id
        results_rds = process_dir / "results" / "rds"
        has_results = _has_rds_artifact(results_rds)

        row = {k: "" for k in fieldnames}
        row["run_id"] = run_id
        row["dataset_id"] = run_id
        row["process_template"] = "illumina_methylation_process"
        row["array_type"] = str(params.get("array_type", "")).strip()
        row["genome_build"] = str(params.get("genome_build", "")).strip()
        row["processed_results_dir"] = str(Path("..") / run_id / "results" / "rds")
        row["samples_file"] = str(Path("..") / run_id / "samples.csv")
        row["enabled"] = "true" if has_results else "false"
        row["include_samples"] = ""
        row["exclude_samples"] = ""

        prev = existing_by_run.get(run_id, {})
        if prev:
            # Preserve user tuning when present.
            for k in ("dataset_id", "enabled", "include_samples", "exclude_samples", "array_type", "genome_build"):
                v = str(prev.get(k, "")).strip()
                if v:
                    row[k] = v
            for k in fieldnames:
                if not str(row.get(k, "")).strip():
                    row[k] = str(prev.get(k, ""))

        discovered_rows.append(row)

    # Keep non-process/manual rows from existing registry.
    discovered_ids = {r["run_id"] for r in discovered_rows}
    extras = [r for rid, r in existing_by_run.items() if rid not in discovered_ids]
    for r in extras:
        row = {k: str(r.get(k, "")) for k in fieldnames}
        if not row.get("enabled"):
            row["enabled"] = "false"
        discovered_rows.append(row)

    discovered_rows.sort(key=lambda r: r.get("run_id", ""))
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(discovered_rows)

    return (
        "[hook:compare_autodiscover_registry] wrote "
        f"{out_csv} (discovered={len(discovered_ids)}, preserved_extra={len(extras)})"
    )
