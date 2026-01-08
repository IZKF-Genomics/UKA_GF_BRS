from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Tuple

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


def _load_project_authors(project_dir: Path) -> List[str]:
    project_path = project_dir / "project.yaml"
    if not project_path.exists():
        return []
    data = safe_load_yaml(project_path)
    authors = data.get("authors") or []
    if isinstance(authors, list):
        formatted: List[str] = []
        for entry in authors:
            if isinstance(entry, dict):
                name = entry.get("name")
                affiliation = entry.get("affiliation")
                if name and affiliation:
                    formatted.append(f"{name}, {affiliation}")
                elif name:
                    formatted.append(str(name))
            elif isinstance(entry, str):
                formatted.append(entry)
        return [a for a in formatted if a]
    return []


def _load_export_job_id(project_dir: Path) -> str:
    project_path = project_dir / "project.yaml"
    if not project_path.exists():
        return ""
    data = safe_load_yaml(project_path)
    for entry in data.get("templates") or []:
        if entry.get("id") == "export":
            published = entry.get("published") or {}
            job_id = published.get("export_job_id")
            if isinstance(job_id, str):
                return job_id
    return ""


def _split_host(path_str: str, default_host: str) -> Tuple[str, str]:
    if ":" in path_str:
        host, rest = path_str.split(":", 1)
    else:
        host, rest = default_host, path_str
    if not rest.startswith("/"):
        rest = f"/{rest}"
    return host, rest


def _render_target_dir(template: str, target_dir: str) -> str:
    return target_dir.replace("{template_id}", template)


def _split_csv(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = [v.strip() for v in value.split(",")]
        return [v for v in parts if v]
    return [str(value)]


def main(ctx: Any) -> Dict[str, Any]:
    """
    Build export_job_spec.json from the mapping table and project state.
    """
    paths = brs_loader.get_paths()
    table_path = paths.templates_dir / "export" / "export_mapping.table.yaml"
    table = safe_load_yaml(table_path)

    mappings = table.get("mappings") or []
    if not isinstance(mappings, list):
        raise ValueError("export_mapping.table.yaml must contain a 'mappings' list")

    project_dir = Path(ctx.project_dir)
    used_templates = _load_project_templates(project_dir) if ctx.project else []
    published = _load_published_outputs(project_dir) if ctx.project else {}
    project_authors = _load_project_authors(project_dir) if ctx.project else []
    export_job_id = _load_export_job_id(project_dir) if ctx.project else ""

    include_in_report = True

    export_list: List[Dict[str, Any]] = []

    for entry in mappings:
        if not isinstance(entry, dict):
            continue
        tpl_id = entry.get("template_id")
        if not tpl_id or tpl_id == "export":
            continue
        if ctx.project and tpl_id not in used_templates:
            continue

        source_path = entry.get("src")
        published_key = entry.get("src_published_key")
        host = entry.get("host") or ctx.hostname()
        project_host, _ = _split_host(ctx.project.project_path, host) if ctx.project else (host, "")
        project_root = Path(ctx.materialize(ctx.project.project_path)) if ctx.project else None

        if isinstance(published_key, str) and ctx.project:
            pub_map = published.get(tpl_id) or {}
            pub_val = pub_map.get(published_key)
            if isinstance(pub_val, str) and pub_val:
                host, source_path = _split_host(pub_val, host)

        if not isinstance(source_path, str):
            continue

        if os.path.isabs(source_path):
            src = source_path
        else:
            if project_root is None:
                continue
            src = str((project_root / source_path).resolve())
            host = project_host

        dest = entry.get("dest")
        if not isinstance(dest, str):
            continue
        dest = _render_target_dir(tpl_id, dest)

        report_section = entry.get("report_section")
        if not isinstance(report_section, str) or not report_section:
            report_section = "general"

        description = entry.get("description")
        if not isinstance(description, str):
            description = ""

        export_list.append(
            {
                "src": src,
                "dest": dest,
                "host": host,
                "project": entry.get("project") or (ctx.project.name if ctx.project else ""),
                "mode": entry.get("mode") or "symlink",
                "include_in_report": entry.get("include_in_report", include_in_report),
                "report_section": report_section,
                "description": description,
            }
        )

    project_name = ctx.project.name if ctx.project else ""
    if not ctx.params.get("export_username") and project_name:
        parts = project_name.split("_")
        if len(parts) >= 2 and parts[1]:
            ctx.params["export_username"] = parts[1]
    if not ctx.params.get("export_password"):
        ctx.params["export_password"] = secrets.token_urlsafe(16)

    job_spec = {
        "project_name": project_name,
        "export_list": export_list,
        "backend": _split_csv(ctx.params.get("export_engine_backends")),
        "username": str(ctx.params.get("export_username", "")),
        "password": str(ctx.params.get("export_password", "")),
        "authors": project_authors,
        "job_id": export_job_id,
        "expiry_days": int(ctx.params.get("export_expiry_days", 0) or 0),
    }

    out_dir = project_dir / ctx.template.id if ctx.project else Path(ctx.cwd)
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / "export_job_spec.json"
    spec_path.write_text(json.dumps(job_spec, indent=2))

    return job_spec
