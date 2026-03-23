# demux_bclconvert


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: demux_bclconvert
kind: template
description: Demultiplex Illumina BCLs using bcl-convert, with optional Falco, fastq_screen,
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
  - falco --version
  - fastq_screen --version
  - multiqc --version
  - kraken2 --version
  - bracken -v
render_file_count: 8
```
<!-- AGENT_METADATA_END -->

Demultiplex Illumina BCLs using the system `bcl-convert` binary, then run Pixi-managed Falco quality control, optional contamination screening, and MultiQC summarization.

## Usage
Render first, then run from the rendered directory. In ad-hoc mode BPM writes a `bpm.meta.yaml` into the output folder so later `bpm template run` and `bpm template publish` can reuse the same rendered context.

Explicit ad-hoc output directory:

```bash
cd /data/fastq
bpm template render demux_bclconvert \
  --out 251209_NB501289_0978_AHKWC7AFX7 \
  --param bcl_dir=/data/raw/nextseq500_NB501289/251209_NB501289_0978_AHKWC7AFX7
cd 251209_NB501289_0978_AHKWC7AFX7
bpm template run demux_bclconvert
```

Resolver-derived ad-hoc output directory (folder name comes from the basename of `bcl_dir`):

```bash
cd /data/fastq
bpm template render demux_bclconvert \
  --adhoc \
  --bcl /data/raw/novaseq_A01742/260320_A01742_0619_AHHT35DRX7/ \
  --agendo-id 5499
cd 260320_A01742_0619_AHHT35DRX7
bpm template run demux_bclconvert
```

## Parameters
- `bcl_dir` (required, str, exists: dir): Path to the Illumina BCL run directory.
- `contamination_method` (str, default `none`): `none`, `fastq_screen`, `kraken2`, or `kraken2_bracken`.
- `kraken2_db` (str, default `/data/shared/databases/kraken2/standard/current`): Shared Kraken2 database path.
- `kraken2_confidence` (float, default `0.0`): Kraken2 confidence threshold.
- `bracken_read_length` (int, default `0`): Read length used for Bracken database assets. Leave at `0` to auto-detect the dominant read length from demultiplexed FASTQs.
- `run_fastq_screen` (bool, default `false`): Backward-compatibility switch. If `contamination_method=none`, this enables `fastq_screen`.
- `thread_ratio` (float, default `0.8`): Fraction of idle CPUs allocated to demultiplexing/QC.
- `no_lane_splitting` (bool, default `true`): Produce one FASTQ per read/sample (not per lane). Currently set via `--param no_lane_splitting=false` because no dedicated CLI flag is declared in the descriptor.
- `sampleproject_subdirs` (bool, default `false`): Keep FASTQs in sample project subdirectories. Currently set via `--param sampleproject_subdirs=true` because no dedicated CLI flag is declared in the descriptor.
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
  - `samplesheet.csv` (rendered by default; replaced by the API response when found, otherwise left unchanged on API 404).
  - `pixi.toml` for non-`bcl-convert` tooling.
  - `run.sh` in the run directory.
  - `collect_versions.sh` helper script for software-version capture.
  - `build_fastq_manifest.py` helper script for FASTQ discovery and SE/PE detection.
  - `process_fastqs.py` helper script for Falco and contamination backends.
  - `results/run_info.yaml` with run metadata, selected parameters, and software versions.
  - `results/run.log` with the combined stdout/stderr stream when `script(1)` is available on the host.
  - `results/fastq_manifest.csv` with detected read mode and paired FASTQ paths.
  - `results/bracken_read_length.txt` when Bracken auto-detects or resolves a read length.
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
- `pixi run falco --version`
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
- If `contamination_method=kraken2_bracken` and `bracken_read_length=0`, the template auto-detects the dominant read length from the demultiplexed FASTQs and records the resolved value in `results/run_info.yaml`.
- If required Kraken2 or Bracken assets are missing, the template fails with explicit build commands for the expected path.
- Post-render hook fetches `samplesheet.csv` when `use_api_samplesheet=true`.
- API URL (flowcell): `https://genomics.rwth-aachen.de/api/get/samplesheet/flowcell/{flowcell}`.
- API URL (Agendo request): `https://genomics.rwth-aachen.de/api/get/samplesheet/request/{id}`.
- Credentials: params `gf_api_name`/`gf_api_pass` or env `GF_API_NAME`/`GF_API_PASS`.
- Flowcell id is derived from the last underscore-delimited token in `bcl_dir`; `agendo_id` is only queried after a flowcell-side `404 Not Found`.
- When the API returns `404`, render continues and prints the API detail message, leaving the rendered `samplesheet.csv` in place. Other API and network errors still abort.
- In ad-hoc mode, the output resolver derives the render directory from `Path(bcl_dir).name` unless you pass `--out` explicitly.
- The run script prints explicit phase banners before metadata collection, demultiplexing, FASTQ-manifest generation, Falco, optional contamination screening, and MultiQC.
