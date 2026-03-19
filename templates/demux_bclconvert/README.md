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
- templates/demux_bclconvert/collect_versions.sh.j2
- templates/demux_bclconvert/build_fastq_manifest.py.j2
- templates/demux_bclconvert/process_fastqs.py.j2
- templates/demux_bclconvert/pixi.toml
- templates/demux_bclconvert/template_config.yaml
methods_file: templates/demux_bclconvert/METHODS.md
citations_file: templates/demux_bclconvert/citations.yaml
bibliography_file: templates/demux_bclconvert/references.bib
required_params:
- bcl_dir
optional_params:
- agendo_id
- bracken_read_length
- contamination_method
- gf_api_name
- gf_api_pass
- kraken2_confidence
- kraken2_db
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
  contamination_method: --contamination-method
  kraken2_db: --kraken2-db
  kraken2_confidence: --kraken2-confidence
  bracken_read_length: --bracken-read-length
  thread_ratio: --thread-ratio
run_entry: run.sh
publish_keys:
- FASTQ_dir
- multiqc_report
software_version_capture:
  run_info: results/run_info.yaml
  commands:
  - bcl-convert --version
  - pixi --version
  - fastqc --version
  - fastq_screen --version
  - multiqc --version
  - kraken2 --version
  - bracken -v
render_file_count: 8
```
<!-- AGENT_METADATA_END -->

Demultiplex Illumina BCLs using the system `bcl-convert` binary, then run Pixi-managed FASTQ quality control, optional contamination screening, and MultiQC summarization.

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
- `contamination_method` (str, default `none`): `none`, `fastq_screen`, `kraken2`, or `kraken2_bracken`.
- `kraken2_db` (str, default `/data/shared/databases/kraken2/standard/current`): Shared Kraken2 database path.
- `kraken2_confidence` (float, default `0.0`): Kraken2 confidence threshold.
- `bracken_read_length` (int, default `151`): Read length used for Bracken database assets.
- `run_fastq_screen` (bool, default `false`): Backward-compatibility switch. If `contamination_method=none`, this enables `fastq_screen`.
- `thread_ratio` (float, default `0.8`): Fraction of idle CPUs allocated to demultiplexing/QC.
- `no_lane_splitting` (bool, default `true`): Produce one FASTQ per read/sample (not per lane).
- `sampleproject_subdirs` (bool, default `false`): Keep FASTQs in sample project subdirectories.
- `use_api_samplesheet` (bool, default `true`): Retrieve `samplesheet.csv` via post-render API hook.
- `gf_api_name` / `gf_api_pass` (optional): API credentials (env vars also supported).
- `agendo_id` (optional): API fallback identifier when flowcell lookup fails.

## Outputs
- Render target (project mode): `${ctx.project_dir}/${ctx.template.id}/`.
- Run directory: same as render target.
- FASTQ output root: `./output/`.
- FASTQ output (`sampleproject_subdirs = true`): bcl-convert creates project/sample subfolders under `./output/`.
- FASTQ output (`sampleproject_subdirs = false`): FASTQs are written directly under `./output/`.
- Other outputs:
  - `samplesheet.csv` (rendered; overwritten by API hook when enabled).
  - `pixi.toml` for non-`bcl-convert` tooling.
  - `run.sh` in the run directory.
  - `collect_versions.sh` helper script for software-version capture.
  - `build_fastq_manifest.py` helper script for FASTQ discovery and SE/PE detection.
  - `process_fastqs.py` helper script for FastQC and contamination backends.
  - `results/run_info.yaml` with run metadata, selected parameters, and software versions.
  - `results/run.log` with the full combined stdout/stderr stream from the run.
  - `results/fastq_manifest.csv` with detected read mode and paired FASTQ paths.
  - `multiqc/multiqc_report.html`.
  - `kraken2/` and `bracken/` result folders when those methods are enabled.

## Published Keys
- `FASTQ_dir`: Host-aware path to the FASTQ output root directory.
- `multiqc_report`: Host-aware path to the MultiQC HTML report.

## Methods and Citations
- Publication-grade methods text: `METHODS.md`.
- Machine-readable references for BPM agent: `citations.yaml`.
- Manuscript bibliography source (for Quarto/Pandoc): `references.bib`.

## Version Provenance
This template captures versions through `collect_versions.sh`, called from `run.sh`, and writes them to `results/run_info.yaml`. The primary commands are:
- `bcl-convert --version`
- `pixi --version`
- `pixi run fastqc --version`
- `pixi run fastq_screen --version`
- `pixi run multiqc --version`
- `pixi run kraken2 --version`
- `pixi run bracken -v`

## Notes
- Primary scientific provenance is defined by:
  - runtime workflow in `run.sh.j2`
  - configured values in `template_config.yaml` and rendered parameters
- `bcl-convert` remains a system dependency and is not managed by Pixi.
- All other QC/classification tooling is expected to come from the rendered `pixi.toml`.
- The run script captures the full interactive terminal session with `script(1)` into `results/run.log`, so tools like `bcl-convert` can keep their native live stdout/stderr behavior while still producing one combined log file.
- The template generates `results/fastq_manifest.csv` and automatically detects single-end versus paired-end FASTQ outputs after demultiplexing.
- Kraken2/Bracken databases are expected under shared storage, for example `/data/shared/databases/`.
- If required Kraken2 or Bracken assets are missing, the template fails with explicit build commands for the expected path.
- Post-render hook fetches samplesheet when `use_api_samplesheet=true`.
- API URL (flowcell): `https://genomics.rwth-aachen.de/api/get/samplesheet/flowcell/{flowcell}`.
- API URL (Agendo request): `https://genomics.rwth-aachen.de/api/get/samplesheet/request/{id}`.
- Credentials: params `gf_api_name`/`gf_api_pass` or env `GF_API_NAME`/`GF_API_PASS`.
- Flowcell id is derived from the last underscore-delimited token in `bcl_dir`; if missing, render fails. `agendo_id` is only used on flowcell 404 responses.
- Render aborts if samplesheet fetch fails.
- The run script prints explicit phase banners before metadata collection, demultiplexing, FASTQ-manifest generation, FastQC, optional contamination screening, and MultiQC.
