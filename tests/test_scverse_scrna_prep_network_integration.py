from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Template


RUN_NETWORK_TESTS = os.environ.get("UKA_BRS_RUN_NETWORK_TESTS") == "1"


def _render_template_file(src: Path, dest: Path, ctx: SimpleNamespace) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix == ".j2":
        rendered = Template(src.read_text(encoding="utf-8")).render(ctx=ctx)
        dest.write_text(rendered, encoding="utf-8")
        if dest.name == "run.sh":
            dest.chmod(0o755)
        return
    shutil.copy2(src, dest)


def _render_scverse_scrna_prep(out_dir: Path, input_h5ad: Path) -> None:
    template_dir = Path("/data/shared/repos/UKA_GF_BRS/templates/scverse_scrna_prep")
    ctx = SimpleNamespace(
        project=SimpleNamespace(
            name="PBMC3K smoke test",
            authors=[SimpleNamespace(name="Codex")],
        ),
        project_dir=str(out_dir.parent),
        template=SimpleNamespace(id="scverse_scrna_prep"),
        cwd=str(out_dir),
        params={
            "input_h5ad": "",
            "input_matrix": str(input_h5ad),
            "input_source_template": "manual",
            "ambient_correction_applied": False,
            "ambient_correction_method": "none",
            "input_format": "h5ad",
            "var_names": "gene_symbols",
            "sample_metadata": "",
            "organism": "human",
            "sample_id_key": "sample_id",
            "batch_key": "batch",
            "condition_key": "condition",
            "doublet_method": "none",
            "filter_predicted_doublets": False,
            "qc_mode": "fixed",
            "qc_nmads": 3.0,
            "min_genes": 50,
            "min_cells": 3,
            "min_counts": 100,
            "max_pct_counts_mt": 30.0,
            "max_pct_counts_ribo": "",
            "max_pct_counts_hb": "",
            "n_top_hvgs": 1000,
            "n_pcs": 20,
            "n_neighbors": 10,
            "leiden_resolution": "",
            "resolution_grid": "0.2,0.4,0.6",
        },
    )

    files = {
        "README.md": out_dir / "README.md",
        "pixi.toml": out_dir / "pixi.toml",
        "run.sh.j2": out_dir / "run.sh",
        ".gitignore": out_dir / ".gitignore",
        "config/project.toml.j2": out_dir / "config/project.toml",
        "config/samples.csv": out_dir / "config/samples.csv",
        "00_qc.qmd.j2": out_dir / "00_qc.qmd",
    }
    for rel, dest in files.items():
        _render_template_file(template_dir / rel, dest, ctx)


@pytest.mark.skipif(not RUN_NETWORK_TESTS, reason="Set UKA_BRS_RUN_NETWORK_TESTS=1 to run real-data integration tests.")
def test_scverse_scrna_prep_runs_on_real_downloaded_pbmc3k_subset(tmp_path: Path):
    run_dir = tmp_path / "scverse_scrna_prep"
    run_dir.mkdir(parents=True, exist_ok=True)
    input_h5ad = run_dir / "pbmc3k_subset.h5ad"

    _render_scverse_scrna_prep(run_dir, input_h5ad)

    # Install the exact Pixi environment used by the template first, then create
    # a small H5AD from a real internet-downloaded dataset using that same stack.
    subprocess.run(["pixi", "install"], cwd=run_dir, check=True)
    subprocess.run(
        [
            "pixi",
            "run",
            "python",
            "-c",
            (
                "import scanpy as sc; "
                "adata = sc.datasets.pbmc3k(); "
                "adata = adata[:400].copy(); "
                "adata.obs['sample_id'] = 'pbmc3k'; "
                "adata.obs['batch'] = 'batch1'; "
                "adata.obs['condition'] = 'control'; "
                "adata.layers['counts'] = adata.X.copy(); "
                f"adata.write_h5ad(r'{input_h5ad}')"
            ),
        ],
        cwd=run_dir,
        check=True,
    )

    subprocess.run(["bash", "run.sh"], cwd=run_dir, check=True, timeout=3600)

    assert input_h5ad.exists()
    assert (run_dir / "results/adata.prep.h5ad").exists()
    assert (run_dir / "results/tables/qc_summary.csv").exists()
    assert (run_dir / "00_qc.html").exists()
