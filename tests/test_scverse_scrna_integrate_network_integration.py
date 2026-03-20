from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
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
            name="PBMC3K integration smoke test",
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


def _render_scverse_scrna_integrate(out_dir: Path, input_h5ad: Path, integration_method: str) -> None:
    template_dir = Path("/data/shared/repos/UKA_GF_BRS/templates/scverse_scrna_integrate")
    params = {
        "input_h5ad": str(input_h5ad),
        "input_source_template": "manual",
        "integration_method": integration_method,
        "batch_key": "batch",
        "condition_key": "condition",
        "sample_id_key": "sample_id",
        "sample_label_key": "sample_display",
        "use_hvgs_only": True,
        "n_pcs": 20,
        "n_neighbors": 10,
        "harmony_theta": 2.0,
        "harmony_lambda": 1.0,
        "harmony_max_iter": 10,
        "bbknn_neighbors_within_batch": 3,
        "bbknn_trim": 0,
        "scanvi_label_key": "",
        "scanvi_unlabeled_category": "Unknown",
        "scvi_latent_dim": 10,
        "scvi_max_epochs": 5,
        "scvi_gene_likelihood": "zinb",
        "scvi_accelerator": "cpu",
        "scvi_devices": 1,
        "umap_min_dist": 0.5,
        "cluster_resolution": 0.5,
    }
    ctx = SimpleNamespace(
        project=SimpleNamespace(
            name=f"PBMC3K {integration_method} integration smoke test",
            authors=[SimpleNamespace(name="Codex")],
        ),
        project_dir=str(out_dir.parent),
        template=SimpleNamespace(id="scverse_scrna_integrate"),
        cwd=str(out_dir),
        params=params,
    )

    files = {
        "README.md": out_dir / "README.md",
        "pixi.toml": out_dir / "pixi.toml",
        "run.sh.j2": out_dir / "run.sh",
        ".gitignore": out_dir / ".gitignore",
        "config/project.toml.j2": out_dir / "config/project.toml",
        "00_integrate.qmd.j2": out_dir / "00_integrate.qmd",
    }
    for rel, dest in files.items():
        _render_template_file(template_dir / rel, dest, ctx)


def _write_pbmc3k_dataset_script(script_path: Path, output_h5ad: Path) -> None:
    script_path.write_text(
        "\n".join(
            [
                "import numpy as np",
                "import scanpy as sc",
                f"output = r'{output_h5ad}'",
                "adata = sc.datasets.pbmc3k()",
                "adata = adata[:400].copy()",
                "adata.obs['sample_id'] = np.where(np.arange(adata.n_obs) < 200, 'pbmc3k_a', 'pbmc3k_b')",
                "adata.obs['sample_display'] = adata.obs['sample_id']",
                "adata.obs['batch'] = np.where(np.arange(adata.n_obs) < 200, 'batch1', 'batch2')",
                "adata.obs['condition'] = np.where(np.arange(adata.n_obs) < 200, 'control', 'treated')",
                "adata.layers['counts'] = adata.X.copy()",
                "adata.write_h5ad(output)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.skipif(
    not RUN_NETWORK_TESTS,
    reason="Set UKA_BRS_RUN_NETWORK_TESTS=1 to run real-data integration tests.",
)
@pytest.mark.parametrize("integration_method", ["harmony", "scvi"])
def test_scverse_scrna_integrate_runs_on_real_pbmc3k_subset(tmp_path: Path, integration_method: str):
    prep_dir = tmp_path / "scverse_scrna_prep"
    integrate_dir = tmp_path / f"scverse_scrna_integrate_{integration_method}"
    prep_dir.mkdir(parents=True, exist_ok=True)
    integrate_dir.mkdir(parents=True, exist_ok=True)

    input_h5ad = prep_dir / "pbmc3k_subset.h5ad"
    dataset_script = prep_dir / "make_pbmc3k_subset.py"

    _render_scverse_scrna_prep(prep_dir, input_h5ad)
    _write_pbmc3k_dataset_script(dataset_script, input_h5ad)

    subprocess.run(["pixi", "install"], cwd=prep_dir, check=True)
    subprocess.run(["pixi", "run", "python", str(dataset_script)], cwd=prep_dir, check=True)
    subprocess.run(["bash", "run.sh"], cwd=prep_dir, check=True, timeout=3600)

    prep_output = prep_dir / "results/adata.prep.h5ad"
    assert prep_output.exists()

    _render_scverse_scrna_integrate(integrate_dir, prep_output, integration_method)
    subprocess.run(["pixi", "install"], cwd=integrate_dir, check=True)
    subprocess.run(["bash", "run.sh"], cwd=integrate_dir, check=True, timeout=7200)

    integration_summary = pd.read_csv(integrate_dir / "results/tables/integration_summary.csv")
    summary_map = dict(zip(integration_summary["field"], integration_summary["value"], strict=False))

    assert (integrate_dir / "results/adata.integrated.h5ad").exists()
    assert (integrate_dir / "results/tables/batch_mixing_summary.csv").exists()
    assert (integrate_dir / "00_integrate.html").exists()
    assert summary_map["integration_method"] == integration_method
    assert summary_map["input_source_template"] == "manual"
