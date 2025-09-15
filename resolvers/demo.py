from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict

def collect_metrics(ctx: Any) -> Dict[str, Any]:
    """Load metrics.json produced by run.sh and return a dict for publishing."""
    metrics_path = Path(ctx.project_dir) / ctx.template.id / "metrics.json"
    if not metrics_path.exists():
        # Be explicit so users see why publish failed
        raise FileNotFoundError(f"metrics.json not found at {metrics_path}")
    with metrics_path.open() as fh:
        data = json.load(fh)
    # Return as-is; keep values JSON-serializable
    return data
