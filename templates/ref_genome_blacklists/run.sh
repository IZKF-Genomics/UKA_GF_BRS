#!/usr/bin/env bash
set -euo pipefail

# Download Boyle-Lab blacklist v2 BED files.
# Skips download if the target file already exists.

OUT_DIR="$(pwd)"
base_url="https://raw.githubusercontent.com/Boyle-Lab/Blacklist/master/lists"
files=(
  "ce10-blacklist.v2.bed.gz"
  "ce11-blacklist.v2.bed.gz"
  "dm3-blacklist.v2.bed.gz"
  "dm6-blacklist.v2.bed.gz"
  "hg19-blacklist.v2.bed.gz"
  "hg38-blacklist.v2.bed.gz"
  "mm10-blacklist.v2.bed.gz"
)

for name in "${files[@]}"; do
  dest="${OUT_DIR}/${name}"
  if [[ -f "${dest}" ]]; then
    echo "[skip] exists: ${dest}"
    continue
  fi
  echo "[get] ${dest}"
  curl -L -o "${dest}" "${base_url}/${name}"
done
