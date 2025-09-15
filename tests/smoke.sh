#!/usr/bin/env bash
set -euo pipefail

# Generate templates.txt in dependency order (reads tests/params.yaml if present)
python3 "$(dirname "${BASH_SOURCE[0]}")/gen_templates_txt.py"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRS_DIR="$ROOT_DIR"
TESTS_DIR="$ROOT_DIR/tests"
PROJECT_PARENT="$TESTS_DIR/.tmp_project"
PROJECT_NAME="BRS_SMOKE"

export BPM_CACHE="$BRS_DIR/.bpm_cache_test"
mkdir -p "$BPM_CACHE"

echo "[info] Using BPM_CACHE=$BPM_CACHE"

# Register this BRS and activate
bpm resource add "$BRS_DIR" --activate

# Fresh project
rm -rf "$PROJECT_PARENT"
mkdir -p "$PROJECT_PARENT"
bpm project init "$PROJECT_NAME" --outdir "$PROJECT_PARENT"

PROJECT_DIR="$PROJECT_PARENT/$PROJECT_NAME"
echo "[info] Project at $PROJECT_DIR"

# Iterate templates.txt (id plus optional args)
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  # shellcheck disable=SC2206
  TOKS=($line)
  TPL_ID="${TOKS[0]}"
  ARGS=("${TOKS[@]:1}")
  echo "[smoke] Rendering $TPL_ID ${ARGS[*]:+with args: ${ARGS[*]}}"
  (cd "$PROJECT_DIR" && bpm template render "${ARGS[@]}" "$TPL_ID")
_done=$?
  if [[ $_done -ne 0 ]]; then
    echo "[fail] $TPL_ID"
    exit 1
  fi
.done

echo "[ok] Smoke render completed"
