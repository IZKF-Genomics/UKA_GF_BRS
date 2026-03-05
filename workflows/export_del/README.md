# export_del


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: export_del
kind: workflow
description: Delete an exported project by project_id or job_id.
descriptor: workflows/export_del/workflow_config.yaml
required_params: []
optional_params:
- api_url
- job_id
- project_id
cli_flags:
  project_id: --project-id
  api_url: --api-url
run_entry: run.py
tools_required:
- python
tools_optional: []
```
<!-- AGENT_METADATA_END -->

Delete an exported project by project ID.

## Run
```
bpm workflow run export_del --project-id PROJECT_ID
bpm workflow run export_del --project-id PROJECT_ID --api-url http://genomics.rwth-aachen.de:9500/export
```

## Parameters
See `workflow_config.yaml` for all parameters and defaults.
