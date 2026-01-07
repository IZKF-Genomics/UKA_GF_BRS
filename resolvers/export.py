from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

def load_mapping(ctx: Any) -> Dict[str, Any]:
    """
    Load export_mapping.yaml from the rendered template directory.

    Returns the parsed mapping dict for publishing into project.yaml.
    """
    if getattr(ctx, "project", None):
        base = Path(ctx.project_dir) / ctx.template.id
    else:
        base = Path(ctx.cwd)

    mapping_path = base / "export_mapping.yaml"
    if not mapping_path.exists():
        raise FileNotFoundError(f"export_mapping.yaml not found at {mapping_path}")

    try:
        import yaml
    except Exception as exc:
        raise RuntimeError(f"PyYAML is required to read export mapping: {exc}") from exc

    data = yaml.safe_load(mapping_path.read_text())
    if not isinstance(data, dict) or "export_structure" not in data:
        raise ValueError(
            "export_mapping.yaml must contain top-level 'export_structure' list"
        )

    entries = data.get("export_structure")
    if not isinstance(entries, list):
        raise ValueError("'export_structure' must be a list")

    return data
