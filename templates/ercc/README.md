# ercc

ERCC spike-in QC report rendered from a Quarto template.

## Render
```
bpm template render ercc --dir /path/to/project
```

Override defaults (if needed):
```
bpm template render ercc --dir /path/to/project \
  --param salmon_dir=/path/to/salmon \
  --param samplesheet=/path/to/samplesheet.csv \
  --param authors="Author A; Author B"
```

## Run
```
bpm template run ercc --dir /path/to/project
```

## Parameters
- salmon_dir: directory containing `salmon.merged.gene_tpm.tsv` (auto from project.yaml when available).
- samplesheet: nf-core pipeline samplesheet CSV with a `sample` column (auto from project.yaml when available).
- authors: optional report author string (auto from project.yaml when available).
