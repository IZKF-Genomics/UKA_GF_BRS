"""
Resolver: get_salmon_dir
Purpose: Locate the nf-core/rnaseq Salmon quant directory and return it as a
         host-aware path string (e.g., "nextgen:/abs/path/to/results/salmon").

Behavior:
  - Project mode: base is <project_dir>/<template_id>.
  - Ad-hoc mode:  base is ctx.cwd.
  - Prefer '<base>/results/salmon' if it exists.
  - Otherwise, search for any 'quant.sf' and return its grandparent (sample dir's parent).
"""

from pathlib import Path, PurePosixPath
import os


def _split_host(path_str: str, default_host: str) -> tuple[str, str]:
    if ":" in path_str:
        host, rest = path_str.split(":", 1)
    else:
        host, rest = default_host, path_str
    if not rest.startswith("/"):
        rest = "/" + rest
    return host, rest


def _hostify(ctx, abs_local_path: Path) -> str:
    """
    Convert an absolute local path to a host-aware string.
    """
    if not getattr(ctx, "project", None):
        ap = abs_local_path.as_posix()
        if not ap.startswith("/"):
            ap = "/" + ap
        return f"{ctx.hostname()}:{ap}"

    proj_host, proj_rest = _split_host(str(ctx.project.project_path), ctx.hostname())
    proj_local_root = Path(ctx.materialize(ctx.project.project_path)).resolve()

    try:
        rel = abs_local_path.resolve().relative_to(proj_local_root)
        joined = str(PurePosixPath(proj_rest) / rel.as_posix())
        if not joined.startswith("/"):
            joined = "/" + joined
        return f"{proj_host}:{joined}"
    except Exception:
        ap = abs_local_path.as_posix()
        if not ap.startswith("/"):
            ap = "/" + ap
        return f"{ctx.hostname()}:{ap}"


def _find_salmon_dir(base: Path) -> Path:
    """
    Return the salmon directory under base.
    """
    # Prefer explicit results*/salmon directories (handles results or results_<id>)
    for cand in list(base.glob("results*/salmon")):
        if cand.is_dir():
            return cand.resolve()

    # Fallback: search for quant.sf and return its grandparent
    for dirpath, _, files in os.walk(base):
        # Skip transient work dirs
        if "/work/" in dirpath or dirpath.rstrip("/").endswith("/work"):
            continue
        if "quant.sf" in files:
            p = Path(dirpath)
            # quant.sf lives in .../salmon/<sample>/quant.sf; grandparent is salmon root
            if p.parent.is_dir():
                return p.parent.resolve()
    raise RuntimeError(f"Salmon directory not found under '{base}'. Expected 'results/salmon' or any quant.sf.")


def main(ctx) -> str:
    if ctx.project:
        base = (Path(ctx.project_dir) / ctx.template.id).resolve()
    else:
        base = Path(ctx.cwd).resolve()
    salmon_dir = _find_salmon_dir(base)
    return _hostify(ctx, salmon_dir)
