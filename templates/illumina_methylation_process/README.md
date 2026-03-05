# illumina_methylation_process


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: illumina_methylation_process
kind: template
description: Illumina methylation array preprocessing + clustering (Quarto + Pixi
  + R/Bioconductor).
descriptor: templates/illumina_methylation_process/template_config.yaml
required_params: []
optional_params:
- array_type
- authors
- genome_build
- group_col
- idat_base_dir
- study_name
cli_flags:
  study_name: --study-name
  authors: --authors
  idat_base_dir: --idat-base-dir
  array_type: --array-type
  genome_build: --genome-build
  group_col: --group-col
run_entry: run.sh
publish_keys: []
render_file_count: 8
```
<!-- AGENT_METADATA_END -->

Preprocessing + clustering template for Illumina methylation arrays.

Scope:
- 01 load IDAT
- 02 QC
- 03 normalization
- 04 filtering
- 05 batch/cell adjustments
- 06 clustering

This template is intentionally comparison-free (no DMP/DMR/enrichment/drilldown).
Use `illumina_methylation_compare` for downstream case-control analyses.

## Render

```bash
bpm template render illumina_methylation_process \
  --param study_name=MyStudy \
  --param authors="Your Name" \
  --param idat_base_dir=data/idat \
  --param array_type=EPIC_V2 \
  --dir /path/to/project
```

## Run

```bash
bpm template run illumina_methylation_process --dir /path/to/project
# or inside rendered folder
./run.sh
```
