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
    params:
      organism: hsapiens
    published:
      nfcore_scrnaseq_res_mt: nextgen:/data/projects/demo/nfcore_scrnaseq/results/cellranger/mtx_conversions/combined_filtered_matrix.h5ad
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
        params={
            "input_h5ad": "",
            "input_matrix": "",
            "input_format": "",
            "sample_metadata": "",
            "input_source_template": "",
            "ambient_correction_applied": None,
            "ambient_correction_method": "",
        },
        project=SimpleNamespace(project_path=str(project_dir), name="Demo scRNA"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="scverse_scrna_prep"),
        materialize=lambda p: str(p).replace("nextgen:", ""),
    )

    populate(ctx)

    assert ctx.params["input_h5ad"] == "/data/projects/demo/nfcore_scrnaseq/results/cellranger/mtx_conversions/combined_filtered_matrix.h5ad"
    assert ctx.params["input_matrix"] == ""
    assert ctx.params["input_format"] == "auto"
    assert ctx.params["organism"] == "hsapiens"
    assert ctx.params["input_source_template"] == "nfcore_scrnaseq"
    assert ctx.params["ambient_correction_applied"] is False
    assert ctx.params["ambient_correction_method"] == "none"


def test_hook_maps_genome_to_organism_when_organism_missing(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text(
        """
name: Demo scRNA
templates:
  - id: nfcore_scrnaseq
    params:
      genome: GRCm39
    published:
      nfcore_scrnaseq_res_mt: nextgen:/data/projects/demo/nfcore_scrnaseq/results/cellranger/mtx_conversions/combined_filtered_matrix.h5ad
""",
        encoding="utf-8",
    )

    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from hooks.scverse_scrna_prep_defaults import populate  # type: ignore

    ctx = SimpleNamespace(
        params={
            "input_h5ad": "",
            "input_matrix": "",
            "input_format": "",
            "sample_metadata": "",
            "organism": "",
            "input_source_template": "",
            "ambient_correction_applied": None,
            "ambient_correction_method": "",
        },
        project=SimpleNamespace(project_path=str(project_dir), name="Demo scRNA"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="scverse_scrna_prep"),
        materialize=lambda p: str(p).replace("nextgen:", ""),
    )

    populate(ctx)

    assert ctx.params["organism"] == "mmusculus"


def test_hook_prefers_cellbender_output_when_available(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text(
        """
name: Demo scRNA
templates:
  - id: nfcore_scrnaseq
    published:
      nfcore_scrnaseq_res_mt: nextgen:/data/projects/demo/nfcore_scrnaseq/results/cellranger/mtx_conversions/combined_filtered_matrix.h5ad
  - id: cellbender_remove_background
    published:
      cellbender_corrected_matrix: nextgen:/data/projects/demo/cellbender_remove_background/results/cellbender/cellbender_filtered.h5
""",
        encoding="utf-8",
    )

    brs_root = Path("/data/shared/repos/UKA_GF_BRS")
    sys.path.insert(0, str(brs_root))

    from hooks.scverse_scrna_prep_defaults import populate  # type: ignore

    ctx = SimpleNamespace(
        params={
            "input_h5ad": "",
            "input_matrix": "",
            "input_format": "",
            "sample_metadata": "",
            "organism": "",
            "input_source_template": "",
            "ambient_correction_applied": None,
            "ambient_correction_method": "",
        },
        project=SimpleNamespace(project_path=str(project_dir), name="Demo scRNA"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="scverse_scrna_prep"),
        materialize=lambda p: str(p).replace("nextgen:", ""),
    )

    populate(ctx)

    assert ctx.params["input_h5ad"] == "/data/projects/demo/cellbender_remove_background/results/cellbender/cellbender_filtered.h5"
    assert ctx.params["input_source_template"] == "cellbender_remove_background"
    assert ctx.params["ambient_correction_applied"] is True
    assert ctx.params["ambient_correction_method"] == "cellbender"
