"""
Pre-render hook to populate ERCC params from project.yaml when missing.
"""

from pathlib import Path
import yaml


def populate(ctx) -> None:
    params = ctx.params

    def _needs_fill(val):
        return val is None or (isinstance(val, str) and val.strip() == "")

    if not getattr(ctx, "project", None):
        return

    proj_dir = Path(ctx.materialize(ctx.project.project_path))
    pyaml = proj_dir / "project.yaml"
    if not pyaml.exists():
        return
    try:
        proj_data = yaml.safe_load(pyaml.read_text()) or {}
    except Exception:
        return

    templates = proj_data.get("templates") if isinstance(proj_data, dict) else []

    def _first_available(key_path):
        for tmpl_id in ("nfcore_3mrnaseq", "nfcore_rnaseq"):
            entry = next((t for t in templates if t.get("id") == tmpl_id), None)
            if not entry:
                continue
            node = entry
            ok = True
            for k in key_path:
                node = node.get(k) if isinstance(node, dict) else None
                if node is None:
                    ok = False
                    break
            if ok and node is not None:
                return node
        return None

    def _authors_from_project():
        if not isinstance(proj_data, dict):
            return None
        authors = proj_data.get("authors") or []
        names = []
        for a in authors:
            if isinstance(a, dict):
                n = a.get("name")
            else:
                n = getattr(a, "name", None)
            if n:
                names.append(n)
        return ", ".join(names) if names else None

    if _needs_fill(params.get("salmon_dir")):
        params["salmon_dir"] = _first_available(["published", "salmon_dir"])
    if _needs_fill(params.get("samplesheet")):
        params["samplesheet"] = _first_available(["published", "nfcore_samplesheet"])
    if _needs_fill(params.get("authors")):
        params["authors"] = _authors_from_project()

    if _needs_fill(params.get("salmon_dir")) or _needs_fill(params.get("samplesheet")):
        raise RuntimeError(
            "Missing salmon_dir or samplesheet; provide params or ensure project.yaml "
            "contains published outputs from nfcore_rnaseq/nfcore_3mrnaseq."
        )
