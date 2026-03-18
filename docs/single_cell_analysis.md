# Single-Cell Analysis Plan

This document defines the top-level design for future single-cell analysis templates in
`UKA_GF_BRS`. The target is a Python-first, scverse-based template family that integrates
cleanly with BPM project history and published outputs from upstream templates such as
`nfcore_scrnaseq`.

## Goals

- Standardize single-cell downstream analysis around the Scanpy/scverse ecosystem.
- Consume `nf-core/scrnaseq` outputs directly, with minimal manual path handling.
- Replace the older monolithic notebook approach with focused BRS templates using:
  - `template_config.yaml`
  - `pixi.toml`
  - `run.sh.j2`
  - one or more Quarto `.qmd` reports
- Keep each template narrow enough to be maintainable and testable.
- Define stable data contracts now so templates can be chained through `project.yaml`.

## Current upstream contract

`nfcore_scrnaseq` is the upstream entry point for scRNA-seq count processing.

Published output:
- `templates.nfcore_scrnaseq.published.nfcore_scrnaseq_res_mt`

Meaning:
- preferred downstream `.h5ad` matrix path resolved from
  `results/<aligner>/mtx_conversions/`
- current resolver preference:
  - `combined_filtered_matrix.h5ad`
  - `combined_cellbender_filter_matrix.h5ad`
  - `combined_raw_matrix.h5ad`
  - `combined_matrix.h5ad`
  - sample-level `.h5ad` fallbacks if combined outputs are absent

This key should be the default handoff for future scRNA templates.

## Design principles

- Do not build one giant single-cell template.
- Separate preprocessing, integration, annotation, differential analysis, and advanced
  modalities into distinct templates.
- Use `.h5ad` for single-modality data and `.h5mu` for multimodal data.
- Prefer resolver-backed upstream discovery over manual path parameters.
- Keep compute logic in Python modules/scripts and use `.qmd` files primarily for
  reporting and orchestration.
- Favor robust CPU defaults; keep GPU acceleration optional.
- Prefer sample-aware statistical methods by default, especially for differential
  analysis.

## Proposed template family

### 1. `cellbender_remove_background`

Purpose:
- Provide an optional upstream ambient RNA correction step for raw droplet matrices.
- Keep ambient/background correction separate from the general Scanpy preprocessing
  template so the data contract stays explicit.

Inputs:
- raw droplet matrix, typically `raw_feature_bc_matrix.h5`
- optional expected cell count and CellBender tuning parameters

Core tasks:
- run `cellbender remove-background`
- publish the corrected raw-count matrix
- record the run parameters and output presence in a lightweight report

Outputs:
- `published.cellbender_corrected_matrix`
- `results/cellbender/cellbender_filtered.h5`
- `00_summary.html`

Notes:
- This template should remain optional.
- `scverse_scrna_prep` should prefer this published output over the generic
  nf-core result matrix when both exist in project history.

### 2. `scverse_scrna_prep`

Purpose:
- Load upstream matrix and metadata.
- Run initial QC, filtering, normalization, feature selection, dimensionality reduction,
  clustering, and baseline visualization.

Inputs:
- `nfcore_scrnaseq_res_mt` from `project.yaml`
- optional sample metadata table
- optional project config for QC thresholds

Core tasks:
- read `.h5ad`
- standardize metadata columns
- compute QC metrics
- mitochondrial / ribosomal / hemoglobin summaries
- cell filtering and gene filtering
- optional doublet scoring hooks
- normalization and log transform
- HVG selection
- PCA, neighbors, UMAP
- Leiden clustering

Outputs:
- `published.scrna_prep_h5ad`
- `results/adata.prep.h5ad`
- `results/tables/qc_metrics.csv`
- `reports/00_qc.html`
- `reports/01_embedding.html`

Default stack:
- `scanpy`
- `anndata`
- `pandas`
- `numpy`
- `matplotlib`
- `seaborn`
- optional `scrublet` or `doubletdetection`

### 3. `scverse_scrna_integrate`

Purpose:
- Correct batch effects and produce integrated embeddings while preserving the original
  count-derived state for later analyses.

Inputs:
- `scrna_prep_h5ad`

Core tasks:
- evaluate batch structure
- run one selected integration backend
- compute integrated neighbors / UMAP
- compare pre/post integration structure

Supported methods:
- `harmony` as the default CPU-friendly baseline
- `bbknn`
- `scanorama`
- `scvi`

Outputs:
- `published.scrna_integrated_h5ad`
- `results/adata.integrated.h5ad`
- `reports/00_batch_effects.html`

Notes:
- Do not force one integration method for all projects.
- The template should expose `integration_method` and `batch_key` explicitly.

### 4. `scverse_scrna_annotate`

Purpose:
- Add biological interpretation to clusters and cells using multiple annotation routes.

Inputs:
- `scrna_integrated_h5ad` or `scrna_prep_h5ad`

Annotation routes:
- manual marker review
- reference mapping with `scanpy.tl.ingest`
- classifier-based labeling with `CellTypist`
- deep generative mapping with `scANVI` where appropriate

Outputs:
- `published.scrna_annotated_h5ad`
- `results/adata.annotated.h5ad`
- `results/tables/marker_summary.csv`
- `reports/00_annotation.html`

Standard obs fields:
- `cell_type_level1`
- `cell_type_level2`
- `annotation_method`
- `annotation_score`

### 5. `scverse_scrna_de`

Purpose:
- Run downstream comparisons after annotation, with sample-aware defaults.

Inputs:
- `scrna_annotated_h5ad`
- comparison config
- sample metadata with biological replicate information

Core tasks:
- define analysis groups
- pseudobulk aggregation by sample and cell type
- differential testing
- visualization and enrichment

Default approach:
- pseudobulk-first differential analysis

Methods to evaluate:
- `decoupler` utilities for aggregation and enrichment
- Python-native statistical path if sufficiently robust
- optional R-backed edgeR/DESeq2 later only if strictly needed

Outputs:
- `results/tables/comparisons/<comparison_id>/...`
- `reports/00_overview.html`
- `reports/01_differential_expression.html`
- `reports/02_enrichment.html`

### 6. `scverse_scrna_trajectory`

Purpose:
- Reconstruct differentiation continua and lineage relationships.

Inputs:
- `scrna_annotated_h5ad`

Methods:
- `PAGA`
- `DPT`
- `CellRank` for fate probabilities
- optional `moscot` later if needed

Outputs:
- `published.scrna_trajectory_h5ad`
- trajectory report with lineage and pseudotime summaries

### 7. `scverse_scrna_velocity`

Purpose:
- Model RNA velocity when spliced/unspliced information is available.

Inputs:
- annotated `.h5ad` with `spliced` and `unspliced` layers or compatible upstream files

Methods:
- `scvelo`
- `CellRank` coupling when useful

Outputs:
- `published.scrna_velocity_h5ad`
- velocity report with stream/grid embeddings and lineage interpretation

Notes:
- Keep separate from generic trajectory analysis because the input requirements differ.

### 8. `scverse_spatial`

Purpose:
- Handle spatial single-cell / spatial transcriptomics analysis as a separate track.

Inputs:
- `SpatialData` or technology-specific spatial outputs

Methods:
- `spatialdata`
- `spatialdata-io`
- `squidpy`

Outputs:
- spatial neighborhood and niche reports
- spatial object publish key

Notes:
- Spatial packages currently have a different dependency profile from core scRNA work.
- Keep a dedicated Pixi environment.

### 9. `scverse_scatac`

Purpose:
- Support scATAC-seq and related chromatin accessibility workflows.

Inputs:
- peak/barcode matrices or upstream scATAC outputs

Methods:
- `SnapATAC2`
- optional `muon` integration for multimodal work

Core tasks:
- QC
- LSI / spectral embedding
- clustering
- differential accessibility
- motif and gene activity summaries

### 10. `scverse_multimodal`

Purpose:
- Support RNA + ATAC or RNA + protein integration and consistency checks.

Data model:
- `.h5mu`

Methods:
- `mudata`
- `muon`
- selected `scvi-tools` multimodal models where justified

Use cases:
- co-embedding
- cross-modality label consistency
- cell type embedding checks
- modality-aware QC

## Shared data contract

These keys should be standardized across templates where possible.

### Metadata columns

- `sample_id`
- `patient_id`
- `condition`
- `batch`
- `library_id`
- `technology`
- `dataset_id`
- `replicate_id`

### Matrix/layer conventions

- raw counts in `layers["counts"]`
- working normalized matrix in `X`
- optional `layers["log1p"]` only when justified
- velocity data in:
  - `layers["spliced"]`
  - `layers["unspliced"]`

### Embedding keys

- `X_pca`
- `X_umap`
- `X_tsne` only if explicitly requested
- `X_pca_harmony`
- `X_scvi`
- `X_lsi` for ATAC

### Standard output publish keys

Each template should publish one primary object path for downstream discovery.

Examples:
- `scrna_prep_h5ad`
- `scrna_integrated_h5ad`
- `scrna_annotated_h5ad`
- `scrna_trajectory_h5ad`
- `scrna_velocity_h5ad`
- `spatial_object`
- `scatac_h5ad`
- `multimodal_h5mu`

## Config strategy

Each template should use a local `config/project.toml` with explicit sections.

Recommended sections:
- `[project]`
- `[input]`
- `[qc]`
- `[normalization]`
- `[integration]`
- `[annotation]`
- `[comparison]`
- `[plotting]`
- `[output]`

Use CSV sidecars only where the data is naturally tabular and user-edited, for example:
- `config/samples.csv`
- `config/comparisons.csv`
- `config/group_map.csv`

## Environment strategy

Do not force one `pixi.toml` to cover all single-cell modalities.

Recommended split:
- one environment for core scRNA templates
- one environment for spatial templates
- one environment for scATAC / multimodal templates
- optional GPU variant or optional dependencies for `scvi-tools` and
  `rapids-singlecell`

Rationale:
- spatial and multimodal packages evolve at different rates
- GPU dependencies should remain optional
- smaller environments are easier to solve, cache, and support

## Implementation order

Build in this order:

1. `scverse_scrna_prep`
2. `scverse_scrna_integrate`
3. `scverse_scrna_annotate`
4. `scverse_scrna_de`
5. `scverse_scrna_trajectory`
6. `scverse_scrna_velocity`
7. `scverse_spatial`
8. `scverse_scatac`
9. `scverse_multimodal`

Reasoning:
- the first four templates cover the majority of routine facility projects
- they establish the core `.h5ad` contract and config conventions
- trajectory, velocity, spatial, and ATAC can then reuse those patterns

## First implementation target

Start with `scverse_scrna_prep`.

Minimum viable scope:
- auto-resolve `nfcore_scrnaseq_res_mt` from `project.yaml`
- render a `pixi.toml`
- write `config/project.toml`
- run QC and baseline Scanpy preprocessing
- write one primary `.h5ad`
- render at least one Quarto HTML report

Minimum parameters:
- `input_h5ad`
- `sample_metadata`
- `organism`
- `batch_key`
- `condition_key`
- `doublet_method`

Likely auto-resolution behavior:
- if `input_h5ad` is not provided, use
  `templates.nfcore_scrnaseq.published.nfcore_scrnaseq_res_mt`

## Open design questions

- Whether sample metadata should be auto-generated from `project.yaml` history or always
  rendered as an editable CSV scaffold.
- Which doublet method should be the default in CPU-only environments.
- Whether differential analysis should remain pure Python in the first version or allow a
  controlled R bridge for pseudobulk.
- How far to support GPU-specific methods in facility defaults.
- How to handle atlas/reference files for annotation in a reproducible way.

## Current package direction

The current ecosystem direction supports this design:
- Scanpy and AnnData remain the core single-cell stack.
- `scvi-tools` is the strongest option for advanced integration and reference mapping.
- `decoupler` is part of the scverse ecosystem and is a good fit for pathway and activity
  analysis.
- `SpatialData` and `Squidpy` are the right basis for spatial work.
- `SnapATAC2` is the leading scverse-aligned option for scATAC.
- `MuData` / `muon` are the right containers for multimodal templates.
- `CellRank` and `scVelo` remain the main trajectory / velocity components.
- `rapids-singlecell` should be treated as optional acceleration, not a hard dependency.

## References

- Scanpy: <https://scanpy.readthedocs.io/>
- AnnData: <https://anndata.readthedocs.io/>
- scvi-tools: <https://docs.scvi-tools.org/>
- decoupler: <https://decoupler.readthedocs.io/>
- CellRank: <https://cellrank.readthedocs.io/>
- scVelo: <https://scvelo.readthedocs.io/>
- SpatialData: <https://spatialdata.scverse.org/>
- Squidpy: <https://squidpy.readthedocs.io/>
- MuData: <https://mudata.readthedocs.io/>
- muon: <https://muon.readthedocs.io/>
- SnapATAC2: <https://scverse.org/SnapATAC2/>
- rapids-singlecell: <https://rapids-singlecell.readthedocs.io/>
- nf-core/scrnaseq outputs: <https://nf-co.re/scrnaseq/latest/docs/output>
