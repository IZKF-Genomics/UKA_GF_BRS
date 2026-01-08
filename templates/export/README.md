# export

Build and submit an export engine job spec from a template mapping table and the current project state.

## Usage
1) Render into a project:
   `bpm template render export --dir /path/to/project`
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
`export_mapping.table.yaml` uses JSON-aligned keys:
```
template_id: <template id>
src: <relative or absolute source path>
src_published_key: <optional key from project.yaml published map>
dest: <relative destination path>
report_section: raw|processed|reports|general
description: <optional text>
```

## Notes
- The job spec is filtered to templates already present in `project.yaml`.
- If the project already published `FASTQ_dir` or `multiqc_report` for
  `demux_bclconvert`, those paths are used as sources.
- Authors are taken from `project.yaml` (formatted as `Name, Affiliation`).
- `src` is absolute in JSON by combining the project root with relative paths.
- The table supports `{template_id}` placeholders in `dest`.
