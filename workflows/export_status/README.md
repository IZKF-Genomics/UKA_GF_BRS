# export_status


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: export_status
kind: workflow
description: Check export engine job status for the current project.
descriptor: workflows/export_status/workflow_config.yaml
required_params: []
optional_params:
- api_url
- job_id
cli_flags:
  job_id: --job-id
  api_url: --api-url
run_entry: run.py
tools_required:
- python
tools_optional: []
```
<!-- AGENT_METADATA_END -->

Check export engine job status for the current project.

## Run
```
bpm workflow run export_status --job-id JOB_ID
```

## Parameters
See `workflow_config.yaml` for all parameters and defaults.
