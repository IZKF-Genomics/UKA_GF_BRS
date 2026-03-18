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
- input_h5ad
- leiden_resolution
- max_pct_counts_mt
- min_cells
- min_counts
- min_genes
- n_neighbors
- n_pcs
- n_top_hvgs
- organism
- sample_id_key
- sample_metadata
run_entry: run.sh
publish_keys:
- scrna_prep_h5ad
render_file_count: 8
```
<!-- AGENT_METADATA_END -->

Scanpy/scverse preprocessing template for single-cell RNA-seq.

Scope:
- consume an upstream `.h5ad` matrix, typically from `nfcore_scrnaseq`
- compute baseline QC metrics
- filter cells and genes
- normalize and log-transform
- flag highly variable genes
- run PCA, neighbors, UMAP, and Leiden clustering
- write one downstream `adata.prep.h5ad`
- render a Quarto QC/embedding report

## Upstream discovery

If `input_h5ad` is not provided, the pre-render hook tries to resolve:

- `templates.nfcore_scrnaseq.published.nfcore_scrnaseq_res_mt`

This is intended to make `scverse_scrna_prep` the default downstream step after
`nfcore_scrnaseq`.

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

Standalone/ad-hoc usage with an explicit input:

```bash
bpm template render scverse_scrna_prep \
  --param input_h5ad=/path/to/input.h5ad \
  --out /path/to/output
```

## Run

```bash
bpm template run scverse_scrna_prep --dir /path/to/project
# or inside rendered folder
./run.sh
```

## Key files

- `config/project.toml`: analysis configuration written at render time
- `config/samples.csv`: optional editable sample metadata scaffold
- `scripts/run_prep.py`: Scanpy preprocessing entrypoint
- `00_qc.qmd`: HTML report

## Outputs

- `results/adata.prep.h5ad`: primary downstream object
- `results/tables/qc_summary.csv`: pre/post filter summary
- `results/tables/sample_qc_summary.csv`: sample-level QC summary
- `results/tables/cluster_counts.csv`: cluster abundances
- `results/figures/*.png`: QC and embedding figures
- `reports/00_qc.html`: rendered report

Published output:
- `scrna_prep_h5ad`: resolver-backed path to `results/adata.prep.h5ad`
