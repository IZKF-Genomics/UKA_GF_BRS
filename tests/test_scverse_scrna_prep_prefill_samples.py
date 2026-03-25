from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


def _add_repo_root_to_syspath():
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def test_prefill_samples_from_nfcore_samplesheet(tmp_path: Path):
    project_dir = tmp_path / "project"
    render_dir = project_dir / "scverse_scrna_prep" / "config"
    nfcore_dir = project_dir / "nfcore_scrnaseq"
    render_dir.mkdir(parents=True)
    nfcore_dir.mkdir(parents=True)

    samplesheet = nfcore_dir / "samplesheet.csv"
    samplesheet.write_text(
        "sample,fastq_1,fastq_2\n"
        "Tumor_A,a_R1.fastq.gz,a_R2.fastq.gz\n"
        "Tumor_B,b_R1.fastq.gz,b_R2.fastq.gz\n"
        "Tumor_A,a2_R1.fastq.gz,a2_R2.fastq.gz\n",
        encoding="utf-8",
    )
    (render_dir / "samples.csv").write_text(
        "sample_id,sample_label,batch,condition,patient_id,notes\n"
        "Tumor_A,Renamed A,,,P1,\n",
        encoding="utf-8",
    )
    (project_dir / "project.yaml").write_text(
        f"""
name: Demo scRNA
templates:
  - id: nfcore_scrnaseq
    published:
      nfcore_samplesheet: nextgen:{samplesheet}
""",
        encoding="utf-8",
    )

    _add_repo_root_to_syspath()

    from hooks.scverse_scrna_prep_prefill_samples import main  # type: ignore

    ctx = SimpleNamespace(
        project=SimpleNamespace(project_path=str(project_dir), name="Demo scRNA"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="scverse_scrna_prep"),
        materialize=lambda p: str(p).replace("nextgen:", ""),
    )

    result = main(ctx)

    content = (render_dir / "samples.csv").read_text(encoding="utf-8").splitlines()
    assert "Tumor_A,Renamed A,,,P1," in content
    assert "Tumor_B,Tumor_B,,,," in content
    assert "added=1" in result


def test_prefill_samples_from_direct_input_path(tmp_path: Path):
    project_dir = tmp_path / "project"
    render_dir = project_dir / "scverse_scrna_prep" / "config"
    matrix_dir = project_dir / "cellranger" / "Tumor_C" / "filtered_feature_bc_matrix"
    render_dir.mkdir(parents=True)
    matrix_dir.mkdir(parents=True)

    (render_dir / "samples.csv").write_text(
        "sample_id,sample_label,batch,condition,patient_id,notes\n",
        encoding="utf-8",
    )
    (project_dir / "project.yaml").write_text(
        "name: Demo scRNA\n",
        encoding="utf-8",
    )

    _add_repo_root_to_syspath()

    from hooks.scverse_scrna_prep_prefill_samples import main  # type: ignore

    ctx = SimpleNamespace(
        params={"input_matrix": str(matrix_dir)},
        project=SimpleNamespace(project_path=str(project_dir), name="Demo scRNA"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="scverse_scrna_prep"),
        materialize=lambda p: str(p),
    )

    result = main(ctx)

    content = (render_dir / "samples.csv").read_text(encoding="utf-8").splitlines()
    assert "Tumor_C,Tumor_C,,,," in content
    assert "source=input_matrix_or_h5ad" in result


def test_prefill_samples_from_per_sample_outs_dir(tmp_path: Path):
    project_dir = tmp_path / "project"
    render_dir = project_dir / "scverse_scrna_prep" / "config"
    per_sample_outs = project_dir / "cellranger" / "Exp3" / "outs" / "per_sample_outs"
    render_dir.mkdir(parents=True)
    for sample_id in ("WT", "Pkp2_het", "Pkp2_Mut"):
        (per_sample_outs / sample_id / "count").mkdir(parents=True)

    (render_dir / "samples.csv").write_text(
        "sample_id,sample_label,batch,condition,patient_id,notes\n",
        encoding="utf-8",
    )
    (project_dir / "project.yaml").write_text(
        "name: Demo scRNA\n",
        encoding="utf-8",
    )

    _add_repo_root_to_syspath()

    from hooks.scverse_scrna_prep_prefill_samples import main  # type: ignore

    ctx = SimpleNamespace(
        params={"input_matrix": str(per_sample_outs)},
        project=SimpleNamespace(project_path=str(project_dir), name="Demo scRNA"),
        project_dir=str(project_dir),
        template=SimpleNamespace(id="scverse_scrna_prep"),
        materialize=lambda p: str(p),
    )

    result = main(ctx)

    content = (render_dir / "samples.csv").read_text(encoding="utf-8").splitlines()
    assert "WT,WT,,,," in content
    assert "Pkp2_het,Pkp2_het,,,," in content
    assert "Pkp2_Mut,Pkp2_Mut,,,," in content
    assert "total_rows=3" in result
