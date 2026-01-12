"""
Resolvers for DGEA defaults that can pull from either nfcore_3mrnaseq or nfcore_rnaseq.
Each returns the first available value; raises if none found.
"""


def _get_template_entry(ctx, template_id: str):
  if not getattr(ctx, "project", None):
    return None
  for entry in getattr(ctx.project, "templates", []) or []:
    if entry.get("id") == template_id:
      return entry
  return None


def _first_available(ctx, key_path: list[str]):
  """
  key_path: list like ["published", "salmon_dir"] or ["params", "genome"]
  """
  for tmpl_id in ("nfcore_3mrnaseq", "nfcore_rnaseq"):
    entry = _get_template_entry(ctx, tmpl_id)
    if not entry:
      continue
    node = entry
    ok = True
    for k in key_path:
      node = node.get(k) if isinstance(node, dict) else None
      if node is None:
        ok = False
        break
    if ok and node:
      return node
  return None


def _materialize(ctx, val: str) -> str:
  if val is None:
    return None
  sval = str(val)
  try:
    return ctx.materialize(sval)
  except Exception:
    return sval


def get_salmon_dir_any_dgea(ctx) -> str:
  val = _first_available(ctx, ["published", "salmon_dir"])
  if not val:
    raise RuntimeError("salmon_dir not found in published entries of nfcore_3mrnaseq or nfcore_rnaseq")
  return _materialize(ctx, val)


def get_samplesheet_any_dgea(ctx) -> str:
  val = _first_available(ctx, ["published", "nfcore_samplesheet"])
  if not val:
    raise RuntimeError("nfcore_samplesheet not found in published entries of nfcore_3mrnaseq or nfcore_rnaseq")
  return _materialize(ctx, val)


def get_organism_any_dgea(ctx) -> str:
  val = _first_available(ctx, ["params", "genome"])
  if not val:
    raise RuntimeError("organism/genome not found in params of nfcore_3mrnaseq or nfcore_rnaseq")
  genome_norm = str(val).lower()
  mapping = {
    "grch38": "hsapiens",
    "hg38": "hsapiens",
    "grcm39": "mmusculus",
    "grcm38": "mmusculus",
    "mm10": "mmusculus",
    "mratbn7.2": "rnorvegicus",
    "rn7": "rnorvegicus",
  }
  # Allow direct organism strings to pass through
  if genome_norm in ("hsapiens", "mmusculus", "rnorvegicus"):
    return genome_norm
  if genome_norm in mapping:
    return mapping[genome_norm]
  raise RuntimeError(f"Cannot map genome '{val}' to organism (hsapiens/mmusculus/rnorvegicus)")


def get_ercc_any_dgea(ctx) -> bool:
  val = _first_available(ctx, ["params", "ercc"])
  # Default to False if missing entirely
  return bool(val)


def get_application_any_dgea(ctx) -> str:
  val = _first_available(ctx, ["params", "application"])
  if val:
    return val
  # Fallback to nfcore_3mrnaseq if nothing found
  return "nfcore_3mrnaseq"


def get_author_names_dgea(ctx) -> str:
  """
  Return a comma-separated list of all author names from project.yaml, or a placeholder.
  """
  if getattr(ctx, "project", None):
    authors = getattr(ctx.project, "authors", None)
    if authors and len(authors) > 0:
      names = []
      for a in authors:
        if isinstance(a, dict):
          n = a.get("name")
        else:
          n = getattr(a, "name", None)
        if n:
          names.append(n)
      if names:
        return ", ".join(names)
  return "PROJECT_AUTHORS"
