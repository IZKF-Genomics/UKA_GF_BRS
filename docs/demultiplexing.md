# Demultiplexing

Use the `demux_bclconvert` template to demultiplex Illumina BCLs, then export FASTQs and
MultiQC with `export_demux` if needed.

## Render and run (ad-hoc)
```
cd /data/fastq
bpm template render demux_bclconvert --out 251209_NB501289_0978_AHKWC7AFX7 --param bcl_dir=/data/raw/nextseq500_NB501289/251209_NB501289_0978_AHKWC7AFX7
cd 251209_NB501289_0978_AHKWC7AFX7
bpm template run demux_bclconvert
```

## Export demultiplexing output
```
bpm workflow run expor
t_demux --run-dir /data/fastq/251209_NB501289_0978_AHKWC7AFX7/ --project-name 251209_UserName_PIName_Institute_FASTQ
```

## Notes
- Outputs land under the render directory (e.g., `output/` and `multiqc/`).
- `--run-dir` must be an absolute path that contains `output/` and `multiqc/`, or a
  `bpm.meta.yaml` with published paths.
- For full parameter details, see
  [templates/demux_bclconvert/README.md](../templates/demux_bclconvert/README.md) and
  [workflows/export_demux/README.md](../workflows/export_demux/README.md).
