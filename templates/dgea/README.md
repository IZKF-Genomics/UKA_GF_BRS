# dgea


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: dgea
kind: template
description: Differential gene expression analysis (DGEA).
descriptor: templates/dgea/template_config.yaml
source_of_truth:
- templates/dgea/run.sh.j2
- templates/dgea/template_config.yaml
methods_file: templates/dgea/METHODS.md
citations_file: templates/dgea/citations.yaml
bibliography_file: templates/dgea/references.bib
required_params: []
optional_params:
- application
- authors
- name
- nfcore_samplesheet
- organism
- salmon_dir
- spikein
cli_flags:
  salmon_dir: --salmon-dir
  nfcore_samplesheet: --samplesheet
  organism: --organism
  spikein: --spikein
  application: --application
  name: --name
  authors: --authors
run_entry: run.sh
publish_keys: []
software_version_capture:
  run_info: results/run_info.yaml
  commands:
  - pixi --version
  - quarto --version
  - pixi run Rscript -e packageVersion(...)
render_file_count: 15
```
<!-- AGENT_METADATA_END -->

Differential gene expression analysis (DGEA).

## Inputs
- Salmon quant directory (from nfcore_rnaseq or nfcore_3mrnaseq).
- nf-core samplesheet CSV with a `sample` column; the constructor splits sample IDs
  on `_` into `group` and `id`.

## Render
Run from the project directory (where project.yaml lives).
```
bpm template render dgea \
  --salmon-dir /path/to/quant \
  --samplesheet /path/to/samplesheet.csv \
  --organism hsapiens \
  --application nfcore_RNAseq \
  --name PROJECT_NAME \
  --authors "Author One, Author Two"
```

## Customize comparisons
Edit `DGEA_constructor.R` in the rendered folder and set:
- `report_config$base_group`
- `report_config$target_group`
- Optional `design_formula`, `paired`, `go`, `gsea`, and cutoffs

## Optional reports
Additional reports are shipped and can be enabled by uncommenting the render
blocks in `DGEA_constructor.R`:
- Correlation analysis (`DGEA_correlation_analysis.qmd`)
- Geneset comparisons (`DGEA_Geneset_Comparisons.qmd`)
- Integrated heatmap (`DGEA_integrated_heatmap.qmd`)
- Simple comparison (`SimpleComparison_template.qmd`)

## Run
```
bpm template run dgea --dir /path/to/project
```

Run metadata and version provenance are written to `results/run_info.yaml`.

## Environment
If you use Pixi, the template ships a `pixi.toml` with all R/Quarto dependencies.

## Methods and Citations
- Publication-grade methods text: `METHODS.md`.
- Machine-readable citation source for BPM agent: `citations.yaml`.
- Manuscript bibliography source (Quarto/Pandoc): `references.bib`.

## Parameters
- `--salmon-dir`: Path to Salmon quant output (from nfcore_rnaseq or nfcore_3mrnaseq).
- `--samplesheet`: Path to nf-core samplesheet CSV containing a `sample` column.
- `--organism`: One of `hsapiens`, `mmusculus`, `rnorvegicus`.
- `--spikein`: Spike-in description string; ERCC filtering is enabled when it contains `ERCC`.
- `--application`: `RNAseq` or `3mRNAseq` to select count handling.
- `--name`: Project name for the report header.
- `--authors`: Comma-separated author names for the report header.

See `template_config.yaml` for defaults and optional behavior.
