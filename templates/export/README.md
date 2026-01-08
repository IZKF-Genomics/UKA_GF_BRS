# export template

This template builds a JSON export job spec from a simple mapping table and the
current project state.

## What it does
- Post-render hook reads the mapping table and filters it to templates used in
  the current project, then writes `export_job_spec.json`.
- Render writes `run.py` into the template folder.
- Run submits `export_job_spec.json` to the export engine and writes the
  returned `job_id` into `project.yaml` under this template’s `published` map.

## Files
- `export_mapping.table.yaml`: Default mapping table for all templates.
- `export_job_spec.json`: Rendered export-engine job spec for this project.
- `run.py`: submits the job spec JSON and records `export_job_id`.

## Usage
1) Render into a project:
   `bpm template render export --dir /path/to/project`
2) Inspect `export_job_spec.json` and confirm fields/paths.
3) Run to submit:
   `bpm template run export --dir /path/to/project`
4) Check `project.yaml` for `templates[].published.export_job_id`.

## Mapping format
The mapping table uses JSON-aligned keys:
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
- The table supports `{template_id}` placeholders in `dest`.
