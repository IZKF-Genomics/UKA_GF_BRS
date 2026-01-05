#!/usr/bin/env bash
# Example entry script for this workflow. See run.py for a Python variant.
set -euo pipefail

name="${1:-World}"
include_time="${2:-false}"

# Return a dotted-path value from BPM_CTX_PATH JSON or empty string.
ctx_get() {
  local key="${1:-}"
  if [[ -z "${BPM_CTX_PATH:-}" || ! -f "${BPM_CTX_PATH}" || -z "${key}" ]]; then
    return 0
  fi
  python - <<'PY'
import json
import os
import sys

path = os.environ.get("BPM_CTX_PATH")
key = sys.argv[1] if len(sys.argv) > 1 else ""
ctx = json.load(open(path))
cur = ctx
for part in key.split("."):
    if isinstance(cur, dict):
        cur = cur.get(part)
    else:
        cur = None
        break
if cur is None:
    cur = ""
print(cur)
PY
  "${key}"
}

project_name="$(ctx_get "project.name")"

echo "Hello, ${name}!"
if [[ -n "${project_name}" ]]; then
  echo "Project: ${project_name}"
fi
if [[ "${include_time}" == "true" ]]; then
  date -u "+%Y-%m-%dT%H:%M:%SZ"
fi
