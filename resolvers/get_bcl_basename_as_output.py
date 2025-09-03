"""
Resolver: get_bcl_basename_as_output
Purpose: Derive an output folder name from the basename of the BCL path
         and place it under the template directory.
"""

from pathlib import Path, PurePosixPath


def _split_host(path_str: str, default_host: str) -> tuple[str, str]:
    """Split a possibly host-aware path ('host:/abs') into (host, '/abs')."""
    if ":" in path_str:
        host, rest = path_str.split(":", 1)
    else:
        host, rest = default_host, path_str
    if not rest.startswith("/"):
        rest = "/" + rest
    return host, rest


def _hostify(ctx, abs_local_path: Path) -> str:
    """
    Convert an absolute local path to a host-aware string based on the project's
    host-aware project_path; fall back to current host if not inside project root.
    """
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


def main(ctx) -> str:
    """
    Resolver: returns a host-aware path for the template output directory,
    named after the basename of the given bcl_path parameter.
    """
    # Expect bcl_path param to be set
    bcl_path = ctx.params.get("bcl_path")
    if not bcl_path:
        raise RuntimeError("[resolver:get_bcl_basename_as_output] Missing param: bcl_path")

    bcl_name = Path(ctx.materialize(bcl_path)).name
    tpl_dir = Path(ctx.template.id).resolve()
    out_dir = tpl_dir / bcl_name

    return _hostify(ctx, out_dir.resolve())