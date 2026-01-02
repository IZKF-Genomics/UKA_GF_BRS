#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTDIR="${OUTDIR:-$PWD}"

python3 "$SCRIPT_DIR/build_ref_genomes.py" \
  --config "$SCRIPT_DIR/genomes.yaml" \
  --outdir "$OUTDIR"
