# UKA_GF_BRS — Genomics Facility Templates

This repository is a Bioinformatics Resource Store (BRS) for the UKA Genomics Facility. It
contains reusable analysis templates designed to be rendered, run, and published with the
BPM CLI.

- BPM project: https://github.com/chaochungkuo/BPM
- BRS concept: organize your lab/facility templates in a single repo; render them into
  projects or in ad-hoc output folders without changing your pipelines.

## Simple usage
1) Add the BRS and activate it
```
bpm resource add https://github.com/IZKF-Genomics/UKA_GF_BRS --activate
```

2) Discover templates and docs
```
bpm template list
bpm template readme <template_id>
```

3) Render a template
```
bpm template render <template_id> --dir /path/to/project
# or ad-hoc
bpm template render <template_id> --out /path/to/output
```

4) Run the rendered output (template-specific)
```
cd /path/to/output
./run.sh
```

## Templates
- demux_bclconvert: [templates/demux_bclconvert/README.md](templates/demux_bclconvert/README.md)
- dgea: [templates/dgea/README.md](templates/dgea/README.md)
- export: [templates/export/README.md](templates/export/README.md) (report_links-based mapping table; remote links supported, host prefixes allowed)
- hello_world: [templates/hello_world/README.md](templates/hello_world/README.md)
- illumina_methylation_process: [templates/illumina_methylation_process/README.md](templates/illumina_methylation_process/README.md)
- illumina_methylation_compare: [templates/illumina_methylation_compare/README.md](templates/illumina_methylation_compare/README.md)
- ercc: [templates/ercc/README.md](templates/ercc/README.md)
- nfcore_3mrnaseq: [templates/nfcore_3mrnaseq/README.md](templates/nfcore_3mrnaseq/README.md)
- nfcore_cutandrun: [templates/nfcore_cutandrun/README.md](templates/nfcore_cutandrun/README.md)
- nfcore_rnaseq: [templates/nfcore_rnaseq/README.md](templates/nfcore_rnaseq/README.md)
- nfcore_scrnaseq: [templates/nfcore_scrnaseq/README.md](templates/nfcore_scrnaseq/README.md)
- ref_genomes: [templates/ref_genomes/README.md](templates/ref_genomes/README.md)
- ref_genome_blacklists: [templates/ref_genome_blacklists/README.md](templates/ref_genome_blacklists/README.md)
- ref_10xgenomics: [templates/ref_10xgenomics/README.md](templates/ref_10xgenomics/README.md)
- scrnaseq_pipeline: [templates/scrnaseq_pipeline/README.md](templates/scrnaseq_pipeline/README.md)

## Workflows
- archive_cleanup: [workflows/archive_cleanup/README.md](workflows/archive_cleanup/README.md) (manifest-driven guarded deletion of source folders)
- archive_fastq: [workflows/archive_fastq/README.md](workflows/archive_fastq/README.md) (archive + verify + manifest generation for FASTQ runs)
- archive_rawdata: [workflows/archive_rawdata/README.md](workflows/archive_rawdata/README.md) (archive + verify + manifest generation; no source deletion)
- clean_fastq: [workflows/clean_fastq/README.md](workflows/clean_fastq/README.md) (pattern-based cleanup in /data/fastq without archiving)
- export_bcl: [workflows/export_bcl/README.md](workflows/export_bcl/README.md)
- export_demux: [workflows/export_demux/README.md](workflows/export_demux/README.md) (report_links-based spec)
- export_status: [workflows/export_status/README.md](workflows/export_status/README.md)
- hello_world: [workflows/hello_world/README.md](workflows/hello_world/README.md)
- keep_rules: [workflows/keep_rules/README.md](workflows/keep_rules/README.md) (manage keep-rules file with list/add/remove/prune actions)

## Docs
- Docs index: [docs/index.md](docs/index.md)
- Install BPM: [docs/install_bpm.md](docs/install_bpm.md)
- Add this BRS: [docs/add_brs.md](docs/add_brs.md)
- Update this BRS: [docs/update_brs.md](docs/update_brs.md)
- Archiving: [docs/archiving.md](docs/archiving.md)
- Keep rules: [docs/keep_rules.md](docs/keep_rules.md)
- Demultiplexing: [docs/demultiplexing.md](docs/demultiplexing.md)
- Basic analysis: [docs/basic_analysis.md](docs/basic_analysis.md)

## Conventions
- Project mode renders into `<project_dir>/<template_id>/` and updates `project.yaml`.
- Ad-hoc mode renders into the provided `--out` directory and writes `bpm.meta.yaml`.

## Notes
- demux_bclconvert samplesheet retrieval uses the flowcell endpoint when available and falls back to the Agendo request ID endpoint if no flowcell ID can be derived.
- nfcore_3mrnaseq and nfcore_rnaseq use `spikein` (string) to capture Agendo spike-in metadata; `_with_ERCC` is appended when the value contains `ERCC`.
- ercc template no longer uses a pre-render hook; provide `--salmon-dir`/`--samplesheet` directly.
- nfcore_3mrnaseq and nfcore_rnaseq no longer require `--genome` when Agendo provides an organism; the genome hook may fill it.
- dgea pixi environment now pins `r-rlang >= 1.1.7` to satisfy `dplyr` requirements.
- dgea pixi environment now pins `r-vctrs >= 0.7.1` to satisfy `dplyr` requirements.
- dgea pixi environment now pins `r-lifecycle >= 1.0.5` to satisfy `dplyr` requirements.
- export template now writes the final API response to `export_final_<job_id>.json`, storing only paths + summary fields in `project.yaml`.
- hooks.agendo:fetch and hooks.genome_from_organism:set_from_organism print the resolved or missing organism/umi/genome to guide manual overrides.
- archive_rawdata workflow supports `non_interactive=true` for cron-safe execution (`interactive=false`, `yes=true`) and now produces a manifest for external cleanup.
- archive_fastq workflow archives `/data/fastq` runs while always excluding `*.fastq.gz` and `*.fq.gz`; archive_cleanup then removes archived non-FASTQ content while preserving FASTQ files.
- archive_cleanup workflow consumes archive_rawdata/archive_fastq manifests and applies guarded source cleanup, suitable for sudo execution.
- archive_cleanup docs now include the recommended sudo command with `BPM_CACHE="$BPM_CACHE"` to avoid "No active BRS" under sudo.
- archive_rawdata, archive_fastq, archive_cleanup, and clean_fastq now default `manifest_dir` to `/data/shared/bpm_manifests`, so CLI examples can omit `--manifest-dir` unless overriding.
- archive_cleanup now resolves the latest manifest by file modification time across `archive_rawdata_*.json` and `archive_fastq_*.json` (not by filename ordering).
- export_demux workflow config now exposes `include_in_report`, `include_in_report_fastq`, and `include_in_report_multiqc` parameters used by the run script.
- clean_fastq workflow removes pattern-matched files/directories directly from `/data/fastq` without archiving, with retention and manifest logging.
- keep_rules workflow manages `/data/shared/bpm_manifests/keep_rules.yaml`, including `prune` to remove stale run entries no longer present in source roots.
- keep_rules now defaults to a keyboard TUI for bulk keep/unkeep management (`Space` toggle, `u` keep_until, `s` save) with browse root `/data/fastq`.
- illumina_methylation_compare now supports registry-driven multi-run input management (`config/input_registry.csv`), strict upstream object path resolution, group harmonization via `config/group_map.csv`, and `pixi run sync-samples` for rebuilding compare sample sheets from enabled process runs.

## Agent Readability

To keep this BRS easy for `bpm agent` to interpret:

- Each template/workflow `README.md` includes an `Agent Metadata` block (YAML).
- Keep descriptor files (`template_config.yaml`, `workflow_config.yaml`) aligned with README text.
- Prefer explicit parameter descriptions and concrete command examples.
- Document required inputs and expected outputs in README files.
