from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from bpm.core import brs_loader
from bpm.io.yamlio import safe_load_yaml


def _load_project_templates(project_dir: Path) -> List[str]:
    project_path = project_dir / "project.yaml"
    if not project_path.exists():
        return []
    data = safe_load_yaml(project_path)
    return [t.get("id") for t in (data.get("templates") or []) if t.get("id")]


def _load_published_outputs(project_dir: Path) -> Dict[str, Dict[str, Any]]:
    project_path = project_dir / "project.yaml"
    if not project_path.exists():
        return {}
    data = safe_load_yaml(project_path)
    published: Dict[str, Dict[str, Any]] = {}
    for entry in data.get("templates") or []:
        tpl_id = entry.get("id")
        if not tpl_id:
            continue
        published[tpl_id] = entry.get("published") or {}
    return published


def _render_target_dir(template: str, target_dir: str, export_root: str) -> str:
    return (
        target_dir.replace("{export_root}", export_root).replace("{template_id}", template)
    )


def main(ctx: Any) -> Dict[str, Any]:
    """
    Build export_mapping.seed.yaml from the table and the project's used templates.
    """
    try:
        import yaml
    except Exception as exc:
        raise RuntimeError(f"PyYAML is required to build export mapping: {exc}") from exc

    paths = brs_loader.get_paths()
    table_path = paths.templates_dir / "export" / "export_mapping.table.yaml"
    table = safe_load_yaml(table_path)

    mappings = table.get("mappings") or []
    if not isinstance(mappings, list):
        raise ValueError("export_mapping.table.yaml must contain a 'mappings' list")

    project_dir = Path(ctx.project_dir)
    used_templates = _load_project_templates(project_dir) if ctx.project else []
    published = _load_published_outputs(project_dir) if ctx.project else {}

    export_root = str(ctx.params.get("export_root", "/export"))

    export_structure: List[list] = []
    included_templates: List[str] = []

    for entry in mappings:
        if not isinstance(entry, dict):
            continue
        tpl_id = entry.get("template_id")
        if not tpl_id or tpl_id == "export":
            continue
        if used_templates and tpl_id not in used_templates:
            continue

        section = entry.get("section")
        source_path = entry.get("source_path")
        published_key = entry.get("source_published_key")
        if isinstance(published_key, str) and ctx.project:
            pub_map = published.get(tpl_id) or {}
            pub_val = pub_map.get(published_key)
            if isinstance(pub_val, str) and pub_val:
                source_path = ctx.materialize(pub_val)

        target_dir = entry.get("target_dir")
        if not isinstance(section, str) or not isinstance(source_path, str):
            continue
        if not isinstance(target_dir, str):
            continue

        target_dir = _render_target_dir(tpl_id, target_dir, export_root)
        rename = entry.get("rename")

        export_structure.append([section, source_path, target_dir, rename])
        if tpl_id not in included_templates:
            included_templates.append(tpl_id)

    # Determine output folder: project mode -> <project_dir>/<template_id>
    # Ad-hoc mode -> ctx.cwd
    if ctx.project:
        out_dir = project_dir / ctx.template.id
    else:
        out_dir = Path(ctx.cwd)
    out_dir.mkdir(parents=True, exist_ok=True)

    seed = {
        "available_templates": included_templates,
        "export_structure": export_structure,
        "export_engine": {
            "api_url": ctx.params.get("export_engine_api_url"),
            "backends": ctx.params.get("export_engine_backends"),
        },
    }

    seed_path = out_dir / "export_mapping.seed.yaml"
    seed_path.write_text(yaml.safe_dump(seed, sort_keys=False))
    return seed
