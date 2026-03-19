"""
Resolver: get_fastq_folder
Purpose: Return the FASTQ output root directory for the current template run,
         provided that FASTQ files exist under it (excluding any path with
         'Undetermined' in it).

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
    Convert an absolute local path to a host-aware string.

    - Project mode: express as host:project_rel_path when possible.
    - Ad-hoc mode: return hostname:/abs/local/path.
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
        # Ensure single leading slash
        if not joined.startswith("/"):
            joined = "/" + joined
        return f"{proj_host}:{joined}"
    except Exception:
        # Not under project root; fall back to current host + absolute local path
        ap = abs_local_path.as_posix()
        if not ap.startswith("/"):
            ap = "/" + ap
        return f"{ctx.hostname()}:{ap}"


def main(ctx) -> str:
    """
    Locate the FASTQ output root directory for this template run.

    Behavior:
      - Project mode: base is <project_dir>/<tpl_id>
      - Ad‑hoc mode:  base is ctx.cwd (render.into='.')
      - Prefer '<base>/output' if it exists, else use '<base>'
      - Return the root directory itself once FASTQs are detected anywhere under it
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

    for dirpath, _, files in os.walk(root):
        p = Path(dirpath)
        # Exclude any path containing 'Undetermined' (case-insensitive)
        if any("undetermined" in part.lower() for part in p.parts):
            continue

        if any(f.lower().endswith(FASTQ_EXTS) for f in files):
            return _hostify(ctx, root.resolve())

    if not root.exists():
        raise RuntimeError(
            f"FASTQ output root not found: '{root}'. Expected demultiplexed FASTQs under this directory."
        )

    if not any(root.iterdir()):
        raise RuntimeError(
            f"FASTQ output root exists but is empty: '{root}'. Expected demultiplexed FASTQs under this directory."
        )

    raise RuntimeError(
        "No FASTQ files found under template directory "
        f"('{root}'), excluding 'Undetermined' paths."
    )
