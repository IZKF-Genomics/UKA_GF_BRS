# hello_world


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: hello_world
kind: workflow
description: A demo workflow that prints a greeting and optional project name.
descriptor: workflows/hello_world/workflow_config.yaml
required_params:
- name
optional_params:
- include_time
cli_flags:
  name: --name
  include_time: --include-time
run_entry: run.sh
tools_required:
- python
tools_optional: []
```
<!-- AGENT_METADATA_END -->

A demo workflow that prints a greeting and optional project name.

## Run
```
bpm workflow run hello_world --name Alice
```

## Parameters
See `workflow_config.yaml` for the full parameter list and defaults.
