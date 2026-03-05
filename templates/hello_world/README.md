# hello_world


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: hello_world
kind: template
description: A demo template that prints a greeting and project name.
descriptor: templates/hello_world/template_config.yaml
required_params:
- name
optional_params:
- include_time
- items
cli_flags:
  name: --name
  include_time: --include-time
  items: --items
run_entry: run.sh
publish_keys:
- greeting
render_file_count: 1
```
<!-- AGENT_METADATA_END -->

A demo template that prints a greeting and project name.

## Render
Run from the project directory (where project.yaml lives).
```
bpm template render hello_world --param name=Alice
```

## Run
```
bpm template run hello_world --dir /path/to/project
```

## Parameters
See `template_config.yaml` for the full parameter list and defaults.
