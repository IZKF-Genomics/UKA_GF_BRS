# scverse_scrna_integrate


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: scverse_scrna_integrate
kind: template
description: scverse/Scanpy single-cell RNA-seq integration from scverse_scrna_prep
  outputs.
descriptor: templates/scverse_scrna_integrate/template_config.yaml
required_params: []
optional_params:
- batch_key
- bbknn_neighbors_within_batch
- bbknn_trim
- cluster_resolution
- condition_key
- harmony_lambda
- harmony_max_iter
- harmony_theta
- input_h5ad
- input_source_template
- integration_method
- n_neighbors
- n_pcs
- sample_id_key
- sample_label_key
- umap_min_dist
- use_hvgs_only
run_entry: run.sh
publish_keys:
- scrna_integrated_h5ad
render_file_count: 6
```
<!-- AGENT_METADATA_END -->

Scanpy/scverse integration template for single-cell RNA-seq.

Scope:
- consume a preprocessed `.h5ad`, typically from `scverse_scrna_prep`
- run one integration backend with explicit provenance
- rebuild the graph and UMAP in integrated space
- write one downstream `adata.integrated.h5ad`
- render a Quarto report with batch-mixing diagnostics

## Upstream discovery

If `input_h5ad` is not provided, the pre-render hook resolves:

- `templates.scverse_scrna_prep.published.scrna_prep_h5ad`

Direct manual input is also supported:
- `--param input_h5ad=/path/to/adata.prep.h5ad`

If explicit input paths use host-prefixed values such as `nextgen:/...`, the
pre-render hook materializes them into local filesystem paths before render.

## Integration methods

This first version supports:
- `harmony` (default)
- `bbknn`

Recommended defaults:
- use `harmony` when you want a straightforward integrated PCA embedding with
  minimal extra graph logic
- use `bbknn` when your main goal is balanced neighbor graph construction across
  batches and you want a lighter-weight alternative

This template assumes that the input object already contains the basic prep-stage
content from `scverse_scrna_prep`, including:
- `layers["counts"]`
- QC-filtered cells
- highly variable gene flags when available
- baseline metadata such as `sample_id`, `batch`, and `condition`

## Render

```bash
bpm template render scverse_scrna_integrate --dir /path/to/project
```

Optional overrides:

```bash
bpm template render scverse_scrna_integrate \
  --param integration_method=harmony \
  --param batch_key=batch \
  --param n_pcs=30 \
  --param n_neighbors=15 \
  --dir /path/to/project
```

Standalone/ad-hoc usage with an explicit input:

```bash
bpm template render scverse_scrna_integrate \
  --param input_h5ad=/path/to/adata.prep.h5ad \
  --out /path/to/output
```

## Run

```bash
bpm template run scverse_scrna_integrate --dir /path/to/project
# or inside rendered folder
./run.sh
```

## Key files

- `config/project.toml`: analysis configuration written at render time
- `00_integrate.qmd`: Quarto notebook containing the integration logic and report

## Outputs

- `results/adata.integrated.h5ad`: primary downstream object
- `results/tables/integration_summary.csv`: integration configuration and object summary
- `results/tables/batch_mixing_summary.csv`: batch-level diagnostics in the integrated graph
- `results/tables/cluster_counts.csv`: integrated Leiden cluster abundances
- `results/tables/session_info.csv`: package and platform versions used for the run
- `00_integrate.html`: rendered report

## Notes

- This template does not overwrite the prep-stage object. It writes a separate
  `results/adata.integrated.h5ad` file for downstream annotation/DE work.
- The template records:
  - `input_source_template`
  - `integration_method`
  - key integration parameters
  in both the report-facing tables and `adata.uns`.
- `harmony` currently writes the integrated embedding to `obsm["X_pca_harmony"]`.
- `bbknn` currently rebuilds the graph directly from the chosen PCA space and
  records the method in `uns`.

Published output:
- `scrna_integrated_h5ad`: resolver-backed path to `results/adata.integrated.h5ad`
