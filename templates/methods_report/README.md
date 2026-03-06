# methods_report


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: methods_report
kind: template
description: Generate a publication-oriented methods draft from project.yaml template history.
descriptor: templates/methods_report/template_config.yaml
required_params: []
optional_params:
- methods_style
- methods_output
cli_flags:
  methods_style: --methods-style
  methods_output: --methods-output
run_entry: null
publish_keys: []
render_file_count: 1
```
<!-- AGENT_METADATA_END -->

Generate publication-ready methods text from project template history without coupling to the `export` template.

## Usage
Run from project directory:

```bash
bpm template render methods_report
```

Customize output:

```bash
bpm template render methods_report --methods-style concise --methods-output methods_for_publication.md
```

## Parameters
- `methods_style` (str, default `full`): Methods output style (`full` or `concise`).
- `methods_output` (str, default `auto_methods.md`): Output filename created under `methods_report/`.

## Output
- `methods_report/<methods_output>` generated on render by `hooks.generate_methods_report:main`.

## Notes
- Source of truth is `project.yaml` template history, plus template metadata files (`METHODS.md`, `citations.yaml`) and run artifacts (`results/run_info.yaml`).
- If automatic generation fails, a fallback note with manual command is written to the output file.

