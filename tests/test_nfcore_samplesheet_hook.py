"""
Unit-style test for the nfcore rnaseq samplesheet hook (reverse-stranded).

This does not run Nextflow. It creates a fake FASTQ directory and project.yaml,
then calls the hook to generate samplesheet.csv in a temp folder.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


def test_hook_generates_samplesheet(tmp_path: Path):
    # Arrange: fake FASTQ inputs
    fq_dir = tmp_path / "fastq"
    fq_dir.mkdir()
    # Create minimal paired files (empty content is fine)
    (fq_dir / "S1_R1_001.fastq.gz").write_text("")
    (fq_dir / "S1_R2_001.fastq.gz").write_text("")

    # Fake project with published FASTQ_dir pointing to our fixture
    prj = tmp_path / "project"
    prj.mkdir()
    (prj / "project.yaml").write_text(
        f"""
name: TEST
project_path: {prj}
templates:
  - id: demux_bclconvert
    published:
      FASTQ_dir: {fq_dir}
"""
    )

    # Make BRS root importable for hooks.* module resolution
    # Expect this test to run from the repo root
    brs_root = Path.cwd() / "UKA_GF_BRS"
    sys.path.insert(0, str(brs_root))

    # Import the hook
    from hooks.nfcore_rnaseq_samplesheet_reverse import main as hook_main  # type: ignore

    # Act: call hook with ctx shape used by BPM
    ctx = SimpleNamespace(project_dir=str(prj), cwd=str(tmp_path))
    out = hook_main(ctx)

    # Assert
    outp = Path(out)
    assert outp.exists(), "samplesheet.csv should be created"
    content = outp.read_text().splitlines()
    assert content[0].startswith("sample,fastq_1,fastq_2"), "CSV header missing"
    assert any("S1_R1_001.fastq.gz" in line for line in content[1:]), "R1 path missing in CSV"

