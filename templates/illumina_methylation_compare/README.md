# illumina_methylation_compare


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: illumina_methylation_compare
kind: template
description: Illumina methylation array comparison analysis (DMP/DMR/enrichment/drilldown)
  from preprocessed inputs.
descriptor: templates/illumina_methylation_compare/template_config.yaml
required_params: []
optional_params:
- array_type
- authors
- case_label
- control_label
- genome_build
- group_col
- process_results_dir
- study_name
cli_flags:
  study_name: --study-name
  authors: --authors
  array_type: --array-type
  genome_build: --genome-build
  process_results_dir: --process-results-dir
  group_col: --group-col
  case_label: --case
  control_label: --control
run_entry: run.sh
publish_keys: []
render_file_count: 14
```
<!-- AGENT_METADATA_END -->

Comparison template for Illumina methylation arrays.

Scope:
- 01 DMP
- 02 DMR (scaffold)
- 03 enrichment
- 04 drilldown

Input expectation:
- One or more upstream process runs listed in `config/input_runs.csv`.
- Each run points to a `results/rds` directory containing one of:
  `adjustedset.rds`, `filteredset.rds`, `normset.rds`, or `rgset.rds`.

Typical workflow:
1. Run `illumina_methylation_process` first.
2. Edit `config/input_runs.csv` to choose which runs and samples to include.
3. Edit `config/samples.csv` for metadata and grouping.
4. Run this compare template.

## Multi-run input selection

`config/input_runs.csv` columns:
- `run_id`: short label for this input run.
- `processed_results_dir`: path to a process run `results/rds` folder.
- `array_type`: optional per-run array type (`450K`, `EPIC`, `EPIC_V2`) for mixed-array enrichment handling.
- `enabled`: `true`/`false`.
- `include_samples`: optional comma/semicolon-separated sample IDs to keep.
- `exclude_samples`: optional comma/semicolon-separated sample IDs to drop.

Notes:
- By default, only sample IDs present in `config/samples.csv` are used (`input.require_samples_in_sheet = true`).
- If multiple runs are enabled, probes are merged by intersection of CpG IDs.
- Mixed `450K` + `EPIC/EPIC_V2` is supported by probe intersection; enrichment auto-selects a compatible mapping (`450K` when 450K is present).
- `sample_id` must be globally unique across all enabled runs.

## Render

```bash
bpm template render illumina_methylation_compare \
  --param study_name=MyStudyCompare \
  --param process_results_dir=../illumina_methylation_process/results/rds \
  --param array_type=AUTO \
  --param group_col=group \
  --param case_label=HPNST \
  --param control_label=HPNST-SC \
  --dir /path/to/project
```

After render, adjust:
- `config/input_runs.csv` to combine runs / filter samples.
- `config/project.toml` to tune analysis parameters (`dmp`, `dmr`, `enrichment`, `drilldown`).

Example multi-run setup:

```csv
run_id,processed_results_dir,array_type,enabled,include_samples,exclude_samples
process_450k,../process_450k/results/rds,450K,true,,
process_epic_geo_schwannoma_core_n50,../process_epic_geo_schwannoma_core_n50/results/rds,EPIC,true,,
process_epic_internal_tumor_panel_n37,../process_epic_internal_tumor_panel_n37/results/rds,EPIC,true,,
process_epic_mini_mixed_n6,../process_epic_mini_mixed_n6/results/rds,EPIC,true,,
```

## Run

```bash
bpm template run illumina_methylation_compare --dir /path/to/project
# or inside rendered folder
./run.sh
```
