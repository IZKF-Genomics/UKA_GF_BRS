# demux_bclconvert


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: demux_bclconvert
kind: template
description: Demultiplex Illumina BCLs using bcl-convert, with optional FastQC, fastq_screen,
  and MultiQC.
descriptor: templates/demux_bclconvert/template_config.yaml
required_params:
- bcl_dir
optional_params:
- agendo_id
- gf_api_name
- gf_api_pass
- no_lane_splitting
- run_fastq_screen
- sampleproject_subdirs
- thread_ratio
- use_api_samplesheet
cli_flags:
  bcl_dir: --bcl
  use_api_samplesheet: --api-samplesheet
  gf_api_name: --api-user
  gf_api_pass: --api-pass
  agendo_id: --agendo-id
  run_fastq_screen: --fastq-screen
  thread_ratio: --thread-ratio
run_entry: run.sh
publish_keys:
- FASTQ_dir
- multiqc_report
render_file_count: 3
```
<!-- AGENT_METADATA_END -->

Demultiplex Illumina BCLs using bcl-convert, with optional FastQC, fastq_screen, and a MultiQC summary.

## Usage
Render, then run in the desired working directory (where you want outputs):

```
cd /data/fastq/

bpm template render demux_bclconvert --adhoc --bcl /data/raw/nextseq500_NB501289/251209_NB501289_0978_AHKWC7AFX7/ 

cd 250915_A01742_0505_AH2NNKDRX7
bpm template run demux_bclconvert
```

## Parameters
- `bcl_dir` (required, str, exists: dir): Path to the BCL run folder.
- `run_fastq_screen` (bool, default `false`): Run fastq_screen on FASTQs.
- `thread_ratio` (float, default `0.8`): Fraction of idle CPUs to allocate per bcl-convert pool (0-1).
- `no_lane_splitting` (bool, default `true`): Pass `--no-lane-splitting` to bcl-convert.
- `sampleproject_subdirs` (bool, default `false`): Create per-sample project subdirectories.
- `use_api_samplesheet` (bool, default `true`): Fetch samplesheet.csv from API in post-render.
- `gf_api_name` / `gf_api_pass` (optional): Credentials for API (env vars also supported).
- `agendo_id` (optional): Agendo request ID for samplesheet retrieval when flowcell is unavailable.

## Outputs
- Render target (project mode): `${ctx.project_dir}/${ctx.template.id}/`.
- Run directory: same as render target.
- FASTQ output (`sampleproject_subdirs = true`): bcl-convert creates project subfolders.
- FASTQ output (`sampleproject_subdirs = false`): FASTQs are written under `./output/`.
- Other outputs:
  - `samplesheet.csv` (rendered; overwritten by API hook when enabled).
  - `run.sh` in the run directory.
  - `multiqc/multiqc_report.html`.

## Published Keys
- `FASTQ_dir`: Host-aware path to the chosen FASTQ directory.
- `multiqc_report`: Host-aware path to the MultiQC HTML report.

## Notes
- Post-render hook fetches samplesheet when `use_api_samplesheet=true`.
- API URL (flowcell): `https://genomics.rwth-aachen.de/api/get/samplesheet/flowcell/{flowcell}`.
- API URL (Agendo request): `https://genomics.rwth-aachen.de/api/get/samplesheet/request/{id}`.
- Credentials: params `gf_api_name`/`gf_api_pass` or env `GF_API_NAME`/`GF_API_PASS`.
- Flowcell id is derived from the last underscore-delimited token in `bcl_dir`; if missing, render fails. `agendo_id` is only used on flowcell 404 responses.
- Render aborts if samplesheet fetch fails.
