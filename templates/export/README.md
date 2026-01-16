# export

Build and submit an export engine job spec from a rule-based mapping table and
project.yaml state.

## Usage
1) Render into a project (run from the project directory):
   `bpm template render export`
2) Inspect `export_job_spec.json` and confirm fields/paths.
3) Submit to the export engine:
   `bpm template run export --dir /path/to/project`
4) Check `project.yaml` for `templates[].published.export_job_id`.

## Parameters
- `export_engine_api_url` (str): Base URL for the export engine API (no trailing `/export`).
- `export_engine_backends` (str): Comma-separated backends for the job spec.
- `export_expiry_days` (int): Expiry days for the job spec.

## Outputs
- `export_job_spec.json`: JSON payload sent to the export engine.

## Mapping Table
The mapping table lives at `export_mapping.table.yaml`. Each entry becomes one
or many export spec entries depending on its rule. Report visibility is always
controlled by `include_in_report`.

### Rule Summary
- `tree`: export a whole folder as a single export entry.
- `folder`: export a specific subfolder as a single entry.
- `file`: export a specific file as a single entry.
- `glob`: expand a pattern into multiple file entries.

### Required Keys
```
template_id: <template id>
rule: tree|folder|file|glob
```

### Source Keys (pick one)
```
src: <relative or absolute source path>
src_project_key: <path in project.yaml>
src_published_key: <key under templates[].published>  # legacy shortcut
```
Precedence: `src_project_key` -> `src_published_key` -> `src`.

### Destination Keys
```
dest: <relative destination path>  # required for tree/folder/file/glob
```

### Optional Keys
```
report_section: raw|processed|reports|general  # default: general
include_in_report: true|false                  # default: true
mode: symlink|copy|...                          # default: symlink
project: <override project name>
host: <override host>
description: <free text>
```

### Placeholders
- `{template_id}`: the template id from the mapping entry.
- `{template_root}`: the resolved template folder path in the project.
- `{basename}`: matched file name with extension, e.g. `multiqc_report.html` (glob only).
- `{stem}`: matched file name without extension, e.g. `multiqc_report` (glob only).
- `{relpath}`: matched path relative to `{template_root}` (glob only).

### src_project_key Path Syntax
`src_project_key` points into `project.yaml` using dot + selector syntax.

Examples:
- `project_name`
- `authors[0].name`
- `templates[id=nfcore_rnaseq].params.output_dir`
- `templates[id=demux_bclconvert].published.FASTQ_dir`

The resolved value must be a string path. If it includes a host prefix
(e.g. `host:/abs/path`), the host is preserved.

### Behavior Notes
- Only entries whose `template_id` exists in `project.yaml` are processed.
- `glob` expands to one entry per matched file.
- Missing sources are skipped silently.

## Example Mapping
```
mappings:
  - template_id: nfcore_rnaseq
    rule: tree
    src: "{template_root}"
    dest: "2_Processed_data/nfcore_rnaseq"
    report_section: processed
    include_in_report: true
    description: "All nfcore_rnaseq outputs"

  - template_id: demux_bclconvert
    rule: file
    src_project_key: "templates[id=demux_bclconvert].published.multiqc_report"
    src: demux_bclconvert/multiqc/multiqc_report.html
    dest: "1_Raw_data/demultiplexing_multiqc_report.html"
    report_section: raw
    include_in_report: true
    description: "MultiQC report"

  - template_id: nfcore_3mrnaseq
    rule: glob
    src: "{template_root}/results/**/*.{csv,tsv}"
    dest: "2_Processed_data/nfcore_3mrnaseq/results/{relpath}"
    report_section: processed
    include_in_report: true
    description: "Result tables"

  - template_id: nfcore_3mrnaseq
    rule: file
    src: "{template_root}/results/qc/summary.txt"
    dest: "2_Processed_data/nfcore_3mrnaseq/qc/summary.txt"
    report_section: reports
    include_in_report: false
    description: "QC summary (exported, not shown in report)"

```

## Notes
- `export_job_spec.json` is created by the post-render hook.
- Authors are taken from `project.yaml` and formatted as `Name, Affiliation`.
- `src` values that are relative are resolved against the project root.
