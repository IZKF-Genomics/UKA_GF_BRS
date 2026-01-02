#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable
from urllib.parse import urlparse
from urllib.request import urlopen

import yaml  # type: ignore


def log(msg: str) -> None:
    print(f"[ref_genomes] {msg}")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def download_or_copy(src: str, dest: Path, force: bool) -> Path:
    ensure_dir(dest.parent)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        log(f"exists: {dest}")
        return dest
    if is_url(src):
        log(f"download: {src} -> {dest}")
        with urlopen(src) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return dest
    p = Path(src)
    if not p.exists():
        raise SystemExit(f"Source file does not exist: {src}")
    log(f"stage: {src} -> {dest}")
    shutil.copyfile(p, dest)
    return dest


def decompress_if_needed(src: Path, dest: Path, force: bool) -> Path:
    ensure_dir(dest.parent)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        log(f"exists: {dest}")
        return dest
    if src.suffix == ".gz":
        log(f"decompress: {src.name} -> {dest.name}")
        with gzip.open(src, "rb") as f_in, open(dest, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        return dest
    shutil.copyfile(src, dest)
    return dest


def concat_files(parts: Iterable[Path], dest: Path, force: bool) -> Path:
    ensure_dir(dest.parent)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        log(f"exists: {dest}")
        return dest
    with open(dest, "wb") as f_out:
        for p in parts:
            with open(p, "rb") as f_in:
                shutil.copyfileobj(f_in, f_out)
    return dest


def run(cmd: list[str], cwd: Path | None = None) -> None:
    log(" ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None)


def index_star(fasta: Path, gtf: Path | None, outdir: Path, threads: int) -> None:
    ensure_dir(outdir)
    cmd = [
        "STAR",
        "--runMode",
        "genomeGenerate",
        "--runThreadN",
        str(threads),
        "--genomeDir",
        str(outdir),
        "--genomeFastaFiles",
        str(fasta),
    ]
    if gtf:
        cmd += ["--sjdbGTFfile", str(gtf)]
    run(cmd)


def index_bowtie2(fasta: Path, outdir: Path, prefix: str) -> None:
    ensure_dir(outdir)
    run(["bowtie2-build", str(fasta), str(outdir / prefix)])


def index_bwa(fasta: Path, outdir: Path, prefix: str) -> None:
    ensure_dir(outdir)
    run(["bwa", "index", "-p", str(outdir / prefix), str(fasta)])


def index_hisat2(fasta: Path, outdir: Path, prefix: str) -> None:
    ensure_dir(outdir)
    run(["hisat2-build", str(fasta), str(outdir / prefix)])


def index_salmon(fasta: Path, outdir: Path) -> None:
    ensure_dir(outdir)
    run(["salmon", "index", "-t", str(fasta), "-i", str(outdir)])


def index_kallisto(fasta: Path, outdir: Path) -> None:
    ensure_dir(outdir)
    run(["kallisto", "index", "-i", str(outdir / "kallisto.idx"), str(fasta)])


def tool_done(path: Path) -> Path:
    return path / ".done"


def should_skip(outdir: Path, force: bool) -> bool:
    return tool_done(outdir).exists() and not force


def mark_done(outdir: Path) -> None:
    tool_done(outdir).write_text("ok\n")


def build_indices(
    genome_id: str,
    fasta: Path,
    gtf: Path | None,
    out_root: Path,
    tools: list[str],
    threads: int,
    force: bool,
) -> None:
    for tool in tools:
        tool_dir = out_root / "indices" / tool
        if should_skip(tool_dir, force):
            log(f"skip {genome_id} {tool} (exists)")
            continue
        if tool == "star":
            index_star(fasta, gtf, tool_dir, threads)
        elif tool == "bowtie2":
            index_bowtie2(fasta, tool_dir, genome_id)
        elif tool == "bwa":
            index_bwa(fasta, tool_dir, genome_id)
        elif tool == "hisat2":
            index_hisat2(fasta, tool_dir, genome_id)
        elif tool == "salmon":
            index_salmon(fasta, tool_dir)
        elif tool == "kallisto":
            index_kallisto(fasta, tool_dir)
        else:
            raise SystemExit(f"Unknown tool: {tool}")
        mark_done(tool_dir)


def normalize_path(base: Path, path_str: str) -> Path:
    if is_url(path_str):
        name = Path(urlparse(path_str).path).name
        return base / name
    return Path(path_str).expanduser().resolve()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Build genome indices with optional ERCC augmentation.")
    ap.add_argument("--config", required=True, help="Path to genomes.yaml")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--force", action="store_true", help="Re-download and rebuild outputs")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config).resolve()
    outdir = Path(args.outdir).resolve()
    ensure_dir(outdir)

    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    defaults: Dict[str, Any] = cfg.get("defaults") or {}
    tools_default = defaults.get("tools") or []
    threads = int(defaults.get("threads") or 16)
    memory_gb = int(defaults.get("memory_gb") or 64)
    with_ercc = bool(cfg.get("with_ercc", True))
    ercc_cfg = cfg.get("ercc") or {}
    ercc_fa = ercc_cfg.get("fasta", "ERCC92/ERCC92.fa")
    ercc_gtf = ercc_cfg.get("gtf", "ERCC92/ERCC92.gtf")

    log(f"Output root: {outdir}")
    log(f"Tools: {tools_default}")
    log(f"Threads: {threads}  Memory: {memory_gb}GB")

    ercc_fa_path = (cfg_path.parent / ercc_fa).resolve()
    ercc_gtf_path = (cfg_path.parent / ercc_gtf).resolve()
    if with_ercc and not ercc_fa_path.exists():
        raise SystemExit(f"ERCC FASTA not found: {ercc_fa_path}")

    for g in cfg.get("genomes") or []:
        gid = g.get("id")
        if not gid:
            log("skip genome with missing id")
            continue
        fasta_src = g.get("fasta")
        if not fasta_src:
            log(f"skip {gid}: missing fasta")
            continue
        gtf_src = g.get("gtf")
        tools = g.get("tools") or tools_default

        genome_root = outdir / gid
        src_dir = genome_root / "src"
        ensure_dir(src_dir)

        fasta_staged = download_or_copy(fasta_src, normalize_path(src_dir, fasta_src), args.force)
        fasta_plain = decompress_if_needed(
            fasta_staged,
            src_dir / (fasta_staged.stem if fasta_staged.suffix == ".gz" else fasta_staged.name),
            args.force,
        )

        gtf_plain: Path | None = None
        if gtf_src:
            gtf_staged = download_or_copy(gtf_src, normalize_path(src_dir, gtf_src), args.force)
            gtf_plain = decompress_if_needed(
                gtf_staged,
                src_dir / (gtf_staged.stem if gtf_staged.suffix == ".gz" else gtf_staged.name),
                args.force,
            )

        log(f"== {gid} ==")
        build_indices(gid, fasta_plain, gtf_plain, genome_root, tools, threads, args.force)

        if with_ercc:
            ercc_root = outdir / f"{gid}_with_ERCC"
            ercc_src = ercc_root / "src"
            ensure_dir(ercc_src)
            ercc_fa_out = ercc_src / f"{gid}_with_ERCC.fa"
            concat_files([fasta_plain, ercc_fa_path], ercc_fa_out, args.force)
            ercc_gtf_out: Path | None = None
            if gtf_plain and ercc_gtf_path.exists():
                ercc_gtf_out = ercc_src / f"{gid}_with_ERCC.gtf"
                concat_files([gtf_plain, ercc_gtf_path], ercc_gtf_out, args.force)
            build_indices(gid + "_with_ERCC", ercc_fa_out, ercc_gtf_out, ercc_root, tools, threads, args.force)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
