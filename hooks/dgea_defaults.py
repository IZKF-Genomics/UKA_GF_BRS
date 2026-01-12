"""
Pre-render hook to populate DGEA params from project defaults/resolvers when missing.
"""

from pathlib import Path
import yaml
from resolvers import dgea_defaults


def populate(ctx) -> None:
    params = ctx.params

    def _needs_fill(val):
        return (
            val is None
            or (isinstance(val, str) and (val.startswith("${resolvers.") or val == "" or val == "PROJECT_AUTHORS"))
        )

    def _load_project_templates():
        if not getattr(ctx, "project", None):
            return []
        proj_dir = Path(ctx.materialize(ctx.project.project_path))
        pyaml = proj_dir / "project.yaml"
        if not pyaml.exists():
            return []
        try:
            proj_data = yaml.safe_load(pyaml.read_text()) or {}
            return proj_data
        except Exception:
            return []

    proj_data = _load_project_templates()
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
    if _needs_fill(params.get("nfcore_samplesheet")):
        params["nfcore_samplesheet"] = _first_available(["published", "nfcore_samplesheet"])
    if _needs_fill(params.get("organism")):
        genome_val = _first_available(["params", "genome"])
        if genome_val:
            genome_norm = str(genome_val).lower()
            mapping = {
                "grch38": "hsapiens",
                "hg38": "hsapiens",
                "grcm39": "mmusculus",
                "grcm38": "mmusculus",
                "mm10": "mmusculus",
                "mratbn7.2": "rnorvegicus",
                "rn7": "rnorvegicus",
            }
            if genome_norm in ("hsapiens", "mmusculus", "rnorvegicus"):
                params["organism"] = genome_norm
            elif genome_norm in mapping:
                params["organism"] = mapping[genome_norm]
        if _needs_fill(params.get("organism")):
            raise RuntimeError("organism/genome not found or unmappable in upstream templates")
    if "ercc" not in params or params.get("ercc") is None:
        params["ercc"] = bool(_first_available(["params", "ercc"]))
    if _needs_fill(params.get("application")):
        params["application"] = _first_available(["params", "application"]) or "nfcore_3mrnaseq"
    if _needs_fill(params.get("name")) and getattr(ctx, "project", None):
        params["name"] = getattr(ctx.project, "name", "project")
    if _needs_fill(params.get("authors")):
        params["authors"] = _authors_from_project() or dgea_defaults.get_author_names_dgea(ctx)
    # Drop legacy genome key if present
    if "genome" in params:
        params.pop("genome", None)
