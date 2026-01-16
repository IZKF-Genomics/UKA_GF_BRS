from __future__ import annotations
"""
Draft samplesheet generator for nf-core/cutandrun.

- Scans demux FASTQs from project.yaml (demux_bclconvert published FASTQ_dir).
- Derives group names from Illumina-style filenames and strips suffixes like _S1.
- Writes samplesheet.csv into the template render directory.
"""

import csv
import glob
import re
from pathlib import Path
from typing import Dict, List, Tuple

from bpm.io.yamlio import safe_load_yaml


DEMUX_ID = "demux_bclconvert"
PUBLISHED_KEY = "FASTQ_dir"
FASTQ_PATTERNS = ("*.fastq.gz", "*.fq.gz")

READ_RE = re.compile(
    r"^(?P<sample>.+?)(?:_S\d+)?(?:_L\d{3})?_(?P<read>R1|R2)(?:_001)?\.(?:fastq|fq)\.gz$",
    re.IGNORECASE,
)


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
            if isinstance(fastq_dir, str) and ":" in fastq_dir:
                local_path = ctx.materialize(fastq_dir)
            else:
                local_path = fastq_dir
            p = Path(str(local_path))
            if not p.exists():
                raise RuntimeError(f"FASTQ dir does not exist: {p}")
            return p
    raise RuntimeError(f"Template not found in project.yaml: {DEMUX_ID}")


def _collect_fastqs(fqdir: Path) -> List[Path]:
    files: List[Path] = []
    for pat in FASTQ_PATTERNS:
        files.extend(Path(p) for p in glob.glob(str(fqdir / pat)))
    return sorted({p.resolve() for p in files})


def _parse_fastq_name(path: Path) -> Tuple[str, str] | None:
    base = path.name
    m = READ_RE.match(base)
    if not m:
        return None
    sample = m.group("sample")
    sample = re.sub(r"_S\d+$", "", sample)
    return sample, m.group("read").upper()


def _detect_control_group(groups: List[str]) -> str | None:
    for g in groups:
        if g.lower() == "igg_ctrl":
            return g
    for g in groups:
        gl = g.lower()
        if "igg" in gl or "control" in gl:
            return g
    return None


def main(ctx) -> str:
    fqdir = _load_fastq_dir(ctx)
    fastqs = _collect_fastqs(fqdir)
    if not fastqs:
        raise RuntimeError(f"No FASTQ files found in {fqdir}")

    reads: Dict[str, Dict[str, List[str]]] = {}
    unmatched: List[str] = []
    for p in fastqs:
        parsed = _parse_fastq_name(p)
        if not parsed:
            unmatched.append(p.name)
            continue
        sample, read = parsed
        if sample.startswith("Undetermined"):
            continue
        reads.setdefault(sample, {"R1": [], "R2": []})[read].append(str(p))

    if not reads:
        raise RuntimeError("No FASTQ files matched Illumina paired-end naming.")
    if unmatched:
        msg = ", ".join(unmatched[:5])
        raise RuntimeError(f"Unrecognized FASTQ names (examples): {msg}")

    groups = sorted(reads.keys())
    control_group = _detect_control_group(groups)

    if ctx.project:
        out_dir = Path(ctx.project_dir) / ctx.template.id
    else:
        out_dir = Path(ctx.cwd)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "samplesheet.csv"

    header = ["group", "replicate", "fastq_1", "fastq_2", "control"]
    rows: List[List[str]] = []
    for group in groups:
        r1s = sorted(reads[group]["R1"])
        r2s = sorted(reads[group]["R2"])
        if len(r1s) != len(r2s):
            raise RuntimeError(f"Mismatched R1/R2 counts for group '{group}'")
        for i, (r1, r2) in enumerate(zip(r1s, r2s), start=1):
            control = "" if not control_group or group == control_group else control_group
            rows.append([group, str(i), r1, r2, control])

    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)

    print(f"[samplesheet] {len(rows)} rows from {len(groups)} group(s) -> {out}")
    return str(out)
