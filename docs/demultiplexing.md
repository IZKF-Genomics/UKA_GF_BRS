# Demultiplexing

Use the `demux_bclconvert` template to demultiplex Illumina BCLs, then export FASTQs and
MultiQC with `export_demux` if needed.

## Render and run (ad-hoc)
```bash
cd /data/fastq
bpm template render demux_bclconvert --out 251209_NB501289_0978_AHKWC7AFX7 --param bcl_dir=/data/raw/nextseq500_NB501289/251209_NB501289_0978_AHKWC7AFX7
cd 251209_NB501289_0978_AHKWC7AFX7
bpm template run demux_bclconvert
```

Example using the template's ad-hoc output resolver:
```bash
cd /data/fastq
bpm template render demux_bclconvert --adhoc --bcl /data/raw/novaseq_A01742/260320_A01742_0619_AHHT35DRX7/ --agendo-id 5499
cd 260320_A01742_0619_AHHT35DRX7
bpm template run demux_bclconvert
```

## Export demultiplexing output
```
bpm workflow run export_demux --run-dir /data/fastq/251209_NB501289_0978_AHKWC7AFX7/ --project-name 251209_UserName_PIName_Institute_FASTQ
```

## Notes
- Outputs land under the render directory (for example `output/`, `multiqc/`, `results/`, and `bpm.meta.yaml` in ad-hoc mode).
- The ad-hoc resolver derives the output directory from the basename of `bcl_dir` unless `--out` is given explicitly.
- Runtime metadata is recorded in `results/run_info.yaml` (status, selected params, and software versions).
- The API samplesheet hook runs at render time when `use_api_samplesheet=true`; API `404 Not Found` leaves the rendered `samplesheet.csv` in place and prints the API detail message.
- `--run-dir` must be an absolute path that contains `output/` and `multiqc/`, or a
  `bpm.meta.yaml` with published paths.
- For full parameter details, see
  [templates/demux_bclconvert/README.md](../templates/demux_bclconvert/README.md) and
  [workflows/export_demux/README.md](../workflows/export_demux/README.md).

## Methods/Citation Source of Truth (demux_bclconvert)
The following files define demultiplexing methods and citation provenance and are consumed by BPM agent features:

- `templates/demux_bclconvert/template_config.yaml` (declared params, defaults, run entry).
- `templates/demux_bclconvert/run.sh.j2` (actual runtime behavior and version capture commands).
- `templates/demux_bclconvert/README.md` (usage and operational notes).
- `templates/demux_bclconvert/METHODS.md` (publication-oriented method narrative).
- `templates/demux_bclconvert/citations.yaml` (machine-readable citations).
- `templates/demux_bclconvert/references.bib` (BibTeX for Quarto/manuscript citation flow).
