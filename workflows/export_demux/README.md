# export_demux


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: export_demux
kind: workflow
description: Export FASTQs and MultiQC from an ad-hoc demux_bclconvert run.
descriptor: workflows/export_demux/workflow_config.yaml
required_params:
- run_dir
optional_params:
- export_engine_api_url
- export_engine_backends
- export_expiry_days
- export_password
- export_username
- project_name
cli_flags:
  run_dir: --run-dir
  project_name: --project-name
run_entry: run.py
tools_required:
- python
tools_optional: []
```
<!-- AGENT_METADATA_END -->

Export FASTQs and MultiQC from an ad-hoc demux_bclconvert run.

## Run
```
bpm workflow run export_demux --run-dir /absolute/path/to/run --project-name PROJECT_NAME
```

## Notes
- `--run-dir` should point to a demux run directory containing `output/` and `multiqc/`
  (or a `bpm.meta.yaml` with published paths).
- `export_job_spec.json` includes report links under `export_list[].report_links`
  for FASTQ and MultiQC entries.
- Host-prefixed published paths (e.g., `nextgen:/path`) are preserved as export hosts.
- See `workflow_config.yaml` for all parameters.
