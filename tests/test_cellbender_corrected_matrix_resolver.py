from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


def test_cellbender_corrected_matrix_resolver_returns_project_host_path(tmp_path: Path):
    project_dir = tmp_path / "project"
    run_dir = project_dir / "cellbender_remove_background" / "results" / "cellbender"
    run_dir.mkdir(parents=True)
    out = run_dir / "cellbender_filtered.h5"
    out.write_text("placeholder", encoding="utf-8")

    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from resolvers.get_cellbender_corrected_matrix import main  # type: ignore

    ctx = SimpleNamespace(
        project=SimpleNamespace(project_path="nextgen:/data/projects/demo"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="cellbender_remove_background"),
        cwd=str(project_dir / "cellbender_remove_background"),
        hostname=lambda: "nextgen",
        materialize=lambda p: str(project_dir) if str(p) == "nextgen:/data/projects/demo" else str(p).replace("nextgen:", ""),
    )

    resolved = main(ctx)

    assert resolved == "nextgen:/data/projects/demo/cellbender_remove_background/results/cellbender/cellbender_filtered.h5"
