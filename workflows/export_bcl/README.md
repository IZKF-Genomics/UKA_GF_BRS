# export_bcl


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: export_bcl
kind: workflow
description: Export raw BCL data from a sequencing run directory.
descriptor: workflows/export_bcl/workflow_config.yaml
required_params:
- run_dir
optional_params:
- bcl_dir
- export_engine_api_url
- export_engine_backends
- export_expiry_days
- export_password
- export_username
- include_in_report
- include_in_report_bcl
- project_name
cli_flags:
  run_dir: --run-dir
  project_name: --project-name
  bcl_dir: --bcl-dir
run_entry: run.py
tools_required:
- python
tools_optional: []
```
<!-- AGENT_METADATA_END -->

Export raw BCL data from a sequencing run directory without demultiplexing.

## Run
```
bpm workflow run export_bcl --run-dir /absolute/path/to/run --project-name PROJECT_NAME
```

## Notes
- `--run-dir` should point to the sequencing run directory (the workflow exports the entire run directory).
- Use `--bcl-dir` to override the default directory if needed.
- See `workflow_config.yaml` for all parameters.
