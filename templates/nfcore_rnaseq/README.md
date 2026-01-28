# nfcore_rnaseq

nf-core/rnaseq wrapper for total RNA-seq and mRNA-seq data.

## Render
Run from the project directory (where project.yaml lives).
```
bpm template render nfcore_rnaseq --genome GRCh38
bpm template render nfcore_rnaseq --genome GRCh38 --agendo-id 12345
```

## Run
```
bpm template run nfcore_rnaseq --dir /path/to/project
```

## Parameters
See `template_config.yaml` for the full parameter list and defaults.
