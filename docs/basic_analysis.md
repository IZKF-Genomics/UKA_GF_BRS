# Basic analysis

This workflow starts after demultiplexing and does not use `export_demux`.

## Project init (adopt a demux run)
```
cd /data/projects
bpm project init --author ckuo --adopt /data/fastq/251209_NB501289_0978_AHKWC7AFX7/ 251209_UserName_PIName_Institute_3mRNAseq
```

## RNA-seq processing (nf-core 3'mRNA-seq)
```
cd 251209_UserName_PIName_Institute_3mRNAseq
bpm template render nfcore_3mrnaseq --genome GRCh38 --agendo-id 4622
# check nfcore_3mrnaseq/run.sh
bpm template run nfcore_3mrnaseq
```

If the project is not 3' mRNA-seq, use `nfcore_rnaseq`:
```
bpm template render nfcore_rnaseq --genome GRCh38 --agendo-id 4622
# check nfcore_rnaseq/run.sh
bpm template run nfcore_rnaseq
```

More options will be implemented.

## Differential expression (DGEA)
```
bpm template render dgea
# check dgea/DGEA_constructor.R to generate all reports manually
# or, do this command:
# bpm template run dgea
```

## Export
```
bpm template render export
# check or edit export/export_job_spec.json
bpm template run export
```

## Notes
- Parameters vary by template; check the per-template README for details.
- `bpm template readme <template_id>` prints the README from the active BRS.
