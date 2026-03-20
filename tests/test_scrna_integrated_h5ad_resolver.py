from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


def test_resolver_returns_host_aware_integrated_h5ad(tmp_path: Path):
    project_root = tmp_path / "project"
    run_dir = project_root / "scverse_scrna_integrate"
    out = run_dir / "results" / "adata.integrated.h5ad"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("dummy", encoding="utf-8")

    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from resolvers.get_scrna_integrated_h5ad import main  # type: ignore

    ctx = SimpleNamespace(
        project=True,
        project_dir=str(project_root),
        template=SimpleNamespace(id="scverse_scrna_integrate"),
        cwd=str(run_dir),
        hostname=lambda: "nextgen",
        materialize=lambda p: str(p).replace("nextgen:/data/projects/demo", str(project_root)),
    )
    ctx.project = SimpleNamespace(project_path="nextgen:/data/projects/demo")

    resolved = main(ctx)
    assert resolved == "nextgen:/data/projects/demo/scverse_scrna_integrate/results/adata.integrated.h5ad"
