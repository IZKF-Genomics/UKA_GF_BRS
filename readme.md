# UKA_GF_BRS — Genomics Facility Templates

This repository is a Bioinformatics Resource Store (BRS) for the UKA Genomics Facility. It
contains reusable analysis templates designed to be rendered, run, and published with the
BPM CLI.

- BPM project: https://github.com/chaochungkuo/BPM
- BRS concept: organize your lab/facility templates in a single repo; render them into
  projects or in ad‑hoc output folders without changing your pipelines.

## Template: ref_genomes (ad‑hoc friendly)

Build reference genomes and indices (STAR, BWA, HISAT2, Salmon, etc.) using
`nf-core/references`. The template is optimized for ad‑hoc usage so you can maintain a
central reference tree such as `/data/genomes`.

### Requirements
- Nextflow installed and working with your preferred runtime (Docker/Singularity/Conda)
- Network access to download source FASTA/GTF files (or provide local paths)
- Optional: PyYAML for editing/rendering YAML (runner supports JSON as alternative)

Validate your setup once:
```
nextflow run nf-core/references -profile test
```

### Quick Start
1) Activate this BRS in BPM (optional if running purely ad‑hoc)
```
# Local path or Git URL
bpm resource add /path/to/UKA_GF_BRS --activate
# or
bpm resource add https://github.com/IZKF-Genomics/UKA_GF_BRS --activate
```

2) Render the template into your references root
```
bpm template render ref_genomes --out /data/genomes
```
This writes:
- `/data/genomes/run.sh` and `runner.py` (orchestration + helpers)
- `/data/genomes/genomes.yaml` (starter config)
- `/data/genomes/ERCC92/ERCC92.fa` and `ERCC92.gtf` (bundled)

3) Configure genomes in `genomes.yaml`
- Define `id`, `fasta` (URL or local path), optional `gtf`, optional `indices` (tools)
- Global `with_ercc: true` creates an additional `<id>_with_ERCC` genome using bundled ERCC

Example snippet:
```yaml
with_ercc: true

genomes:
  - id: GRCh38
    fasta: https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/GRCh38.primary_assembly.genome.fa.gz
    gtf:   https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/gencode.v49.primary_assembly.annotation.gtf.gz
    # omit indices to build all supported by default
  - id: GRCm39
    fasta: https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_mouse/release_M38/GRCm39.primary_assembly.genome.fa.gz
    gtf:   https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_mouse/release_M38/gencode.vM38.primary_assembly.annotation.gtf.gz
```

4) Run
```
cd /data/genomes
# All genomes
./run.sh --all
# Or select specific genomes
./run.sh --only GRCh38,GRCm39
```
The script prints the exact Nextflow command before running each build.

Environment overrides:
```
NXF_PROFILE=docker THREADS=32 MEM_GB=128 NF_REVISION=dev \
  NF_EXTRA_ARGS='-with-report -with-timeline' ./run.sh --only GRCh38
```

### Outputs
- Base genomes: `/data/genomes/<id>/indices/…`
- ERCC genomes: `/data/genomes/<id>_with_ERCC/indices/…`
- Staged sources under `/data/genomes/<id>/src/`
- The ERCC variant uses concatenated FASTA and a combined GTF (base + ERCC)

### Notes
- The top‑level `run.sh` keeps orchestration transparent (selection, datasheet creation,
  and printed commands). The heavy‑duty helpers live in `runner.py` and are invoked per
  step to keep the code readable and maintainable.
- You can also call `runner.py` subcommands directly for debugging (see `runner.py --help`).

