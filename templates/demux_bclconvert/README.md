# demux_bclconvert

Demultiplex Illumina BCLs using `bcl-convert`, with optional FastQC, fastq_screen, and a MultiQC summary.

## Parameters
- `bcl_dir` (required, str): Absolute path to the BCL run folder.
- `run_fastq_screen` (bool, default `false`): Run `fastq_screen` on FASTQs.
- `reserve_cores` (int, default `10`): CPU cores to reserve (not used by bcl-convert).
- `threads_fraction` (float, default `0.33`): Fraction of idle CPUs to assign per bcl-convert thread pool.
- `no_lane_splitting` (bool, default `true`): Pass `--no-lane-splitting` to bcl-convert.
- `sampleproject_subdirs` (bool, default `true`): Create per-sample project subdirectories.
- `extra_bclconvert_args` (str, default empty): Additional arguments appended to `bcl-convert`.

## Paths and Outputs
- Render target (project mode): `${ctx.project_dir}/${ctx.template.id}/` → `<project_path>/demux_bclconvert/`
- Run directory: same as render target.
- FASTQ output:
  - If `sampleproject_subdirs = true`: bcl-convert creates project subfolders under the run directory.
  - If `sampleproject_subdirs = false`: FASTQs are written under `./output/` inside the run directory.
- Other outputs:
  - `samplesheet.csv`, `run.sh` in the run directory
  - `multiqc/multiqc_report.html`

## Usage
Render, then run (from your project directory):

```
cd /path/to/projects/PROJECT

# Render with required parameter
bpm template render --param "bcl_dir=/path/to/BCL_RUN" demux_bclconvert

# Run entry script
bpm template run demux_bclconvert

# Publish resolvers (records paths into project.yaml)
bpm template publish demux_bclconvert
```

## Published keys
- `FASTQ_dir`: Host-aware path to the chosen FASTQ directory (prefers `./output` when present; otherwise the directory containing the most FASTQs, excluding `Undetermined`).
- `multiqc_report`: Host-aware path to the MultiQC HTML report.
