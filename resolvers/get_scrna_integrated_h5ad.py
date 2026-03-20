"""
Resolver: get_scrna_integrated_h5ad
Purpose: Return results/adata.integrated.h5ad for scverse_scrna_integrate as a host-aware path.
"""

from pathlib import Path, PurePosixPath


def _split_host(path_str: str, default_host: str) -> tuple[str, str]:
    if ":" in path_str:
        host, rest = path_str.split(":", 1)
    else:
        host, rest = default_host, path_str
    if not rest.startswith("/"):
        rest = "/" + rest
    return host, rest


def _hostify(ctx, abs_local_path: Path) -> str:
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


def main(ctx) -> str:
    if ctx.project:
        base = (Path(ctx.project_dir) / ctx.template.id).resolve()
    else:
        base = Path(ctx.cwd).resolve()
    out = base / "results" / "adata.integrated.h5ad"
    if not out.is_file():
        raise RuntimeError(f"Expected output H5AD not found: {out}")
    return _hostify(ctx, out.resolve())
