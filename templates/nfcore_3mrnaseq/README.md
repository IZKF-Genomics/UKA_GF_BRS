# nfcore_3mrnaseq

nf-core/rnaseq wrapper for 3' mRNA-seq data.

## Render
Run from the project directory (where project.yaml lives).
```
bpm template render nfcore_3mrnaseq --genome GRCh38
bpm template render nfcore_3mrnaseq --genome GRCh38 --agendo-id 12345
```

If `--agendo-id` is provided and Agendo supplies `organism`, the genome may be derived
by `hooks.genome_from_organism:set_from_organism`.

## Run
```
bpm template run nfcore_3mrnaseq --dir /path/to/project
```

## Parameters
See `template_config.yaml` for the full parameter list and defaults.

`spikein` is a free-text value from Agendo (or `--spikein`) and is used to decide
whether to append `_with_ERCC` to the genome when it contains `ERCC`.
