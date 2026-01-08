# export template

This template builds a JSON export job spec from a simple mapping table and the
current project state.

## What it does
- Post-render hook reads the mapping table and filters it to templates used in
  the current project, then writes `export_job_spec.json`.
- Render writes `run.py` into the template folder.
- Run checks that `export_job_spec.json` exists and is valid JSON.

## Files
- `export_mapping.table.yaml`: Default mapping table for all templates.
- `export_job_spec.json`: Rendered export-engine job spec for this project.
- `run.py`: validates the job spec JSON.

## Usage
1) Render into a project:
   `bpm template render export --dir /path/to/project`
2) Inspect `export_job_spec.json` and confirm fields/paths.
3) Run to validate:
   `bpm template run export --dir /path/to/project`
4) Submit the JSON to the export engine (outside BPM).

## Mapping format
The mapping table emits `export_list` entries in this format:
```
[section, source_path, target_dir, rename]
```
- `section`: label used by GPM for report grouping ("FASTQ" forces raw).
- `source_path`: path to export from (relative to project root or absolute).
- `target_dir`: destination folder passed to the export engine.
- `rename`: optional filename override (use `~` for null).

## Notes
- The job spec is filtered to templates already present in `project.yaml`.
- If the project already published `FASTQ_dir` or `multiqc_report` for
  `demux_bclconvert`, those paths are used as sources.
- Authors are taken from `project.yaml` (formatted as `Name, Affiliation`).
- The table supports `{template_id}` placeholders in `dest`.
