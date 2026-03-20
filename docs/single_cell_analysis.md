# Single-Cell Analysis Plan

This document defines the current design for single-cell analysis templates in
`UKA_GF_BRS`. The direction is Python-first and scverse-based, with BPM-managed
template chaining through stable publish keys in `project.yaml`.

The goal is not to reproduce the older monolithic notebook workflow inside one
template. The goal is to build a small template family with explicit handoff
objects, clear provenance, and separate environments where the dependency
profiles genuinely differ.

## Goals

- Standardize downstream single-cell analysis around the Scanpy/scverse ecosystem.
- Consume `nf-core/scrnaseq` outputs directly when available.
- Keep each template narrow, testable, and publishable.
- Prefer one canonical primary object per template stage.
- Preserve stage-specific outputs instead of overwriting biologically distinct states.
- Make upstream/downstream discovery work through BPM publish keys rather than path guessing.

## Core Design Decisions

### 1. One stage, one canonical object

Each template should write one canonical primary object that represents its stage.

Examples:
- `cellbender_remove_background` -> corrected raw-count matrix
- `scverse_scrna_prep` -> `adata.prep.h5ad`
- `scverse_scrna_integrate` -> `adata.integrated.h5ad`
- `scverse_scrna_annotate` -> `adata.annotated.h5ad`

This object should be:
- saved as a distinct file
- published through one stable key
- used as the default handoff to the next template

Do not overwrite a previous biologically meaningful stage output in place.

### 2. Keep stage outputs separate

For single-cell data, separate files are preferable to overwriting:

- safer reruns
- easier debugging
- clearer provenance
- better reproducibility
- simpler downstream chaining

Recommended split:
- persistent stage objects:
  - biologically meaningful checkpoints
- temporary scratch files:
  - safe to remove with `pixi run clean`

Do not keep every accidental temporary copy forever, but do keep one canonical
object per stage.

### 3. Ambient RNA correction is upstream and optional

Ambient/background RNA correction is not just another QC plot. It is a raw-data
decontamination step and should remain a separate optional upstream template.

Current design:
- `cellbender_remove_background` is the optional ambient-RNA branch
- `scverse_scrna_prep` does not perform ambient correction internally
- `scverse_scrna_prep` records whether the input was already corrected

This keeps:
- the contract explicit
- the compute/runtime requirements isolated
- the QC notebook readable

### 4. Notebook-driven reporting is acceptable for prep

For `scverse_scrna_prep`, the analysis logic lives directly in a Quarto notebook:
- `00_qc.qmd`

This is intentional because the prep stage is:
- linear
- report-oriented
- easier for users to review when code and interpretation are in one place

For later templates, move reusable or more complex logic into modules only when
that actually improves maintainability.

### 5. Every template should have an input hook and an output resolver

For the single-cell template family, input discovery and output publishing should
be treated as first-class parts of the template contract.

Recommended standard:
- one pre-render hook:
  - resolve the best upstream published object into the local input param
  - materialize host-prefixed paths
  - fill provenance fields
- one publish resolver:
  - emit the canonical primary output path
  - write it back to `project.yaml`

This avoids:
- manual path editing
- inconsistent downstream handoff behavior
- ambiguity about which object the next template should consume

Current implemented examples:
- `cellbender_remove_background`
  - pre-render hook materializes `input_raw_matrix`
  - publish resolver emits `cellbender_corrected_matrix`
- `scverse_scrna_prep`
  - pre-render hook resolves and materializes explicit or upstream matrix inputs
  - publish resolver emits `scrna_prep_h5ad`

## Current Upstream Contract

### `nfcore_scrnaseq`

Current publish key:
- `templates.nfcore_scrnaseq.published.nfcore_scrnaseq_res_mt`

Meaning:
- preferred downstream `.h5ad` matrix resolved from
  `results/<aligner>/mtx_conversions/`

Current resolver preference:
- `combined_filtered_matrix.h5ad`
- `combined_cellbender_filter_matrix.h5ad`
- `combined_raw_matrix.h5ad`
- `combined_matrix.h5ad`
- sample-level `.h5ad` fallbacks if combined outputs are absent

### `cellbender_remove_background`

Current publish key:
- `templates.cellbender_remove_background.published.cellbender_corrected_matrix`

Meaning:
- corrected CellBender output for downstream use

Current published file:
- `results/cellbender/cellbender_filtered.h5`

Current input handling:
- pre-render hook materializes explicit `input_raw_matrix`
- current supported input contract is intentionally strict:
  - raw 10x HDF5 input
  - `input_format=10x_h5`

### Input preference for `scverse_scrna_prep`

Current default resolution order:
1. explicit `input_matrix`
2. explicit `input_h5ad`
3. `templates.cellbender_remove_background.published.cellbender_corrected_matrix`
4. `templates.nfcore_scrnaseq.published.nfcore_scrnaseq_res_mt`

This preference is intentional:
- use user override first
- prefer dedicated ambient-corrected input when present
- otherwise fall back to the generic nf-core downstream matrix

Current input handling:
- pre-render hook materializes explicit host-prefixed `input_matrix`, `input_h5ad`,
  and `sample_metadata` paths
- if no explicit matrix input is provided, the hook resolves the best upstream
  published object and records provenance

## File And Object Naming Convention

### Single-modality objects

Use `.h5ad`.

Recommended canonical file names:
- `adata.prep.h5ad`
- `adata.integrated.h5ad`
- `adata.annotated.h5ad`
- `adata.trajectory.h5ad`
- `adata.velocity.h5ad`

### Multimodal objects

Use `.h5mu`.

Recommended canonical file names:
- `adata.multimodal.h5mu`

### Raw / external matrix files

Keep original upstream files separate from downstream `.h5ad` products.

Examples:
- raw 10x input: `raw_feature_bc_matrix.h5`
- CellBender output: `cellbender_filtered.h5`

Do not overwrite raw inputs.

### Directory convention

Recommended within each template:
- `results/objects/` for stage objects when multiple objects are expected
- `results/tables/` for machine-readable summaries
- `results/figures/` for static exports when needed
- `results/tmp/` for scratch intermediates

Current implemented templates do not yet use `results/objects/` consistently,
but future templates should move in that direction.

## Shared Data Contract

These keys should be standardized across templates wherever possible.

### Metadata columns

- `sample_id`
- `sample_label`
- `sample_display`
- `patient_id`
- `condition`
- `batch`
- `library_id`
- `technology`
- `dataset_id`
- `replicate_id`

Notes:
- `sample_id` is the stable technical join key
- `sample_label` is the user-editable report-facing label
- `sample_display` is the resolved display column used in reports and plots

### Layer conventions

- raw counts in `layers["counts"]`
- working normalized matrix in `X`
- optional `layers["log1p"]` only if there is a concrete need
- velocity layers when present:
  - `layers["spliced"]`
  - `layers["unspliced"]`

### Embedding keys

- `X_pca`
- `X_umap`
- `X_scvi`
- `X_pca_harmony`
- `X_lsi`
- `X_tsne` only when explicitly justified

### Provenance keys

Downstream templates should record where their input came from.

Current prep-stage provenance fields:
- `input_source_template`
- `ambient_correction_applied`
- `ambient_correction_method`

These should become standard across future scverse templates.

## Current Template Family

### 1. `cellbender_remove_background`

Purpose:
- Optional upstream ambient RNA correction for raw droplet matrices

Current scope:
- consume raw 10x HDF5 input
- run `cellbender remove-background`
- publish corrected `.h5`
- render a minimal summary report

Current notes:
- host-prefixed input paths are materialized during render
- current supported input contract is intentionally strict:
  - `input_format=10x_h5`
- this template is intentionally minimal until validated on real project runs

Current outputs:
- `published.cellbender_corrected_matrix`
- `results/cellbender/cellbender_filtered.h5`
- `00_summary.html`

### 2. `scverse_scrna_prep`

Purpose:
- baseline scRNA preprocessing and QC

Current implemented behavior:
- notebook-driven execution in Quarto
- flexible input loading:
  - `.h5ad`
  - Cell Ranger `.h5`
  - generic `10x_mtx`
  - ParseBio directory
  - ScaleBio directory
- sample metadata scaffold:
  - `config/samples.csv`
- report-facing sample renaming through `sample_label`
- organism inheritance from upstream `organism`, then `genome`
- optional Scrublet scoring
- fixed-threshold QC
- optional per-sample MAD QC
- interactive Plotly report
- clustering resolution diagnostics
- sample/condition cluster composition summaries
- session info capture

Current canonical output:
- `published.scrna_prep_h5ad`
- `results/adata.prep.h5ad`

Current notes:
- if fewer than 3 cells remain after QC, the notebook stops rather than trying
  to run invalid PCA/neighbors settings
- ambient correction is not performed inside this template
- explicit host-prefixed input overrides are materialized during render, not only
  auto-resolved upstream publish keys
- a real-data network integration test is now present and passes on a downloaded
  PBMC3K subset
- that test already caught and fixed a real H5AD serialization issue in `uns`

### 3. `scverse_scrna_integrate`

Planned purpose:
- batch correction and integrated embedding generation

Recommended defaults:
- `harmony` as the baseline CPU-friendly default

Methods to support:
- `harmony`
- `bbknn`
- `scanorama`
- `scvi`

Planned canonical output:
- `published.scrna_integrated_h5ad`
- `results/adata.integrated.h5ad`

### 4. `scverse_scrna_annotate`

Planned purpose:
- cell and cluster annotation

Annotation routes:
- manual marker review
- `scanpy.tl.ingest`
- `CellTypist`
- `scANVI`

Planned canonical output:
- `published.scrna_annotated_h5ad`
- `results/adata.annotated.h5ad`

Standard annotation fields:
- `cell_type_level1`
- `cell_type_level2`
- `annotation_method`
- `annotation_score`

### 5. `scverse_scrna_de`

Planned purpose:
- downstream comparison and enrichment analysis

Default analytical stance:
- pseudobulk-first

Recommended stack:
- `decoupler`
- Python-native enrichment/utilities
- optional controlled R bridge later only if justified

Planned outputs:
- per-comparison tables under `results/tables/comparisons/`
- report pages for overview, DE, and enrichment

### 6. `scverse_scrna_trajectory`

Planned purpose:
- lineage and pseudotime analysis

Methods:
- `PAGA`
- `DPT`
- `CellRank`

Planned canonical output:
- `published.scrna_trajectory_h5ad`

### 7. `scverse_scrna_velocity`

Planned purpose:
- RNA velocity analysis when spliced/unspliced information is available

Methods:
- `scvelo`
- optional `CellRank` coupling

Planned canonical output:
- `published.scrna_velocity_h5ad`

### 8. `scverse_spatial`

Planned purpose:
- spatial transcriptomics / spatial single-cell analysis

Recommended stack:
- `spatialdata`
- `spatialdata-io`
- `squidpy`

Notes:
- dedicated environment
- separate dependency profile from core scRNA

### 9. `scverse_scatac`

Planned purpose:
- scATAC-seq analysis

Recommended stack:
- `SnapATAC2`
- optional `muon`

Core tasks:
- QC
- LSI / spectral embedding
- clustering
- DA peaks
- motif / gene activity

### 10. `scverse_multimodal`

Planned purpose:
- RNA + ATAC or RNA + protein analysis

Data model:
- `.h5mu`

Recommended stack:
- `mudata`
- `muon`
- selected `scvi-tools` multimodal models

Use cases:
- co-embedding
- cross-modality consistency
- cell type embedding checks
- modality-aware QC

## Config Strategy

Each template should use `config/project.toml` with explicit sections.

Recommended sections:
- `[project]`
- `[input]`
- `[metadata]`
- `[qc]`
- `[analysis]`
- `[annotation]`
- `[comparison]`
- `[plotting]`
- `[output]`

Use CSV sidecars where the content is genuinely tabular and user-edited:
- `config/samples.csv`
- `config/comparisons.csv`
- `config/group_map.csv`

## Environment Strategy

Do not force one `pixi.toml` to cover every modality.

Recommended split:
- one environment for core scRNA
- one environment for spatial
- one environment for ATAC / multimodal
- optional GPU-enabled variants where justified

Rationale:
- dependency solve times remain manageable
- spatial and multimodal packages evolve at different rates
- GPU-specific methods should remain optional

## Reporting Strategy

For QC and early-stage templates:
- prefer interactive figures first
- compare `before filtering` vs `after filtering` directly
- use one table with deltas rather than disconnected summaries

For publication-oriented outputs:
- keep the report readable and explanatory
- store machine-readable tables in `results/tables/`
- optionally add static figure exports later where publication layout requires them

## Publish-Key Strategy

Each template should publish one primary object path.

Recommended keys:
- `cellbender_corrected_matrix`
- `scrna_prep_h5ad`
- `scrna_integrated_h5ad`
- `scrna_annotated_h5ad`
- `scrna_trajectory_h5ad`
- `scrna_velocity_h5ad`
- `spatial_object`
- `scatac_h5ad`
- `multimodal_h5mu`

Downstream templates should prefer:
- explicit user input
- then the most specific upstream published object
- then broader generic upstream fallbacks

For each template, document the full input resolution order explicitly in the
template README and implement it in the pre-render hook rather than hiding it in
the notebook or run script.

## Cleanup Policy

Recommended default:
- keep canonical stage outputs
- remove only scratch and cache outputs

Examples safe to clean:
- `.quarto/`
- notebook caches
- temporary conversion files
- `results/tmp/`

Examples not safe to remove by default:
- `results/adata.prep.h5ad`
- `results/adata.integrated.h5ad`
- `results/adata.annotated.h5ad`
- `results/cellbender/cellbender_filtered.h5`

## Current Validation Status

### Already validated on real data

- `scverse_scrna_prep`
  - downloaded PBMC3K subset
  - full Pixi + Quarto execution path
  - real output assertions for:
    - `results/adata.prep.h5ad`
    - summary tables
    - rendered HTML report

### Implemented but still awaiting staged real validation

- `cellbender_remove_background`
  - structure and publish contract implemented
  - still needs a real CellBender run on raw droplet input

## Implementation Order

Recommended order from here:
1. stabilize and field-test `cellbender_remove_background`
2. implement `scverse_scrna_integrate`
3. add one more `scverse_scrna_prep` integration test for direct `10x_h5` or `10x_mtx`
4. implement `scverse_scrna_annotate`
5. implement `scverse_scrna_de`
6. implement trajectory / velocity
7. implement spatial
8. implement scATAC
9. implement multimodal

Reasoning:
- the prep-stage `.h5ad` contract is now in much better shape and already has a
  passing real-data integration test
- the next missing canonical handoff stage is integrated batch-corrected analysis

## Open Design Questions

- Whether future templates should consistently move canonical stage objects into
  `results/objects/` rather than template-specific top-level `results/*.h5ad`
- Whether `scverse_scrna_prep` should auto-discover more upstream raw matrix
  publish keys for CellBender input once `nfcore_scrnaseq` exposes them
- Which annotation reference management strategy should be used for `CellTypist`,
  `scANVI`, and custom atlases
- How much GPU-specific functionality should be facility-default versus optional
- Whether static publication exports should be generated in each template or only
  in later presentation/report templates

## Current Package Direction

The current ecosystem direction supports this design:
- `scanpy` and `anndata` remain the core stack
- `scvi-tools` is the strongest option for advanced integration and reference mapping
- `decoupler` is well suited for pathway and activity analysis
- `SpatialData` and `Squidpy` are the right basis for spatial work
- `SnapATAC2` is the leading scverse-aligned option for scATAC
- `MuData` / `muon` are the right multimodal containers
- `CellRank` and `scVelo` remain the main trajectory / velocity components
- `CellBender` is the main Python option for ambient/background correction
- `rapids-singlecell` should remain optional acceleration, not a hard dependency

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
- CellBender: <https://cellbender.readthedocs.io/>
- nf-core/scrnaseq outputs: <https://nf-co.re/scrnaseq/latest/docs/output>
