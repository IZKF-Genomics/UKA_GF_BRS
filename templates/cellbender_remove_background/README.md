# cellbender_remove_background


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: cellbender_remove_background
kind: template
description: Optional CellBender ambient RNA correction for raw droplet scRNA-seq
  matrices.
descriptor: templates/cellbender_remove_background/template_config.yaml
required_params:
- input_raw_matrix
optional_params:
- epochs
- expected_cells
- fpr
- input_format
- low_count_threshold
- total_droplets_included
- use_cuda
run_entry: run.sh
publish_keys:
- cellbender_corrected_matrix
render_file_count: 6
```
<!-- AGENT_METADATA_END -->

Optional upstream ambient RNA correction template based on CellBender.

Scope:
- consume a raw droplet matrix, typically a raw 10x HDF5 matrix
- run `cellbender remove-background`
- publish the corrected matrix for downstream templates
- render a minimal run summary

Current input contract:
- `input_raw_matrix` should point to a raw 10x HDF5 matrix such as `raw_feature_bc_matrix.h5`
- host-prefixed project paths are materialized during render
- `input_format` is currently restricted to `10x_h5`

## Render

```bash
bpm template render cellbender_remove_background \
  --param input_raw_matrix=/path/to/raw_feature_bc_matrix.h5 \
  --dir /path/to/project
```

Common overrides:

```bash
bpm template render cellbender_remove_background \
  --param input_raw_matrix=/path/to/raw_feature_bc_matrix.h5 \
  --param expected_cells=12000 \
  --param total_droplets_included=25000 \
  --param fpr=0.01 \
  --param use_cuda=true \
  --dir /path/to/project
```

If your matrix path in `project.yaml` uses a host prefix such as `nextgen:/...`, the
pre-render hook materializes it into the local filesystem path used by the run script.

## Run

```bash
bpm template run cellbender_remove_background --dir /path/to/project
# or inside rendered folder
./run.sh
```

## Outputs

- `results/cellbender/cellbender_filtered.h5`: corrected matrix published for downstream use
- `00_summary.html`: minimal run summary and output presence check

Published output:
- `cellbender_corrected_matrix`: resolver-backed path to `results/cellbender/cellbender_filtered.h5`

## Notes

- This template is intended for raw droplet inputs, not downstream filtered `.h5ad` objects.
- BPM publishing is enabled through the `cellbender_corrected_matrix` publish key, so
  after `bpm template run cellbender_remove_background --dir <project>`, the resulting
  HDF5 path is written to `project.yaml` under
  `templates[].published.cellbender_corrected_matrix`.
- `scverse_scrna_prep` prefers this published output over `nfcore_scrnaseq_res_mt` when both are present.
- The current scaffold is intentionally minimal; diagnostics and automatic raw-matrix discovery can be added once real project runs are validated.
