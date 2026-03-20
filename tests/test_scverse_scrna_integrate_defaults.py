from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


def test_hook_populates_input_h5ad_from_scverse_scrna_prep(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text(
        """
name: Demo integration
templates:
  - id: scverse_scrna_prep
    published:
      scrna_prep_h5ad: nextgen:/data/projects/demo/scverse_scrna_prep/results/adata.prep.h5ad
""",
        encoding="utf-8",
    )

    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from hooks.scverse_scrna_integrate_defaults import populate  # type: ignore

    ctx = SimpleNamespace(
        params={
            "input_h5ad": "",
            "input_source_template": "",
        },
        project=SimpleNamespace(project_path=str(project_dir), name="Demo integration"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="scverse_scrna_integrate"),
        materialize=lambda p: str(p).replace("nextgen:", ""),
    )

    populate(ctx)

    assert ctx.params["input_h5ad"] == "/data/projects/demo/scverse_scrna_prep/results/adata.prep.h5ad"
    assert ctx.params["input_source_template"] == "scverse_scrna_prep"


def test_hook_materializes_explicit_input_overrides(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text("name: Demo integration\n", encoding="utf-8")

    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from hooks.scverse_scrna_integrate_defaults import populate  # type: ignore

    ctx = SimpleNamespace(
        params={
            "input_h5ad": "nextgen:/data/projects/demo/input.h5ad",
            "input_source_template": "",
        },
        project=SimpleNamespace(project_path=str(project_dir), name="Demo integration"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="scverse_scrna_integrate"),
        materialize=lambda p: str(p).replace("nextgen:", ""),
    )

    populate(ctx)

    assert ctx.params["input_h5ad"] == "/data/projects/demo/input.h5ad"
    assert ctx.params["input_source_template"] == "manual"
