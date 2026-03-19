from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


def test_hook_materializes_host_prefixed_input_and_defaults_format(tmp_path: Path):
    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from hooks.cellbender_remove_background_defaults import populate  # type: ignore

    ctx = SimpleNamespace(
        params={"input_raw_matrix": "nextgen:/data/projects/demo/raw_feature_bc_matrix.h5", "input_format": ""},
        materialize=lambda p: str(p).replace("nextgen:", ""),
    )

    populate(ctx)

    assert ctx.params["input_raw_matrix"] == "/data/projects/demo/raw_feature_bc_matrix.h5"
    assert ctx.params["input_format"] == "10x_h5"


def test_hook_rejects_unsupported_input_format(tmp_path: Path):
    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from hooks.cellbender_remove_background_defaults import populate  # type: ignore

    ctx = SimpleNamespace(
        params={"input_raw_matrix": "/data/projects/demo/raw_feature_bc_matrix", "input_format": "10x_mtx"},
        materialize=lambda p: str(p),
    )

    try:
        populate(ctx)
    except RuntimeError as exc:
        assert "currently supports only input_format=10x_h5" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for unsupported input_format")
