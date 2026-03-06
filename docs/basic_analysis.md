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

`export` auto-discovers `agendo_id`/`flowcell_id` from `project.yaml` when available
(typically from previous template params). Use `--agendo-id` / `--flowcell-id` only
to override.
Metadata context files are generated during export render:
- `export/metadata_raw.json`
- `export/metadata_normalized.yaml`
- `export/metadata_context.yaml`

## Methods Draft (independent from export)
Generate publication-oriented methods text from project history:
```
bpm template render methods_report
# output: methods_report/auto_methods.md
```
Optional:
```
bpm template render methods_report --methods-style concise --methods-output methods_for_publication.md
```

## Notes
- Parameters vary by template; check the per-template README for details.
- `bpm template readme <template_id>` prints the README from the active BRS.
