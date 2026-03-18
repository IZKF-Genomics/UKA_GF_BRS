"""
Resolver: get_scrnaseq_result_matrix
Purpose: Return the preferred nf-core/scrnaseq result matrix for downstream
         single-cell templates as a host-aware path string.

Behavior:
  - Project mode: base is <project_dir>/<template_id>.
  - Ad-hoc mode:  base is ctx.cwd.
  - Prefer combined filtered H5AD outputs under results*/<aligner>/mtx_conversions.
  - Fall back to other combined or sample-level H5AD outputs if needed.
  - Raise RuntimeError if no H5AD matrix can be found.
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


def _matrix_priority(path: Path) -> tuple[int, int, str]:
    name = path.name.lower()

    if name == "combined_filtered_matrix.h5ad":
        return (6, 1, path.as_posix())
    if name == "combined_cellbender_filter_matrix.h5ad":
        return (5, 1, path.as_posix())
    if name == "combined_raw_matrix.h5ad":
        return (4, 1, path.as_posix())
    if name == "combined_matrix.h5ad":
        return (3, 1, path.as_posix())
    if name.endswith("_filtered_matrix.h5ad"):
        return (2, 0, path.as_posix())
    if name.endswith("_cellbender_filter_matrix.h5ad"):
        return (1, 0, path.as_posix())
    if name.endswith(".h5ad"):
        return (0, 0, path.as_posix())
    return (-1, 0, path.as_posix())


def _find_result_matrix(base: Path) -> Path:
    candidates: list[Path] = []
    for conv_dir in sorted(base.glob("results*/*/mtx_conversions")):
        if not conv_dir.is_dir():
            continue
        candidates.extend(sorted(conv_dir.glob("*.h5ad")))

    if not candidates:
        raise RuntimeError(
            f"No nf-core/scrnaseq H5AD matrix found under '{base}'. "
            "Expected results/<aligner>/mtx_conversions/*.h5ad."
        )

    candidates.sort(key=_matrix_priority, reverse=True)
    return candidates[0].resolve()


def main(ctx) -> str:
    if ctx.project:
        base = (Path(ctx.project_dir) / ctx.template.id).resolve()
    else:
        base = Path(ctx.cwd).resolve()
    matrix_path = _find_result_matrix(base)
    return _hostify(ctx, matrix_path)
