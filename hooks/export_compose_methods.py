from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from bpm.core import agent_methods
from bpm.io.yamlio import safe_dump_yaml, safe_load_yaml


def _load_project(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw = safe_load_yaml(path)
    return raw if isinstance(raw, dict) else {}


def _collect_versions(project_dir: Path, project_data: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for t in project_data.get("templates") or []:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not tid:
            continue
        run_info = project_dir / tid / "results" / "run_info.yaml"
        if not run_info.exists():
            continue
        raw = safe_load_yaml(run_info)
        if not isinstance(raw, dict):
            continue
        versions = raw.get("versions")
        if not isinstance(versions, dict):
            continue
        for k, v in versions.items():
            kk = str(k).strip()
            vv = str(v).strip()
            if kk and vv and kk not in out:
                out[kk] = vv
    return out


def _extract_citations(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    out: list[str] = []
    in_cit = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("## ") and s.lower() == "## citations":
            in_cit = True
            continue
        if in_cit and s.startswith("## "):
            break
        if in_cit and s.startswith("- "):
            out.append(s[2:].strip())
    return out


def main(ctx: Any) -> Dict[str, Any]:
    if not getattr(ctx, "project", None):
        return {"status": "skipped", "reason": "no_project_context"}

    include_methods = bool(ctx.params.get("include_methods_in_spec", True))
    if not include_methods:
        return {"status": "skipped", "reason": "include_methods_in_spec=false"}

    style = str(ctx.params.get("methods_style") or "full").strip().lower()
    if style not in ("full", "concise"):
        style = "full"

    project_dir = Path(ctx.project_dir)
    export_dir = project_dir / ctx.template.id
    export_dir.mkdir(parents=True, exist_ok=True)

    project_data = _load_project(project_dir / "project.yaml")
    metadata_normalized_path = export_dir / "metadata_normalized.yaml"
    metadata_normalized = (
        safe_load_yaml(metadata_normalized_path) if metadata_normalized_path.exists() else {}
    )
    if not isinstance(metadata_normalized, dict):
        metadata_normalized = {}

    result = agent_methods.generate_methods_markdown(project_dir, style=style)
    citations = _extract_citations(result.markdown)
    versions = _collect_versions(project_dir, project_data)

    methods_block = {
        "style": style,
        "templates_count": result.templates_count,
        "citation_count": result.citation_count,
        "full_text": result.markdown,
        "citations": citations,
        "software_versions": versions,
        "protocol_metadata": metadata_normalized,
    }

    methods_md_path = export_dir / "project_methods.md"
    methods_md_path.write_text(result.markdown, encoding="utf-8")
    safe_dump_yaml(export_dir / "methods_context.yaml", methods_block)

    spec_path = export_dir / "export_job_spec.json"
    if spec_path.exists():
        raw = json.loads(spec_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw["methods"] = methods_block
            raw["methods_markdown_path"] = str(methods_md_path)
            spec_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    return {
        "status": "ok",
        "style": style,
        "methods_path": str(methods_md_path),
        "templates_count": result.templates_count,
        "citation_count": result.citation_count,
    }

