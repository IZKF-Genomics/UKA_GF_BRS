# Basic analysis

Common analysis entry points in this BRS:

## RNA-seq processing (nf-core)
```
bpm template render nfcore_rnaseq --dir /path/to/project --param genome=GRCh38 --param agendo_id=12345
bpm template run nfcore_rnaseq --dir /path/to/project
```

For 3' mRNA-seq, use:
```
bpm template render nfcore_3mrnaseq --dir /path/to/project --param genome=GRCh38 --param agendo_id=12345
bpm template run nfcore_3mrnaseq --dir /path/to/project
```

## Differential expression (DGEA)
```
bpm template render dgea --dir /path/to/project --param salmon_dir=/path/to/quant --param organism=hsapiens
bpm template run dgea --dir /path/to/project
```

## Notes
- Parameters vary by template; check the per-template README for details.
- `bpm template readme <template_id>` prints the README from the active BRS.
