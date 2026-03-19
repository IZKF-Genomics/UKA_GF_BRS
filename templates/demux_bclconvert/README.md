# demux_bclconvert


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: demux_bclconvert
kind: template
description: Demultiplex Illumina BCLs using bcl-convert, with optional FastQC, fastq_screen,
  and MultiQC.
descriptor: templates/demux_bclconvert/template_config.yaml
source_of_truth:
- templates/demux_bclconvert/run.sh.j2
- templates/demux_bclconvert/template_config.yaml
methods_file: templates/demux_bclconvert/METHODS.md
citations_file: templates/demux_bclconvert/citations.yaml
bibliography_file: templates/demux_bclconvert/references.bib
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
software_version_capture:
  run_info: results/run_info.yaml
  commands:
  - bcl-convert --version
  - fastqc --version
  - fastq_screen --version
  - multiqc --version
render_file_count: 4
```
<!-- AGENT_METADATA_END -->

Demultiplex Illumina BCLs using `bcl-convert`, then summarize FASTQ quality with FastQC and MultiQC. Optional cross-species contamination screening can be enabled with `fastq_screen`.

## Usage
Render, then run in the desired working directory (where you want outputs):

```
cd /data/fastq/

bpm template render demux_bclconvert --adhoc --bcl /data/raw/nextseq500_NB501289/251209_NB501289_0978_AHKWC7AFX7/ 

cd 250915_A01742_0505_AH2NNKDRX7
bpm template run demux_bclconvert
```

## Parameters
- `bcl_dir` (required, str, exists: dir): Path to the Illumina BCL run directory.
- `run_fastq_screen` (bool, default `false`): Enable optional contamination screening.
- `thread_ratio` (float, default `0.8`): Fraction of idle CPUs allocated to demultiplexing/QC.
- `no_lane_splitting` (bool, default `true`): Produce one FASTQ per read/sample (not per lane).
- `sampleproject_subdirs` (bool, default `false`): Keep FASTQs in sample project subdirectories.
- `use_api_samplesheet` (bool, default `true`): Retrieve `samplesheet.csv` via post-render API hook.
- `gf_api_name` / `gf_api_pass` (optional): API credentials (env vars also supported).
- `agendo_id` (optional): API fallback identifier when flowcell lookup fails.

## Outputs
- Render target (project mode): `${ctx.project_dir}/${ctx.template.id}/`.
- Run directory: same as render target.
- FASTQ output (`sampleproject_subdirs = true`): bcl-convert creates project subfolders.
- FASTQ output (`sampleproject_subdirs = false`): FASTQs are written under `./output/`.
- Other outputs:
  - `samplesheet.csv` (rendered; overwritten by API hook when enabled).
  - `run.sh` in the run directory.
  - `results/run_info.yaml` with run metadata, selected parameters, and software versions.
  - `results/bcl_convert.log` with streamed demultiplexing output.
  - `results/fastqc.log` with streamed FastQC output.
  - `results/multiqc.log` with streamed MultiQC output.
  - `results/fastq_screen.log` when `run_fastq_screen=true`.
  - `multiqc/multiqc_report.html`.

## Published Keys
- `FASTQ_dir`: Host-aware path to the chosen FASTQ directory.
- `multiqc_report`: Host-aware path to the MultiQC HTML report.

## Methods and Citations
- Publication-grade methods text: `METHODS.md`.
- Machine-readable references for BPM agent: `citations.yaml`.
- Manuscript bibliography source (for Quarto/Pandoc): `references.bib`.

## Version Provenance
This template captures versions from tools executed in `run.sh` and writes them to `results/run_info.yaml`. The primary commands are:
- `bcl-convert --version`
- `fastqc --version`
- `fastq_screen --version`
- `multiqc --version`

## Notes
- Primary scientific provenance is defined by:
  - runtime workflow in `run.sh.j2`
  - configured values in `template_config.yaml` and rendered parameters
- Post-render hook fetches samplesheet when `use_api_samplesheet=true`.
- API URL (flowcell): `https://genomics.rwth-aachen.de/api/get/samplesheet/flowcell/{flowcell}`.
- API URL (Agendo request): `https://genomics.rwth-aachen.de/api/get/samplesheet/request/{id}`.
- Credentials: params `gf_api_name`/`gf_api_pass` or env `GF_API_NAME`/`GF_API_PASS`.
- Flowcell id is derived from the last underscore-delimited token in `bcl_dir`; if missing, render fails. `agendo_id` is only used on flowcell 404 responses.
- Render aborts if samplesheet fetch fails.
- The run script prints explicit phase banners before `bcl-convert`, FastQC, optional FastQ Screen, and MultiQC.
