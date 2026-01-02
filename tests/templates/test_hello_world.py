from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import tempfile

import pytest


def test_hello_world_renders() -> None:
    bpm = shutil.which("bpm")
    if not bpm:
        pytest.skip("bpm CLI not found on PATH")

    repo_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / "project"
        cache_dir = Path(tmpdir) / "bpm_cache"
        project_dir.mkdir()
        (project_dir / "project.yaml").write_text(
            f"name: TEST\nproject_path: {project_dir}\n"
        )

        env = os.environ.copy()
        env["BPM_CACHE"] = str(cache_dir)

        subprocess.run(
            [bpm, "resource", "add", str(repo_root), "--activate"],
            cwd=str(repo_root),
            check=True,
            text=True,
            env=env,
        )

        subprocess.run(
            [
                bpm,
                "template",
                "render",
                "hello_world",
                "--dir",
                str(project_dir),
                "--param",
                "name=Joseph",
            ],
            cwd=str(repo_root),
            check=True,
            text=True,
            env=env,
        )

        rendered = project_dir / "hello_world" / "run.sh"
        assert rendered.exists(), "run.sh should be rendered in ad-hoc output"
        content = rendered.read_text()
        assert "Hello Joseph!" in content
        assert "This project is TEST" in content

        adhoc_dir = Path(tmpdir) / "adhoc"
        adhoc_dir.mkdir()
        subprocess.run(
            [
                bpm,
                "template",
                "render",
                "hello_world",
                "--ad-hoc",
                "--out",
                str(adhoc_dir),
                "--param",
                "name=Joseph",
            ],
            cwd=str(repo_root),
            check=True,
            text=True,
            env=env,
        )
        adhoc_rendered = adhoc_dir / "run.sh"
        assert adhoc_rendered.exists(), "run.sh should be rendered in ad-hoc output"
        adhoc_content = adhoc_rendered.read_text()
        assert "Hello Joseph!" in adhoc_content
        assert "This project is (ad-hoc)" in adhoc_content
