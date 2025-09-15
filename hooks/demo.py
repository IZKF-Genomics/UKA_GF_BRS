from __future__ import annotations
from pathlib import Path
from typing import Any

def _out_dir(ctx: Any) -> Path:
    return Path(ctx.project_dir) / ctx.template.id

def post_render(ctx: Any) -> str:
    out = _out_dir(ctx)
    out.mkdir(parents=True, exist_ok=True)
    # Create a simple stamp file to show the hook ran
    (out / ".post_render.stamp").write_text("post_render ok\n")
    return f"post_render: prepared {out}"

def pre_run(ctx: Any) -> str:
    # Example validation
    threads = int(ctx.params.get("threads", 1))
    if threads < 1:
        raise ValueError("threads must be >= 1")
    return f"pre_run: threads={threads}"

def post_run(ctx: Any) -> str:
    out = _out_dir(ctx)
    results = out / "results.txt"
    if not results.exists():
        raise FileNotFoundError(f"Expected results.txt at {results}")
    # Leave a marker for demonstration purposes
    (out / ".post_run.stamp").write_text("post_run ok\n")
    return f"post_run: verified {results}"
