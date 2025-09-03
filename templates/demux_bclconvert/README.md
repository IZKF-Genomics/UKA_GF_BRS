# demux_bclconvert

Demultiplex Illumina BCLs using `bcl-convert` and summarize with MultiQC.

## Parameters
- `bcl_dir` (required): Path to the BCL run folder.
- `output_dir` (default `output`): Output folder within the template directory.
- `run_fastq_screen` (default `false`): Run `fastq_screen` on output FASTQs.
- `reserve_cores` (default `10`): Number of CPU cores to reserve from total.
- `threads_fraction` (default `0.33`): Fraction of idle CPUs per bcl-convert thread pool.
- `no_lane_splitting` (default `true`): bcl-convert `--no-lane-splitting`.
- `sampleproject_subdirs` (default `true`): create per-sample project subdirectories.
- `extra_bclconvert_args` (default empty): additional args appended to `bcl-convert`.

## Usage
Render, then run:

```
bpm template render demux_bclconvert \
  --param bcl=/path/to/BCL_RUN

bpm template run demux_bclconvert --dir /path/to/projects/PROJECT
```
