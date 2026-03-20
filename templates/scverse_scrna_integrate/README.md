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
- scanvi_label_key
- scanvi_unlabeled_category
- scvi_accelerator
- scvi_devices
- scvi_gene_likelihood
- scvi_latent_dim
- scvi_max_epochs
- umap_min_dist
- use_hvgs_only
run_entry: run.sh
publish_keys:
- scrna_integrated_h5ad
render_file_count: 6
```
<!-- AGENT_METADATA_END -->

Scanpy/scverse integration template for single-cell RNA-seq. It consumes a prep-stage `.h5ad`, applies one integration backend, rebuilds the neighbor graph and UMAP from the integrated representation, and writes one canonical downstream object at `results/adata.integrated.h5ad`.

## Scope

This template is designed for batch correction and cross-sample integration after QC/prep. It is not a raw-count preprocessing template and it is not an annotation template.

Expected input:
- prep-stage `.h5ad`, typically from `scverse_scrna_prep`
- cell metadata including batch/sample fields
- `layers["counts"]` available for `scvi` and `scanvi`

Main outputs:
- `results/adata.integrated.h5ad`
- `results/tables/integration_summary.csv`
- `results/tables/batch_mixing_summary.csv`
- `results/tables/cluster_counts.csv`
- `results/tables/session_info.csv`
- `00_integrate.html`

Published output:
- `scrna_integrated_h5ad`

## Upstream Discovery

If `input_h5ad` is not provided, the pre-render hook resolves:

- `templates.scverse_scrna_prep.published.scrna_prep_h5ad`

Direct manual input is also supported:

```bash
bpm template render scverse_scrna_integrate \
  --param input_h5ad=/path/to/adata.prep.h5ad \
  --out /path/to/output
```

Host-prefixed values such as `nextgen:/...` are materialized to local paths before render.

## Supported Methods

This template currently supports:
- `harmony`
- `bbknn`
- `scanorama`
- `scvi`
- `scanvi`

### Method Comparison

| Method | Type | Good Default Use | Typical Scale | GPU | Weak Fits / Unsuitable Cases |
| --- | --- | --- | --- | --- | --- |
| `harmony` | PCA-space correction | General-purpose batch correction when you want a fast, stable integrated embedding | Small to large | No | Very strong non-linear batch effects; multimodal latent modeling; cases where you want a reusable probabilistic latent model |
| `bbknn` | Graph balancing | Fast neighborhood correction when PCA already separates biology reasonably well | Small to medium-large | No | When you need a corrected embedding rather than only a balanced graph; severe batch effects; highly imbalanced batches |
| `scanorama` | Manifold stitching | Cross-dataset integration when batches are related but not perfectly overlapping | Medium to large | No | Extremely homogeneous batches where simpler methods are enough; very large atlas-scale runs where `scvi` may scale better |
| `scvi` | Deep generative latent model | Strong all-purpose integration for heterogeneous datasets and downstream latent-space reuse | Medium to very large | Recommended, not required | Very small datasets where training overhead is not worth it; inputs without raw counts |
| `scanvi` | Semi-supervised deep generative model | Integration plus label transfer / partial annotation refinement | Medium to very large | Recommended, not required | Datasets without a meaningful label column; labels that are low quality or entirely absent |

### Practical Guidance

Use `harmony` when:
- you want a CPU-friendly default
- you need something robust for most routine batch correction
- your downstream work is clustering, UMAP, and annotation

Use `bbknn` when:
- your main goal is graph construction rather than latent modeling
- batches are modest and the biology is already visible in PCA
- you want a very lightweight correction step

Use `scanorama` when:
- you are integrating multiple studies or cohorts with partially shared structure
- you want a non-deep method that can do more than graph balancing

Use `scvi` when:
- datasets are large
- batch structure is strong or complex
- you want a reusable latent representation for downstream work
- GPU is available and you want a stronger modern default

Use `scanvi` when:
- you already have a label column such as coarse cell type annotations
- some cells are unlabeled or uncertain
- you want integration and semi-supervised label refinement in one model

### Cell Number Heuristics

These are practical heuristics, not hard limits:

- `< 5k cells`: `harmony` or `bbknn` are usually the simplest choices
- `5k to 100k cells`: `harmony`, `scanorama`, and `scvi` are all reasonable
- `> 100k cells`: `scvi` is often the best long-term choice if compute allows it
- `scanvi` becomes attractive once you have enough labeled data to inform the model

### GPU Expectations

- `harmony`: GPU not needed
- `bbknn`: GPU not needed
- `scanorama`: GPU not needed
- `scvi`: runs on CPU, but GPU is strongly recommended for larger datasets
- `scanvi`: runs on CPU, but GPU is strongly recommended for larger datasets

### Important Caveats

- `scvi` and `scanvi` expect count-like input and use `layers["counts"]` when available.
- `scanvi` is not a generic unsupervised integration method. It needs a meaningful label column via `scanvi_label_key`.
- `bbknn` corrects the graph, not the PCA matrix itself.
- `harmony` and `scanorama` work in feature/PCA space and therefore depend more directly on the chosen HVG/PCA setup.

## Key Parameters

General:
- `integration_method`
- `batch_key`
- `condition_key`
- `sample_id_key`
- `sample_label_key`
- `use_hvgs_only`
- `n_pcs`
- `n_neighbors`
- `umap_min_dist`
- `cluster_resolution`

Harmony:
- `harmony_theta`
- `harmony_lambda`
- `harmony_max_iter`

BBKNN:
- `bbknn_neighbors_within_batch`
- `bbknn_trim`

scVI / scANVI:
- `scvi_latent_dim`
- `scvi_max_epochs`
- `scvi_gene_likelihood`
- `scvi_accelerator`
- `scvi_devices`

scANVI only:
- `scanvi_label_key`
- `scanvi_unlabeled_category`

## Render

From the project directory:

```bash
bpm template render scverse_scrna_integrate
```

With explicit method choice:

```bash
bpm template render scverse_scrna_integrate \
  --param integration_method=scvi \
  --param batch_key=batch \
  --param n_pcs=30 \
  --param n_neighbors=15
```

scANVI example:

```bash
bpm template render scverse_scrna_integrate \
  --param integration_method=scanvi \
  --param scanvi_label_key=cell_type_coarse \
  --param scanvi_unlabeled_category=Unknown
```

From outside the project directory:

```bash
bpm template render scverse_scrna_integrate --dir /path/to/project
```

## Run

```bash
bpm template run scverse_scrna_integrate
# or inside the rendered template folder
./run.sh
```

From outside the project directory:

```bash
bpm template run scverse_scrna_integrate --dir /path/to/project
```

## Output Semantics

This template writes a new stage object and does not overwrite the prep-stage object.

Saved object:
- `results/adata.integrated.h5ad`

Recorded provenance:
- `input_source_template`
- `integration_method`
- `integration_embedding_key`
- key method parameters

Method-specific embedding keys:
- `harmony`: `obsm["X_pca_harmony"]`
- `bbknn`: neighbors built from `obsm["X_pca"]`
- `scanorama`: `obsm["X_scanorama"]`
- `scvi`: `obsm["X_scvi"]`
- `scanvi`: `obsm["X_scanvi"]`

## Environment

This template uses Pixi and includes:
- Scanpy/scverse stack
- `harmonypy`
- `bbknn`
- `scanorama`
- `scvi-tools`

`scvi-tools` can run on CPU, but practical performance improves substantially with GPU for large datasets.
