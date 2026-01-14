from __future__ import annotations
"""Post-render hook: generate samplesheet.csv for nf-core/scrnaseq."""

import csv
import glob
from pathlib import Path
from typing import Dict, List

from ._samplesheet_common import (
    READ1_EXTENSION,
    READ2_EXTENSION,
    SINGLE_END,
    _base_no_ext,
    _load_fastq_dir,
    _sanitize,
    _strip_sample_suffix,
)


def _expected_cells_value(ctx) -> str | None:
    raw = (ctx.params or {}).get("expected_cells")
    if raw in (None, ""):
        return None
    try:
        return str(int(raw))
    except Exception as exc:
        raise RuntimeError("expected_cells must be an integer") from exc


def main(ctx) -> str:
    fqdir = _load_fastq_dir(ctx)
    out_dir = (Path(ctx.project_dir) / ctx.template.id) if ctx.project else Path(ctx.cwd)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "samplesheet.csv"

    r1s: List[str] = sorted(glob.glob(str(fqdir / f"*{READ1_EXTENSION}")))
    if not r1s:
        raise RuntimeError(f"No R1 files in {fqdir} with '*{READ1_EXTENSION}'")
    r2s: List[str] = [] if SINGLE_END else sorted(glob.glob(str(fqdir / f"*{READ2_EXTENSION}")))

    reads: Dict[str, Dict[str, List[str]]] = {}
    for p in r1s:
        sample = _sanitize(_base_no_ext(p, READ1_EXTENSION))
        sample = _strip_sample_suffix(sample)
        if sample.startswith("Undetermined"):
            continue
        reads.setdefault(sample, {"R1": [], "R2": []})["R1"].append(p)

    if not SINGLE_END:
        for p in r2s:
            sample = _sanitize(_base_no_ext(p, READ2_EXTENSION))
            sample = _strip_sample_suffix(sample)
            if sample.startswith("Undetermined"):
                continue
            reads.setdefault(sample, {"R1": [], "R2": []})["R2"].append(p)

    if not reads:
        raise RuntimeError("No usable FASTQ files found (all Undetermined?)")

    expected_cells = _expected_cells_value(ctx)
    header = ["sample", "fastq_1", "fastq_2"]
    if expected_cells is not None:
        header.append("expected_cells")

    rows: List[List[str]] = []
    for sample, rr in sorted(reads.items()):
        for i, r1 in enumerate(rr["R1"]):
            if SINGLE_END:
                r2 = ""
            else:
                if i >= len(rr["R2"]):
                    raise RuntimeError(f"Missing R2 for sample {sample} at index {i}")
                r2 = rr["R2"][i]
            row = [sample, r1, r2]
            if expected_cells is not None:
                row.append(expected_cells)
            rows.append(row)

    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)

    print(f"[samplesheet] {len(rows)} rows from {len(reads)} sample(s) -> {out}")
    return str(out)
