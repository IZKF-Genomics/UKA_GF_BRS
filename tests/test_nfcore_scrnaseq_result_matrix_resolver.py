from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


def test_resolver_prefers_combined_filtered_matrix(tmp_path: Path):
    project_dir = tmp_path / "project"
    template_dir = project_dir / "nfcore_scrnaseq" / "results" / "cellranger" / "mtx_conversions"
    template_dir.mkdir(parents=True)

    (template_dir / "combined_raw_matrix.h5ad").write_text("")
    best = template_dir / "combined_filtered_matrix.h5ad"
    best.write_text("")
    (template_dir / "sample1_filtered_matrix.h5ad").write_text("")

    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from resolvers.get_scrnaseq_result_matrix import main as resolver_main  # type: ignore

    ctx = SimpleNamespace(
        project=SimpleNamespace(project_path=str(project_dir)),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="nfcore_scrnaseq"),
        hostname=lambda: "testhost",
        materialize=lambda p: str(project_dir),
    )
    out = resolver_main(ctx)

    assert out.endswith("/nfcore_scrnaseq/results/cellranger/mtx_conversions/combined_filtered_matrix.h5ad")
