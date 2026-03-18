from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


def test_hook_populates_input_h5ad_and_project_defaults(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text(
        """
name: Demo scRNA
authors:
  - name: Ada Lovelace
templates:
  - id: nfcore_scrnaseq
    published:
      nfcore_scrnaseq_res_mt: nextgen:/data/projects/demo/nfcore_scrnaseq/results/cellranger/mtx_conversions/combined_filtered_matrix.h5ad
""",
        encoding="utf-8",
    )

    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from hooks.scverse_scrna_prep_defaults import populate  # type: ignore

    ctx = SimpleNamespace(
        params={"input_h5ad": "", "sample_metadata": ""},
        project=SimpleNamespace(project_path=str(project_dir), name="Demo scRNA"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="scverse_scrna_prep"),
        materialize=lambda p: str(p).replace("nextgen:", ""),
    )

    populate(ctx)

    assert ctx.params["input_h5ad"] == "/data/projects/demo/nfcore_scrnaseq/results/cellranger/mtx_conversions/combined_filtered_matrix.h5ad"
