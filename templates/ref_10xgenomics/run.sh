#!/usr/bin/env bash
set -euo pipefail

# Download and extract 10x Genomics reference indices.
# Skips download/extract if files already exist.

OUT_DIR="$(pwd)"
urls=(
  "https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCh38-2024-A.tar.gz"
  "https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz"
  "https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-mRatBN7-2-2024-A.tar.gz"
  "https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCh38_and_GRCm39-2024-A.tar.gz"
  "https://cf.10xgenomics.com/supp/cell-vdj/refdata-cellranger-vdj-GRCh38-alts-ensembl-7.1.0.tar.gz"
  "https://cf.10xgenomics.com/supp/cell-vdj/refdata-cellranger-vdj-GRCm38-alts-ensembl-7.0.0.tar.gz"
)

for url in "${urls[@]}"; do
  file="${OUT_DIR}/$(basename "${url}")"
  dir="${file%.tar.gz}"
  if [[ -f "${file}" ]]; then
    echo "[skip] download exists: ${file}"
  else
    echo "[get] ${file}"
    curl -L -o "${file}" "${url}"
  fi

  if [[ -d "${dir}" ]]; then
    echo "[skip] extracted exists: ${dir}"
  else
    echo "[extract] ${file}"
    tar -xzf "${file}" -C "${OUT_DIR}"
    rm -f "${file}"
  fi
done
