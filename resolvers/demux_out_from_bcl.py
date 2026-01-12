from __future__ import annotations
from pathlib import Path


def main(ctx) -> str:
    """
    Resolve an ad-hoc output folder from the bcl_dir param.

    Returns the basename of bcl_dir (relative), so BPM will place outputs under ./<basename>.
    """
    bcl_dir = (ctx.params or {}).get("bcl_dir")
    if not bcl_dir:
        raise RuntimeError("bcl_dir is required to derive adhoc output directory")
    name = Path(str(bcl_dir)).name
    if not name:
        raise RuntimeError("Could not derive folder name from bcl_dir")
    return name
