"""
Pre-render hook for cellbender_remove_background.

- Materialize host-prefixed raw matrix paths into local filesystem paths
- Enforce the currently supported input contract
"""

from __future__ import annotations


def _needs_fill(val) -> bool:
    return val is None or (isinstance(val, str) and val.strip() == "")


def populate(ctx) -> None:
    params = ctx.params

    raw_matrix = str(params.get("input_raw_matrix", "")).strip()
    if not raw_matrix:
        raise RuntimeError("input_raw_matrix is required")

    try:
        params["input_raw_matrix"] = str(ctx.materialize(raw_matrix))
    except Exception:
        params["input_raw_matrix"] = raw_matrix

    input_format = str(params.get("input_format", "")).strip().lower()
    if _needs_fill(input_format):
        input_format = "10x_h5"
        params["input_format"] = input_format

    if input_format != "10x_h5":
        raise RuntimeError(
            "cellbender_remove_background currently supports only input_format=10x_h5. "
            "Provide a raw 10x HDF5 matrix such as raw_feature_bc_matrix.h5."
        )
