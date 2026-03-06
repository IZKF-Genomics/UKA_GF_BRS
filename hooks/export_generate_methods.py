from __future__ import annotations

from pathlib import Path
from typing import Any


def main(ctx: Any) -> str:
    """
    Post-render hook for template `export`.

    Generates a publication-oriented methods draft from project history and writes
    it into the export template directory. This keeps methods generation automatic
    when users render the export template.
    """
    if not getattr(ctx, "project", None):
        return "[hook:export_generate_methods] skipped (no project context)"

    enabled = bool(ctx.params.get("generate_methods_on_render", True))
    if not enabled:
        return "[hook:export_generate_methods] skipped (generate_methods_on_render=false)"

    style = str(ctx.params.get("methods_style") or "full").strip().lower()
    if style not in ("full", "concise"):
        style = "full"

    out_name = str(ctx.params.get("methods_output") or "auto_methods.md").strip()
    if not out_name:
        out_name = "auto_methods.md"

    out_path = Path(ctx.project_dir) / ctx.template.id / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from bpm.core import agent_methods

        result = agent_methods.generate_methods_markdown(Path(ctx.project_dir), style=style)
        out_path.write_text(result.markdown, encoding="utf-8")
        return (
            "[hook:export_generate_methods] wrote "
            f"{out_path} (templates={result.templates_count}, citations={result.citation_count}, style={style})"
        )
    except Exception as e:
        # Non-fatal: export rendering should still succeed even if methods generation fails.
        note = (
            "# Methods Draft\n\n"
            f"Automatic generation failed: {e}\n"
            "Run manually with:\n"
            f"`bpm agent methods --dir {ctx.project_dir} --style {style} --out {out_path}`\n"
        )
        out_path.write_text(note, encoding="utf-8")
        return f"[hook:export_generate_methods] warning: generation failed ({e}); wrote fallback note to {out_path}"

