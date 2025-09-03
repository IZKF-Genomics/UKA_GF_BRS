"""
Resolver: get_multiqc_report
Purpose: Find the MultiQC HTML report for the current template and return its
         path as a hostname-aware string (e.g., "nextgen:/abs/path/.../multiqc_report.html").

Behavior:
  - Prefer "<template_id>/multiqc/multiqc_report.html" if present.
  - Otherwise, search recursively under the template directory for "multiqc_report*.html".
  - If multiple candidates exist, prefer files inside a "multiqc" folder,
    then by newest modification time, then alphabetically for determinism.
  - Pure function: no side effects. Raises RuntimeError if not found.
"""

from pathlib import Path, PurePosixPath
import os
from typing import List


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
    host-aware project_path; fall back to current host if outside the project root.
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


def _score(path: Path) -> tuple[int, float, str]:
    """
    Higher score wins:
      1) inside a 'multiqc' directory (1 or 0)
      2) newer mtime (float, descending)
      3) alphabetical path (ascending, used as tie-breaker after inversion)
    We return (-mtime) or rather use tuple with negative? Easier: use sort with reverse.
    Here we return a tuple suitable for 'sorted(..., reverse=True)'.
    """
    in_multiqc = 1 if any(part.lower() == "multiqc" for part in path.parts) else 0
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        mtime = 0.0
    return (in_multiqc, mtime, path.as_posix())


def main(ctx) -> str:
    """
    Resolve to the MultiQC report HTML under the current template directory.
    Returns a hostname-aware string.
    """
    # Determine template directory (render root)
    if ctx.project:
        tpl_dir = (Path(ctx.project_dir) / ctx.template.id).resolve()
    else:
        tpl_dir = Path(ctx.cwd).resolve()

    # 1) Preferred conventional location
    preferred = tpl_dir / "multiqc" / "multiqc_report.html"
    if preferred.is_file():
        return _hostify(ctx, preferred.resolve())

    # 2) Fallback: search recursively for multiqc_report*.html
    candidates: List[Path] = []
    for dirpath, _, files in os.walk(tpl_dir):
        for fn in files:
            name = fn.lower()
            if name.startswith("multiqc_report") and name.endswith(".html"):
                candidates.append(Path(dirpath) / fn)

    if not candidates:
        raise RuntimeError(
            f"No MultiQC report found under '{tpl_dir}'. "
            "Expected 'multiqc/multiqc_report.html' or any 'multiqc_report*.html'."
        )

    # Prefer in 'multiqc' dirs, then newest mtime, then alphabetical
    candidates.sort(key=_score, reverse=True)
    best = candidates[0].resolve()
    return _hostify(ctx, best)
