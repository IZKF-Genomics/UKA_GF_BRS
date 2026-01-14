# nfcore_scrnaseq

nf-core/scrnaseq wrapper for single-cell RNA-seq data (default aligner: Cell Ranger).

## Render
```
bpm template render nfcore_scrnaseq --dir /path/to/project \
  --param genome=GRCh38 \
  --param agendo_id=12345 \
  --param cellranger_index=/data/shared_env/10xGenomics/refdata-gex-GRCh38-2020-A
```

## Run
```
bpm template run nfcore_scrnaseq --dir /path/to/project
```

## Parameters
See `template_config.yaml` for the full parameter list and defaults.
