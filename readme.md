# UKA_GF_BRS — Genomics Facility Templates

Version: `2026.03.23`

This repository is a Bioinformatics Resource Store (BRS) for the UKA Genomics Facility. It contains reusable analysis templates and operational workflows designed to be rendered, run, and documented through BPM.

- BPM project: https://github.com/chaochungkuo/BPM
- Main documentation entry point: [docs/index.md](docs/index.md)

## Simple Usage
1. Add the BRS and activate it
```bash
bpm resource add https://github.com/IZKF-Genomics/UKA_GF_BRS --activate
```

2. Discover templates, workflows, and docs
```bash
bpm template list
bpm workflow list
bpm template readme <template_id>
bpm workflow readme <workflow_id>
```

3. Render a template
```bash
bpm template render <template_id> --dir /path/to/project
# or ad-hoc
bpm template render <template_id> --out /path/to/output
```

4. Run the rendered output when the template provides an executable entrypoint
```bash
cd /path/to/output
./run.sh
```

## Start Here
- Setup and installation: [docs/index.md](docs/index.md)
- Archiving and retention handling: [docs/archiving.md](docs/archiving.md)
- Keep-rules behavior inside archive workflows: [docs/keep_rules.md](docs/keep_rules.md)
- Demultiplexing: [docs/demultiplexing.md](docs/demultiplexing.md)
- Basic analysis templates: [docs/basic_analysis.md](docs/basic_analysis.md)
- Single-cell analysis planning: [docs/single_cell_analysis.md](docs/single_cell_analysis.md)

## Templates
- contamination_db: [templates/contamination_db/README.md](templates/contamination_db/README.md)
- demux_bclconvert: [templates/demux_bclconvert/README.md](templates/demux_bclconvert/README.md)
- dgea: [templates/dgea/README.md](templates/dgea/README.md)
- export: [templates/export/README.md](templates/export/README.md)
- hello_world: [templates/hello_world/README.md](templates/hello_world/README.md)
- illumina_methylation_process: [templates/illumina_methylation_process/README.md](templates/illumina_methylation_process/README.md)
- illumina_methylation_compare: [templates/illumina_methylation_compare/README.md](templates/illumina_methylation_compare/README.md)
- ercc: [templates/ercc/README.md](templates/ercc/README.md)
- cellbender_remove_background: [templates/cellbender_remove_background/README.md](templates/cellbender_remove_background/README.md)
- nfcore_3mrnaseq: [templates/nfcore_3mrnaseq/README.md](templates/nfcore_3mrnaseq/README.md)
- nfcore_cutandrun: [templates/nfcore_cutandrun/README.md](templates/nfcore_cutandrun/README.md)
- nfcore_rnaseq: [templates/nfcore_rnaseq/README.md](templates/nfcore_rnaseq/README.md)
- nfcore_scrnaseq: [templates/nfcore_scrnaseq/README.md](templates/nfcore_scrnaseq/README.md)
- ref_genomes: [templates/ref_genomes/README.md](templates/ref_genomes/README.md)
- ref_genome_blacklists: [templates/ref_genome_blacklists/README.md](templates/ref_genome_blacklists/README.md)
- ref_10xgenomics: [templates/ref_10xgenomics/README.md](templates/ref_10xgenomics/README.md)
- scverse_scrna_prep: [templates/scverse_scrna_prep/README.md](templates/scverse_scrna_prep/README.md)
- scrnaseq_pipeline: [templates/scrnaseq_pipeline/README.md](templates/scrnaseq_pipeline/README.md)

## User-Facing Workflows
- archive_raw: [workflows/archive_raw/README.md](workflows/archive_raw/README.md)
- archive_fastq: [workflows/archive_fastq/README.md](workflows/archive_fastq/README.md)
- archive_projects: [workflows/archive_projects/README.md](workflows/archive_projects/README.md)
- export_bcl: [workflows/export_bcl/README.md](workflows/export_bcl/README.md)
- export_demux: [workflows/export_demux/README.md](workflows/export_demux/README.md)
- export_status: [workflows/export_status/README.md](workflows/export_status/README.md)
- hello_world: [workflows/hello_world/README.md](workflows/hello_world/README.md)

## Documentation
- Docs index: [docs/index.md](docs/index.md)
- Install BPM: [docs/install_bpm.md](docs/install_bpm.md)
- Add this BRS: [docs/add_brs.md](docs/add_brs.md)
- Update this BRS: [docs/update_brs.md](docs/update_brs.md)
- Archiving: [docs/archiving.md](docs/archiving.md)
- Keep rules: [docs/keep_rules.md](docs/keep_rules.md)
- Demultiplexing: [docs/demultiplexing.md](docs/demultiplexing.md)
- Basic analysis: [docs/basic_analysis.md](docs/basic_analysis.md)
- Single-cell analysis plan: [docs/single_cell_analysis.md](docs/single_cell_analysis.md)
- Shared contamination database builder: [templates/contamination_db/README.md](templates/contamination_db/README.md)

## Archiving Model
- `archive_raw` is archive-only: discover, review, keep/unkeep, copy, verify, manifest/log.
- `archive_fastq` is archive plus source removal: discover, review, keep/unkeep, copy, verify, then remove the source run directory.
- `archive_projects` follows the same archive-plus-removal model for `/data/projects`, with project-specific archive excludes.
- Keep rules are edited inside the archive TUIs and stored in `/data/shared/bpm_manifests/keep_rules.yaml`.
- `archive_fastq` supports cleanup-only reruns for already-archived FASTQ-only or empty source folders when the target archive already exists.

## Conventions
- Project mode renders into `<project_dir>/<template_id>/` and updates `project.yaml`.
- Ad-hoc mode renders into the provided `--out` directory and writes `bpm.meta.yaml`.
- Template and workflow READMEs are the authoritative usage reference for parameters, defaults, inputs, and outputs.

## Notes
- demux_bclconvert samplesheet retrieval uses the flowcell endpoint when available and falls back to the Agendo request ID endpoint if no flowcell ID can be derived.
- nfcore_3mrnaseq and nfcore_rnaseq use `spikein` to capture Agendo spike-in metadata; `_with_ERCC` is appended when the value contains `ERCC`.
- ercc no longer uses a pre-render hook; provide `--salmon-dir` and `--samplesheet` directly.
- export writes the final API response to `export_final_<job_id>.json`, storing only paths and summary fields in `project.yaml`.
- illumina_methylation_compare supports registry-driven multi-run input management and multi-comparison execution.
- nfcore_scrnaseq publishes `nfcore_scrnaseq_res_mt` for downstream single-cell templates.
- cellbender_remove_background publishes `cellbender_corrected_matrix`.
- scverse_scrna_prep prefers `cellbender_corrected_matrix` when available and otherwise resolves `nfcore_scrnaseq_res_mt`.

## Agent Readability
- Each template or workflow `README.md` includes an `Agent Metadata` block.
- Keep `template_config.yaml` and `workflow_config.yaml` aligned with README text.
- Prefer explicit parameter descriptions and concrete command examples.
- Document required inputs and expected outputs in README files.
