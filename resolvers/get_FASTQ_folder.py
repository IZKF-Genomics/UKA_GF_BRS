"""
Resolver: get_fastq_folder
Purpose: Find the folder under the current template directory that contains FASTQ files
         (excluding any path with 'Undetermined' in it), and return it as a
         hostname-aware path string suitable for storing in project.yaml.

Return:
  str  -> "host:/abs/posix/path"

Notes:
  - Runs without arguments; uses ctx.*
  - Pure function: no side-effects, raises RuntimeError on failure
"""

from pathlib import Path, PurePosixPath
import os


FASTQ_EXTS = (".fastq", ".fastq.gz", ".fq", ".fq.gz")


def _split_host(path_str: str, default_host: str) -> tuple[str, str]:
    """
    Split a path that may be host-aware ("host:/abs") or local ("/abs").
    Returns (host, rest_abs_posix_with_leading_slash).
    """
    if ":" in path_str:
        host, rest = path_str.split(":", 1)
    else:
        host, rest = default_host, path_str

    # normalize leading slash on the 'rest' part
    if not rest.startswith("/"):
        rest = f"/{rest}"
    return host, rest


def _hostify(ctx, abs_local_path: Path) -> str:
    """
    Convert an absolute local path to a host-aware string based on the project's
    host-aware project_path; fall back to current host if not inside the project root.
    """
    proj_host, proj_rest = _split_host(str(ctx.project.project_path), ctx.hostname())
    proj_local_root = Path(ctx.materialize(ctx.project.project_path)).resolve()

    try:
        rel = abs_local_path.resolve().relative_to(proj_local_root)
        joined = str(PurePosixPath(proj_rest) / rel.as_posix())
        # Ensure single leading slash
        if not joined.startswith("/"):
            joined = "/" + joined
        return f"{proj_host}:{joined}"
    except Exception:
        # Not under project root; fall back to current host + absolute local path
        return f"{ctx.hostname()}:{abs_local_path.as_posix() if abs_local_path.as_posix().startswith('/') else '/' + abs_local_path.as_posix()}"


def main(ctx) -> str:
    """
    Locate the FASTQ output directory for this template run.

    Behavior:
      - Project mode: base is <project_dir>/<tpl_id>
      - Ad‑hoc mode:  base is ctx.cwd (render.into='.')
      - Prefer '<base>/output' if it exists, else use '<base>'
      - Exclude any path containing 'Undetermined'

    Returns a hostname-aware path string.
    """
    # Determine base directory depending on mode
    if ctx.project:
        base = (Path(ctx.project_dir) / ctx.template.id).resolve()
    else:
        base = Path(ctx.cwd).resolve()

    # Prefer the common bcl-convert layout: <base>/output
    root = (base / "output") if (base / "output").is_dir() else base

    candidates: list[tuple[int, Path]] = []

    for dirpath, _, files in os.walk(root):
        p = Path(dirpath)
        # Exclude any path containing 'Undetermined' (case-insensitive)
        if any("undetermined" in part.lower() for part in p.parts):
            continue

        # Count FASTQ files in this directory (non-recursive for this node)
        fastq_count = sum(1 for f in files if f.lower().endswith(FASTQ_EXTS))
        if fastq_count > 0:
            candidates.append((fastq_count, p))

    if not candidates:
        raise RuntimeError(
            "No FASTQ files found under template directory "
            f"('{root}'), excluding 'Undetermined' paths."
        )

    # Pick the dir with the most FASTQs; tie-break by path string for determinism
    candidates.sort(key=lambda t: (-t[0], t[1].as_posix()))
    best = candidates[0][1]

    return _hostify(ctx, best.resolve())
