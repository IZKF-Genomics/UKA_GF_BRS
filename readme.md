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
- export_bcl: [workflows/export_bcl/README.md](workflows/export_bcl/README.md)
- export_demux: [workflows/export_demux/README.md](workflows/export_demux/README.md) (report_links-based spec)
- export_status: [workflows/export_status/README.md](workflows/export_status/README.md)
- hello_world: [workflows/hello_world/README.md](workflows/hello_world/README.md)

## Docs
- Install BPM: [docs/install_bpm.md](docs/install_bpm.md)
- Add this BRS: [docs/add_brs.md](docs/add_brs.md)
- Update this BRS: [docs/update_brs.md](docs/update_brs.md)
- Demultiplexing: [docs/demultiplexing.md](docs/demultiplexing.md)
- Basic analysis: [docs/basic_analysis.md](docs/basic_analysis.md)

## Conventions
- Project mode renders into `<project_dir>/<template_id>/` and updates `project.yaml`.
- Ad-hoc mode renders into the provided `--out` directory and writes `bpm.meta.yaml`.
