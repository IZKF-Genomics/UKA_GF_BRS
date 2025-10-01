#!/usr/bin/env python3
"""
ref_genomes Python helper with subcommands used by run.sh for transparency.

Subcommands
- list:     parse config and list genomes (TSV) + WITH_ERCC
- stage:    download/copy inputs and normalize FASTA (prints key=value)
- ercc:     concatenate ERCC to FASTA (prints ERCC_FASTA=...)
- tools:    split indices into aligners vs transcriptome (prints key=value)
- datasheet:create datasheet.yml for a genome (prints DATASHEET=...)
- nf-cmd:   print the full Nextflow command that would run (CMD=...)
- nf-run:   run Nextflow with streaming output (prints CMD: ... first)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


def _have(cmd: str) -> bool:
    from shutil import which

    return which(cmd) is not None


def _log(msg: str) -> None:
    sys.stderr.write(f"[runner] {msg}\n")
    sys.stderr.flush()


def _load_config(path: Path) -> Dict[str, Any]:
    if path.suffix == ".json":
        return json.loads(path.read_text())
    try:
        import yaml  # type: ignore

        return yaml.safe_load(path.read_text()) or {}
    except Exception as e:
        raise SystemExit(f"Failed to parse config at {path}: {e}. Install PyYAML or provide JSON.")


def _conf_from_cfg(cfg: Dict[str, Any]) -> Dict[str, str]:
    nf = cfg.get("nfcore") or {}
    return {
        "NF_PIPELINE": str(nf.get("pipeline") or "nf-core/references"),
        "NF_REVISION": str(nf.get("revision") or "dev"),
        "NXF_PROFILE": str(nf.get("profile") or "docker"),
        "NF_EXTRA_ARGS": str(nf.get("extra_args") or ""),
        "TOOLS": str(nf.get("tools") or ""),
    }


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


def _split_tools(tools_csv: str) -> Tuple[str, str]:
    tools = [t.strip() for t in (tools_csv or "").split(",") if t.strip()]
    if not tools:
        return "star,bwa,bwamem2,bowtie2,hisat2,minimap2", "salmon,kallisto"
    aligners = [t for t in tools if t not in ("salmon", "kallisto")]
    tx = [t for t in tools if t in ("salmon", "kallisto")]
    return ",".join(aligners), ",".join(tx)


def _env_defaults() -> Dict[str, str]:
    return {
        "THREADS": os.environ.get("THREADS", "16"),
        "MEM_GB": os.environ.get("MEM_GB", "64"),
        "NXF_PROFILE": os.environ.get("NXF_PROFILE", "docker"),
        "NF_PIPELINE": os.environ.get("NF_PIPELINE", "nf-core/references"),
        "NF_REVISION": os.environ.get("NF_REVISION", "dev"),
        "NF_EXTRA_ARGS": os.environ.get("NF_EXTRA_ARGS", ""),
        "RESUME": os.environ.get("RESUME", "1"),
    }


def cmd_list(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config or os.environ.get("CFG_PATH", "genomes.yaml"))
    if not cfg_path.exists():
        raise SystemExit(f"Config not found: {cfg_path}")
    cfg = _load_config(cfg_path)
    with_ercc = cfg.get("with_ercc", True)
    print(f"WITH_ERCC\t{with_ercc}")
    for g in (cfg.get("genomes") or []):
        gid = g.get("id") or ""
        fasta = g.get("fasta") or ""
        gtf = g.get("gtf") or ""
        indices = ",".join(g.get("indices") or [])
        ercc = g.get("ercc")
        ercc_s = "" if ercc is None else ("true" if ercc else "false")
        print(f"GENOME\t{gid}\t{fasta}\t{gtf}\t{indices}\t{ercc_s}")
    return 0


def cmd_conf(args: argparse.Namespace) -> int:
    cfg_path = Path(args.config or os.environ.get("CFG_PATH", "genomes.yaml"))
    if not cfg_path.exists():
        raise SystemExit(f"Config not found: {cfg_path}")
    cfg = _load_config(cfg_path)
    conf = _conf_from_cfg(cfg)
    for k, v in conf.items():
        print(f"{k}={v}")
    return 0


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


def cmd_tools(args: argparse.Namespace) -> int:
    aligners, tx = _split_tools(args.indices or "")
    print(f"ALIGNERS={aligners}")
    print(f"TX={tx}")
    return 0


def cmd_datasheet(args: argparse.Namespace) -> int:
    gid = args.gid
    species = args.species or gid
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"- genome: \"{gid}\"\n", f"  species: \"{species}\"\n", f"  fasta: \"{args.fasta}\"\n"]
    if args.gtf:
        lines.append(f"  gtf: \"{args.gtf}\"\n")
    out.write_text("".join(lines))
    print(f"DATASHEET={out}")
    return 0


def _build_nf_cmd(datasheet: Path, outdir: Path, aligners: str, tx: str, env: Dict[str, str]) -> str:
    cmd = [
        "nextflow",
        "run",
        env.get("NF_PIPELINE", "nf-core/references"),
        "-r",
        env.get("NF_REVISION", "dev"),
        "-profile",
        env.get("NXF_PROFILE", "docker"),
        "--input",
        str(datasheet),
        "--outdir",
        str(outdir),
        "--max_cpus",
        env.get("THREADS", "16"),
        "--max_memory",
        f"{env.get('MEM_GB', '64')}GB",
        "-work-dir",
        str(outdir / "work"),
    ]
    if aligners:
        cmd += ["--aligners", aligners]
    if tx:
        cmd += ["--transcriptome_aligners", tx]
    if env.get("RESUME") and str(env["RESUME"]).lower() not in ("0", "false", "no"):
        cmd += ["-resume"]
    extra = env.get("NF_EXTRA_ARGS", "").strip()
    if extra:
        cmd += extra.split()
    return " ".join(cmd)


def cmd_nf_cmd(args: argparse.Namespace) -> int:
    env = _env_defaults()
    cmd = _build_nf_cmd(Path(args.datasheet), Path(args.outdir), args.aligners or "", args.tx or "", env)
    print(f"CMD={cmd}")
    return 0


def cmd_nf_run(args: argparse.Namespace) -> int:
    env = _env_defaults()
    cmd = _build_nf_cmd(Path(args.datasheet), Path(args.outdir), args.aligners or "", args.tx or "", env)
    print(f"CMD: {cmd}")
    rc = subprocess.call(cmd, shell=True, env={**os.environ, **env})
    if rc != 0:
        raise SystemExit(rc)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="runner.py", description="ref_genomes helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List genomes from config as TSV")
    p_list.add_argument("--config", help="Path to genomes.yaml/json")
    p_list.set_defaults(fun=cmd_list)

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

    p_tools = sub.add_parser("tools", help="Split indices CSV into aligners/tx")
    p_tools.add_argument("--indices", default="")
    p_tools.set_defaults(fun=cmd_tools)

    p_ds = sub.add_parser("datasheet", help="Create datasheet.yml for a genome")
    p_ds.add_argument("--gid", required=True)
    p_ds.add_argument("--fasta", required=True)
    p_ds.add_argument("--gtf")
    p_ds.add_argument("--out", required=True)
    p_ds.add_argument("--species")
    p_ds.set_defaults(fun=cmd_datasheet)

    p_cmd = sub.add_parser("nf-cmd", help="Print Nextflow command")
    p_cmd.add_argument("--datasheet", required=True)
    p_cmd.add_argument("--outdir", required=True)
    p_cmd.add_argument("--aligners")
    p_cmd.add_argument("--tx")
    p_cmd.set_defaults(fun=cmd_nf_cmd)

    p_run = sub.add_parser("nf-run", help="Run Nextflow with streaming logs")
    p_run.add_argument("--datasheet", required=True)
    p_run.add_argument("--outdir", required=True)
    p_run.add_argument("--aligners")
    p_run.add_argument("--tx")
    p_run.set_defaults(fun=cmd_nf_run)

    args = ap.parse_args(argv)
    return args.fun(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
    p_conf = sub.add_parser("conf", help="Print nf-core configuration derived from config file")
    p_conf.add_argument("--config", help="Path to genomes.yaml/json")
    p_conf.set_defaults(fun=cmd_conf)
