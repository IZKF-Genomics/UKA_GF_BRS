#!/usr/bin/env python3
"""
ref_genomes helper: only file staging and ERCC concatenation.

Subcommands
- stage: download/copy inputs and normalize FASTA (prints key=value)
- ercc:  concatenate ERCC to FASTA (prints ERCC_FASTA=...)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _have(cmd: str) -> bool:
    from shutil import which

    return which(cmd) is not None


def _log(msg: str) -> None:
    sys.stderr.write(f"[runner] {msg}\n")
    sys.stderr.flush()


def _download_or_copy(src: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    force = str(os.environ.get("FORCE", "0")).lower() not in ("0", "false", "no")
    if dest.exists() and dest.stat().st_size > 0 and not force:
        _log(f"exists: {dest} (skip download)")
        return dest
    if src.startswith("http://") or src.startswith("https://"):
        _log(f"download: {src} -> {dest}")
        if _have("curl"):
            subprocess.check_call(["curl", "-L", "--fail", "--retry", "3", "-o", str(dest), src])
        else:
            subprocess.check_call(["wget", "-O", str(dest), src])
        return dest
    p = Path(src)
    if not p.exists():
        raise SystemExit(f"Source file does not exist: {src}")
    _log(f"stage: {src} -> {dest}")
    dest.write_bytes(p.read_bytes())
    return dest


def _decompress_to(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    force = str(os.environ.get("FORCE", "0")).lower() not in ("0", "false", "no")
    if dst.exists() and dst.stat().st_size > 0 and not force:
        _log(f"exists: {dst} (skip decompress)")
        return dst
    if str(src).endswith(".gz"):
        _log(f"decompress: {src.name} -> {dst.name}")
        import gzip

        with gzip.open(src, "rb") as f_in, open(dst, "wb") as f_out:
            f_out.write(f_in.read())
    else:
        dst.write_bytes(Path(src).read_bytes())
    return dst


def cmd_stage(args: argparse.Namespace) -> int:
    gid = args.gid
    outdir = Path(args.outdir).resolve()
    src_dir = outdir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    fasta_staged = _download_or_copy(args.fasta, src_dir / Path(args.fasta).name)
    fasta_plain = _decompress_to(
        fasta_staged,
        src_dir
        / (
            fasta_staged.stem
            if fasta_staged.suffix == ".gz"
            else fasta_staged.name
        ),
    )

    gtf_staged = ""
    gtf_plain = ""
    if args.gtf:
        gtf_staged_path = _download_or_copy(args.gtf, src_dir / Path(args.gtf).name)
        gtf_staged = str(gtf_staged_path)
        gtf_plain_path = _decompress_to(
            gtf_staged_path,
            src_dir
            / (
                gtf_staged_path.stem
                if gtf_staged_path.suffix == ".gz"
                else gtf_staged_path.name
            ),
        )
        gtf_plain = str(gtf_plain_path)

    print(f"FASTA_STAGED={fasta_staged}")
    print(f"GTF_STAGED={gtf_staged}")
    if gtf_plain:
        print(f"GTF_PLAIN={gtf_plain}")
    print(f"FASTA_PLAIN={fasta_plain}")
    return 0


def cmd_ercc(args: argparse.Namespace) -> int:
    gid = args.gid
    fasta_plain = Path(args.fasta_plain)
    outdir = Path(args.outdir)
    ercc_dir = Path(__file__).resolve().parent / "ERCC92"
    ercc_fa = ercc_dir / "ERCC92.fa"
    ercc_gtf = ercc_dir / "ERCC92.gtf"
    if not ercc_fa.exists():
        raise SystemExit(f"ERCC file missing: {ercc_fa}")
    out_fa = outdir / "src" / f"{gid}_with_ERCC.fa"
    with open(out_fa, "wb") as f_out:
        f_out.write(fasta_plain.read_bytes())
        f_out.write(ercc_fa.read_bytes())
    print(f"ERCC_FASTA={out_fa}")

    # If base GTF provided and ERCC GTF exists, concatenate to produce combined GTF
    if args.gtf:
        base_gtf = Path(args.gtf)
        if not base_gtf.exists():
            raise SystemExit(f"Base GTF not found: {base_gtf}")
        if not ercc_gtf.exists():
            raise SystemExit(f"ERCC GTF file missing: {ercc_gtf}")
        out_gtf = outdir / "src" / f"{gid}_with_ERCC.gtf"
        with open(out_gtf, "wb") as g_out:
            g_out.write(base_gtf.read_bytes())
            g_out.write(b"\n")
            g_out.write(ercc_gtf.read_bytes())
        print(f"ERCC_GTF={out_gtf}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="runner.py", description="ref_genomes helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_stage = sub.add_parser("stage", help="Stage FASTA/annotation and normalize FASTA")
    p_stage.add_argument("--gid", required=True)
    p_stage.add_argument("--fasta", required=True)
    p_stage.add_argument("--gtf")
    p_stage.add_argument("--outdir", required=True)
    p_stage.set_defaults(fun=cmd_stage)

    p_ercc = sub.add_parser("ercc", help="Concatenate ERCC to FASTA and print path")
    p_ercc.add_argument("--gid", required=True)
    p_ercc.add_argument("--fasta-plain", dest="fasta_plain", required=True)
    p_ercc.add_argument("--outdir", required=True)
    p_ercc.add_argument("--gtf", help="Optional base GTF to merge with ERCC annotations")
    p_ercc.set_defaults(fun=cmd_ercc)

    args = ap.parse_args(argv)
    return args.fun(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
