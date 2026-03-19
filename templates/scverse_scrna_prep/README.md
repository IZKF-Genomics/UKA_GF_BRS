# scverse_scrna_prep


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: scverse_scrna_prep
kind: template
description: scverse/Scanpy single-cell RNA-seq preprocessing from nf-core/scrnaseq
  H5AD outputs.
descriptor: templates/scverse_scrna_prep/template_config.yaml
required_params: []
optional_params:
- batch_key
- condition_key
- doublet_method
- filter_predicted_doublets
- input_h5ad
- input_matrix
- input_format
- leiden_resolution
- max_pct_counts_hb
- max_pct_counts_mt
- max_pct_counts_ribo
- min_cells
- min_counts
- min_genes
- n_neighbors
- n_pcs
- n_top_hvgs
- organism
- qc_mode
- qc_nmads
- resolution_grid
- sample_id_key
- sample_metadata
- var_names
run_entry: run.sh
publish_keys:
- scrna_prep_h5ad
render_file_count: 7
```
<!-- AGENT_METADATA_END -->

Scanpy/scverse preprocessing template for single-cell RNA-seq.

Scope:
- consume an upstream `.h5ad` matrix, typically from `nfcore_scrnaseq`
- also accept direct Cell Ranger, ParseBio, and ScaleBio matrix inputs
- compute baseline QC metrics including mitochondrial, ribosomal, hemoglobin, and optional doublet scores
- support fixed-threshold QC and optional per-sample MAD-based QC
- filter cells and genes with explicit before/after diagnostics
- normalize and log-transform
- flag highly variable genes
- run PCA, neighbors, UMAP, and Leiden clustering
- benchmark multiple clustering resolutions for review
- summarize cluster composition by sample and condition
- write one downstream `adata.prep.h5ad`
- render a Quarto QC/embedding report

## Upstream discovery

If `input_h5ad` is not provided, the pre-render hook tries to resolve in order:

- `templates.cellbender_remove_background.published.cellbender_corrected_matrix`
- `templates.nfcore_scrnaseq.published.nfcore_scrnaseq_res_mt`

This is intended to make `scverse_scrna_prep` the default downstream step after
`nfcore_scrnaseq`, while preferring a dedicated ambient-RNA-corrected upstream
matrix when a `cellbender_remove_background` step exists in project history.

Direct manual inputs are also supported:
- `--param input_matrix=/path/to/file.h5ad`
- `--param input_matrix=/path/to/filtered_feature_bc_matrix.h5`
- `--param input_matrix=/path/to/filtered_feature_bc_matrix`
- `--param input_matrix=/path/to/parsebio/output --param input_format=parsebio`
- `--param input_matrix=/path/to/scalebio/output --param input_format=scalebio`

Set `--param input_format=auto|h5ad|10x_h5|10x_mtx|parsebio|scalebio` when auto-detection is not sufficient.
In practice, `parsebio` is auto-detected from its directory structure, while `scalebio`
often still benefits from an explicit `--param input_format=scalebio` because its file
layout can overlap with generic MTX-style outputs.
For `10x_mtx` or `scalebio` inputs, set `--param var_names=gene_symbols|gene_ids` as needed.

## Render

```bash
bpm template render scverse_scrna_prep --dir /path/to/project
```

Optional overrides:

```bash
bpm template render scverse_scrna_prep \
  --param organism=human \
  --param batch_key=batch \
  --param condition_key=condition \
  --param max_pct_counts_mt=15 \
  --dir /path/to/project
```

`leiden_resolution` is optional. If omitted, the template chooses a heuristic value
after QC based on the number of retained cells and records the resolved value in the
results.

Useful QC-related overrides:

```bash
bpm template render scverse_scrna_prep \
  --param doublet_method=scrublet \
  --param filter_predicted_doublets=true \
  --param qc_mode=mad_per_sample \
  --param qc_nmads=3 \
  --param max_pct_counts_mt=15 \
  --param max_pct_counts_ribo=40 \
  --param resolution_grid=0.2,0.4,0.6,0.8,1.0,1.2 \
  --dir /path/to/project
```

Standalone/ad-hoc usage with an explicit input:

```bash
bpm template render scverse_scrna_prep \
  --param input_matrix=/path/to/filtered_feature_bc_matrix.h5 \
  --out /path/to/output
```

If explicit input paths or sample-metadata paths use host-prefixed values such as
`nextgen:/...`, the pre-render hook materializes them into the local filesystem
paths used by the rendered notebook.

## Run

```bash
bpm template run scverse_scrna_prep --dir /path/to/project
# or inside rendered folder
./run.sh
```

## Key files

- `config/project.toml`: analysis configuration written at render time
- `config/samples.csv`: editable sample metadata scaffold; post-render hook pre-fills `sample_id`
  from `nfcore_scrnaseq.published.nfcore_samplesheet` when available and otherwise
  falls back to the direct input name; `sample_label` can be used to rename report-facing labels
- `00_qc.qmd`: Quarto notebook containing the preprocessing logic and report

## Outputs

- `results/adata.prep.h5ad`: primary downstream object
- `results/tables/qc_summary.csv`: pre/post filter summary
- `results/tables/sample_qc_summary.csv`: sample-level QC summary
- `results/tables/cluster_counts.csv`: cluster abundances
- `results/tables/filter_effect_summary.csv`: retained/removed cell and gene summary
- `results/tables/qc_metric_stage_summary.csv`: per-metric before/after summaries
- `results/tables/qc_metric_before_after.csv`: compact before/after delta table
- `results/tables/cluster_resolution_diagnostics.csv`: Leiden resolution benchmark table
- `results/tables/cluster_by_sample_counts.csv`: cluster counts by sample label
- `results/tables/cluster_by_sample_fraction.csv`: row-normalized cluster fractions by sample label
- `results/tables/cluster_by_condition_counts.csv`: cluster counts by condition
- `results/tables/cluster_by_condition_fraction.csv`: row-normalized cluster fractions by condition
- `results/tables/session_info.csv`: package and platform versions used for the run
- `00_qc.html`: rendered report

## Notes

- `organism` is not hard-defaulted. The pre-render hook first looks for an upstream
  `params.organism` and then falls back to mapping common upstream `params.genome`
  values such as `GRCh38` or `GRCm39`.
- Input provenance is recorded in the rendered config/report via
  `input_source_template`, `ambient_correction_applied`, and
  `ambient_correction_method`.
- Scrublet support is fully Python-native. Ambient RNA correction from the older
  R-based template is not performed inside this template; use an upstream
  `cellbender_remove_background` template when available.
- This template expects enough retained cells for PCA/neighbors/UMAP. If fewer than
  3 cells remain after QC, the notebook stops with a clear error instead of trying
  to continue into invalid dimensionality-reduction settings.

Published output:
- `scrna_prep_h5ad`: resolver-backed path to `results/adata.prep.h5ad`
