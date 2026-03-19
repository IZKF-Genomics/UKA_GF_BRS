#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SpeciesEntry:
    label: str
    taxid: int
    fasta_url: str
    fastq_screen_label: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build shared contamination databases.")
    parser.add_argument("--config", required=True, help="Path to contamination_db.yaml")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise SystemExit("Configuration file must contain a YAML mapping.")
    return data


def require(value: Any, message: str) -> Any:
    if value in (None, "", []):
        raise SystemExit(message)
    return value


def as_species(entries: list[dict[str, Any]]) -> list[SpeciesEntry]:
    species: list[SpeciesEntry] = []
    for raw in entries:
        if not raw or not raw.get("enabled", True):
            continue
        label = str(require(raw.get("label"), "Each enabled species needs a label.")).strip()
        fasta_url = str(require(raw.get("fasta_url"), f"Species '{label}' is missing fasta_url.")).strip()
        taxid = int(require(raw.get("taxid"), f"Species '{label}' is missing taxid."))
        fastq_screen_label = str(raw.get("fastq_screen_label") or label).strip()
        species.append(SpeciesEntry(label=label, taxid=taxid, fasta_url=fasta_url, fastq_screen_label=fastq_screen_label))
    if not species:
        raise SystemExit("No enabled species configured. Edit contamination_db.yaml and add at least one FASTA source.")
    return species


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def ensure_empty_or_force(path: Path, force: bool) -> None:
    if path.exists():
        if not force:
            raise SystemExit(f"Refusing to overwrite existing directory without force=true: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dest: Path) -> None:
    print(f"Downloading           : {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out)


def decompress_if_needed(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if src.suffix == ".gz":
        out = dest_dir / src.with_suffix("").name
        with gzip.open(src, "rb") as fin, out.open("wb") as fout:
            shutil.copyfileobj(fin, fout)
        return out
    out = dest_dir / src.name
    shutil.copy2(src, out)
    return out


def normalize_kraken_headers(src: Path, dest: Path, taxid: int, label: str) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    seq_count = 0
    with src.open("r", encoding="utf-8", errors="replace") as fin, dest.open("w", encoding="utf-8") as fout:
        for line in fin:
            if line.startswith(">"):
                seq_count += 1
                header = line[1:].strip().split()[0]
                fout.write(f">{label}_{seq_count}|kraken:taxid|{taxid}|{header}\n")
            else:
                fout.write(line)
    return seq_count


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "label",
            "taxid",
            "fasta_url",
            "downloaded_file",
            "extracted_fasta",
            "normalized_fasta",
            "fastq_screen_label",
            "sequence_count",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def update_current_symlink(version_dir: Path) -> None:
    current = version_dir.parent / "current"
    if current.is_symlink() or current.exists():
        current.unlink()
    current.symlink_to(version_dir.name)


def write_fastq_screen_conf(conf_path: Path, manifest_rows: list[dict[str, Any]], indexes_root: Path) -> None:
    lines = [
        "# Auto-generated FastQ Screen configuration",
        "THREADS 1",
        "",
    ]
    for row in manifest_rows:
        label = row["fastq_screen_label"]
        index_prefix = indexes_root / row["label"] / row["label"]
        lines.append(f"DATABASE\t{label}\t{index_prefix}\tBOWTIE2")
    conf_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).resolve()
    cfg = load_config(config_path)

    panel_name = str(require(cfg.get("panel_name"), "panel_name is required"))
    db_version = str(require(cfg.get("db_version"), "db_version is required"))
    force = bool(cfg.get("force", False))
    cleanup = bool(cfg.get("cleanup_staging", True))
    threads = int(cfg.get("threads", 1))
    kraken2_base = str(cfg.get("kraken2_base", "standard")).strip().lower()
    build_cfg = cfg.get("build", {}) or {}
    paths_cfg = cfg.get("paths", {}) or {}
    bracken_cfg = cfg.get("bracken", {}) or {}

    species = as_species(cfg.get("species", []) or [])

    root_dir = Path(str(cfg.get("root_dir", "."))).resolve()
    kraken_root = Path(str(paths_cfg.get("kraken2_root", root_dir / "kraken2"))).resolve()
    bracken_root = Path(str(paths_cfg.get("bracken_root", root_dir / "bracken"))).resolve()
    fastq_screen_root = Path(str(paths_cfg.get("fastq_screen_root", root_dir / "fastq_screen"))).resolve()

    results_dir = config_path.parent / "results"
    work_dir = config_path.parent / "work" / panel_name / db_version
    downloads_dir = work_dir / "downloads"
    extracted_dir = work_dir / "extracted_fastas"
    normalized_dir = work_dir / "normalized_fastas"

    kraken_dir = kraken_root / panel_name / db_version
    bracken_dir = bracken_root / panel_name / db_version
    fastq_screen_dir = fastq_screen_root / panel_name / db_version

    if build_cfg.get("kraken2", True):
        ensure_empty_or_force(kraken_dir, force)
    if build_cfg.get("bracken", True):
        ensure_empty_or_force(bracken_dir, force)
    if build_cfg.get("fastq_screen", True):
        ensure_empty_or_force(fastq_screen_dir, force)

    downloads_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, Any]] = []
    for entry in species:
        filename = Path(entry.fasta_url.split("?")[0]).name or f"{entry.label}.fa.gz"
        downloaded = downloads_dir / filename
        extracted = extracted_dir / (downloaded.stem if downloaded.suffix == ".gz" else downloaded.name)
        normalized = normalized_dir / f"{entry.label}.fa"

        download_file(entry.fasta_url, downloaded)
        extracted = decompress_if_needed(downloaded, extracted_dir)
        seq_count = normalize_kraken_headers(extracted, normalized, entry.taxid, entry.label)
        manifest_rows.append(
            {
                "label": entry.label,
                "taxid": entry.taxid,
                "fasta_url": entry.fasta_url,
                "downloaded_file": str(downloaded),
                "extracted_fasta": str(extracted),
                "normalized_fasta": str(normalized),
                "fastq_screen_label": entry.fastq_screen_label,
                "sequence_count": seq_count,
            }
        )

    manifest_path = results_dir / "genome_manifest_resolved.csv"
    write_manifest(manifest_path, manifest_rows)

    if build_cfg.get("kraken2", True):
        print(f"Building Kraken2 DB   : {kraken_dir}")
        if kraken2_base == "standard":
            run(["kraken2-build", "--standard", "--threads", str(max(1, threads)), "--db", str(kraken_dir)])
        elif kraken2_base == "none":
            run(["kraken2-build", "--download-taxonomy", "--db", str(kraken_dir)])
        else:
            raise SystemExit(f"Unsupported kraken2_base: {kraken2_base}. Use 'standard' or 'none'.")
        for row in manifest_rows:
            run(["kraken2-build", "--add-to-library", row["normalized_fasta"], "--db", str(kraken_dir)])
        run(["kraken2-build", "--build", "--threads", str(max(1, threads)), "--db", str(kraken_dir)])
        update_current_symlink(kraken_dir)

    read_lengths = [int(x) for x in bracken_cfg.get("read_lengths", [])]
    if build_cfg.get("bracken", True):
        if not build_cfg.get("kraken2", True) and not kraken_dir.exists():
            raise SystemExit("Bracken build requested but Kraken2 DB does not exist.")
        for length in read_lengths:
            print(f"Building Bracken      : readlen={length}")
            run(["bracken-build", "-d", str(kraken_dir), "-t", str(max(1, threads)), "-l", str(length)])
            readlen_dir = bracken_dir / f"readlen_{length}"
            readlen_dir.mkdir(parents=True, exist_ok=True)
            for name in [f"database{length}mers.kmer_distrib", "database100mers.kraken", "database.kraken"]:
                source = kraken_dir / name
                if source.exists():
                    target = readlen_dir / source.name
                    if target.exists() or target.is_symlink():
                        target.unlink()
                    target.symlink_to(source)
            link = readlen_dir / "kraken_db"
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(kraken_dir)
        update_current_symlink(bracken_dir)

    if build_cfg.get("fastq_screen", True):
        print(f"Building FastQ Screen : {fastq_screen_dir}")
        indexes_root = fastq_screen_dir / "indexes"
        for row in manifest_rows:
            prefix_dir = indexes_root / row["label"]
            prefix_dir.mkdir(parents=True, exist_ok=True)
            prefix = prefix_dir / row["label"]
            run(["bowtie2-build", row["extracted_fasta"], str(prefix)])
        write_fastq_screen_conf(fastq_screen_dir / "fastq_screen.conf", manifest_rows, indexes_root)
        update_current_symlink(fastq_screen_dir)

    build_info = {
        "panel_name": panel_name,
        "db_version": db_version,
        "threads": threads,
        "cleanup_staging": cleanup,
        "kraken2_base": kraken2_base,
        "paths": {
            "kraken2": str(kraken_dir),
            "bracken": str(bracken_dir),
            "fastq_screen": str(fastq_screen_dir),
        },
        "bracken_read_lengths": read_lengths,
        "species_count": len(manifest_rows),
        "species": [
            {
                "label": row["label"],
                "taxid": row["taxid"],
                "fasta_url": row["fasta_url"],
                "sequence_count": row["sequence_count"],
            }
            for row in manifest_rows
        ],
    }
    write_yaml(results_dir / "db_build_info.yaml", build_info)

    if cleanup:
        shutil.rmtree(work_dir, ignore_errors=True)

    print("Resolved manifest     :", manifest_path)
    print("Build metadata        :", results_dir / "db_build_info.yaml")


if __name__ == "__main__":
    main()
