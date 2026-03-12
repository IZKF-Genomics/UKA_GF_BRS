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
- auto_discover_inputs
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
  auto_discover_inputs: --auto-discover-inputs
  genome_build: --genome-build
  process_results_dir: --process-results-dir
  group_col: --group-col
  case_label: --case
  control_label: --control
run_entry: run.sh
publish_keys: []
render_file_count: 16
```
<!-- AGENT_METADATA_END -->

Comparison template for Illumina methylation arrays.

Scope:
- 01 DMP
- 02 DMR (scaffold)
- 03 enrichment
- 04 drilldown

Input expectation:
- One or more upstream process runs listed in `config/input_registry.csv` (preferred) or `config/input_runs.csv` (legacy/simple).
- Each run points to a `results/rds` directory containing one of:
  `adjustedset.rds`, `filteredset.rds`, `normset.rds`, or `rgset.rds`.

Typical workflow:
1. Run `illumina_methylation_process` first.
2. On render, `config/input_registry.csv` is auto-populated from active `illumina_methylation_process` runs in `project.yaml`.
3. Review/edit `config/input_registry.csv` if you want to adjust enabled runs, include/exclude filters, or external/manual inputs.
4. Optionally maintain `config/group_map.csv` for cross-dataset group harmonization.
5. Run `pixi run sync-samples` (or rely on `run.sh`, which does this by default).
6. Review `config/samples.csv` and analysis settings in `config/project.toml`.
7. Run this compare template.

## Multi-run input selection

`config/input_registry.csv` columns:
- `run_id`: short label for this input run.
- `dataset_id`: dataset/study identifier for provenance.
- `process_template`: upstream template identifier.
- `processed_results_dir`: path to a process run `results/rds` folder.
- `samples_file`: optional source sample sheet for this run (merged during sync).
- `array_type`: per-run array type (`450K`, `EPIC`, `EPIC_V2`) for mixed-array enrichment handling.
- `genome_build`: per-run genome build label for provenance.
- `enabled`: `true`/`false`.
- `include_samples`: optional comma/semicolon-separated sample IDs to keep.
- `exclude_samples`: optional comma/semicolon-separated sample IDs to drop.

Notes:
- Source directories are resolved strictly from configured paths; the pipeline does not silently fall back to generic `../results/rds`.
- By default, `input.require_samples_in_sheet = false` to avoid accidental sample drop on first run.
- If multiple runs are enabled, probes are merged by intersection of CpG IDs.
- Mixed `450K` + `EPIC/EPIC_V2` is supported by probe intersection; enrichment auto-selects a compatible mapping (`450K` when 450K is present).
- `sample_id` must be globally unique across all enabled runs.
- `config/group_map.csv` can normalize group labels (e.g., `plexNfib` -> `plexiform neurofibroma`) globally or per run/dataset.

## Render

```bash
bpm template render illumina_methylation_compare \
  --param process_results_dir=../illumina_methylation_process/results/rds \
  --param array_type=AUTO \
  --param group_col=group \
  --param case_label=HPNST \
  --param control_label=HPNST-SC \
  --dir /path/to/project
```

`study_name` is optional; if omitted, the rendered template id is used as project/report name.

On render, a post-render hook auto-discovers active `illumina_methylation_process` runs from
`project.yaml` and writes `config/input_registry.csv`.
Disable this behavior with:
```bash
bpm template render illumina_methylation_compare --param auto_discover_inputs=false --dir /path/to/project
```

After render, adjust:
- `config/input_registry.csv` to combine runs / filter samples.
- `config/group_map.csv` to harmonize grouping labels across datasets.
- `config/project.toml` to tune analysis parameters (`dmp`, `dmr`, `enrichment`, `drilldown`).

Example multi-run setup:

```csv
run_id,dataset_id,process_template,array_type,genome_build,processed_results_dir,samples_file,enabled,include_samples,exclude_samples
process_450k,geo_450k,illumina_methylation_process,450K,hg38,../process_450k/results/rds,../process_450k/samples.csv,true,,
process_epic_geo_schwannoma_core_n50,geo_epic_core,illumina_methylation_process,EPIC,hg38,../process_epic_geo_schwannoma_core_n50/results/rds,../process_epic_geo_schwannoma_core_n50/samples.csv,true,,
process_epic_internal_tumor_panel_n37,internal_epic_panel,illumina_methylation_process,EPIC,hg38,../process_epic_internal_tumor_panel_n37/results/rds,../process_epic_internal_tumor_panel_n37/samples.csv,true,,
process_epic_mini_mixed_n6,internal_epic_mini,illumina_methylation_process,EPIC,hg38,../process_epic_mini_mixed_n6/results/rds,../process_epic_mini_mixed_n6/samples.csv,true,,
```

Refresh comparison sample sheet from enabled runs:

```bash
pixi run sync-samples
```

## Run

```bash
bpm template run illumina_methylation_compare --dir /path/to/project
# or inside rendered folder
./run.sh
```
