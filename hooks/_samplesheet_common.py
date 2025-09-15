from __future__ import annotations
"""
Generate an nf-core/rnaseq samplesheet.csv from demuxed FASTQs.

How it works (project mode):
- Reads project.yaml at ctx.project_dir
- Finds demux_bclconvert.published.FASTQ_dir
- Scans R1/R2 files, skips "Undetermined", pairs by index
- Writes samplesheet.csv into the current run folder (ctx.cwd)

Edit constants below if your bclconvert naming differs.
"""

import os
import glob
import csv
from pathlib import Path
from typing import Dict, List

# Use BPM's YAML helper (available when running via BPM)
from bpm.io.yamlio import safe_load_yaml


# Where to read FASTQs from (published by the demux template)
DEMUX_ID = "demux_bclconvert"
PUBLISHED_KEY = "FASTQ_dir"

# File patterns and behavior (adjust to your demux output)
READ1_EXTENSION = "_R1_001.fastq.gz"
READ2_EXTENSION = "_R2_001.fastq.gz"
SINGLE_END = False

# Optional sample name sanitization (off by default)
SANITISE_NAME = False
SANITISE_NAME_DELIMITER = "_"
SANITISE_NAME_INDEX = 1  # keep first N tokens


def _load_fastq_dir(ctx) -> Path:
    prj = Path(ctx.project_dir) / "project.yaml"
    if not prj.exists():
        raise RuntimeError(f"project.yaml not found at {prj}")
    data = safe_load_yaml(prj)
    for tpl in (data.get("templates") or []):
        if tpl.get("id") == DEMUX_ID:
            fastq_dir = (tpl.get("published") or {}).get(PUBLISHED_KEY)
            if not fastq_dir:
                raise RuntimeError(f"Published key missing: {DEMUX_ID}.{PUBLISHED_KEY}")
            p = Path(fastq_dir)
            if not p.exists():
                raise RuntimeError(f"FASTQ dir does not exist: {p}")
            return p
    raise RuntimeError(f"Template not found in project.yaml: {DEMUX_ID}")


def _sanitize(name: str) -> str:
    if not SANITISE_NAME:
        return name
    parts = name.split(SANITISE_NAME_DELIMITER)
    return SANITISE_NAME_DELIMITER.join(parts[:SANITISE_NAME_INDEX])


def _base_no_ext(p: str, ext: str) -> str:
    b = os.path.basename(p)
    return b[:-len(ext)] if b.endswith(ext) else b


def generate(ctx, strandedness: str) -> str:
    """
    Create samplesheet.csv in ctx.cwd and return its absolute path.

    strandedness: one of {"unstranded","forward","reverse"}
    """
    if strandedness not in {"unstranded", "forward", "reverse"}:
        strandedness = "unstranded"

    fqdir = _load_fastq_dir(ctx)
    out = Path(ctx.cwd) / "samplesheet.csv"

    r1s: List[str] = sorted(glob.glob(str(fqdir / f"*{READ1_EXTENSION}")))
    if not r1s:
        raise RuntimeError(f"No R1 files in {fqdir} with '*{READ1_EXTENSION}'")
    r2s: List[str] = [] if SINGLE_END else sorted(glob.glob(str(fqdir / f"*{READ2_EXTENSION}")))

    reads: Dict[str, Dict[str, List[str]]] = {}
    for p in r1s:
        sample = _sanitize(_base_no_ext(p, READ1_EXTENSION))
        if sample.startswith("Undetermined"):
            continue
        reads.setdefault(sample, {"R1": [], "R2": []})["R1"].append(p)

    if not SINGLE_END:
        for p in r2s:
            sample = _sanitize(_base_no_ext(p, READ2_EXTENSION))
            if sample.startswith("Undetermined"):
                continue
            reads.setdefault(sample, {"R1": [], "R2": []})["R2"].append(p)

    if not reads:
        raise RuntimeError("No usable FASTQ files found (all Undetermined?)")

    out.parent.mkdir(parents=True, exist_ok=True)
    header = ["sample", "fastq_1", "fastq_2", "strandedness"]
    rows: List[List[str]] = []
    for sample, rr in sorted(reads.items()):
        for i, r1 in enumerate(rr["R1"]):
            r2 = rr["R2"][i] if (not SINGLE_END and i < len(rr["R2"])) else ""
            rows.append([sample, r1, r2, strandedness])

    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)

    print(f"[samplesheet] {len(rows)} rows from {len(reads)} sample(s) -> {out}")
    return str(out)

