#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone


def ctx_get(path: str) -> str:
    """Return a dotted-path value from BPM_CTX_PATH JSON or empty string."""
    ctx_path = os.environ.get("BPM_CTX_PATH")
    if not ctx_path or not os.path.isfile(ctx_path):
        return ""
    with open(ctx_path, "r", encoding="utf-8") as fh:
        ctx = json.load(fh)
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = None
            break
    return "" if cur is None else str(cur)


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "World"
    include_time = sys.argv[2] if len(sys.argv) > 2 else "false"

    project_name = ctx_get("project.name")

    print(f"Hello, {name}!")
    if project_name:
        print(f"Project: {project_name}")
    if include_time.lower() == "true":
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(now)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
