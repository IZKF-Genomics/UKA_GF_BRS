# scrnaseq_pipeline


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: scrnaseq_pipeline
kind: template
description: Single-cell RNA-seq notebook pipeline (monolithic).
descriptor: templates/scrnaseq_pipeline/template_config.yaml
required_params: []
optional_params:
- auto_find
- dir_samples
- organism
- technology
cli_flags:
  dir_samples: --dir-samples
  technology: --technology
  organism: --organism
  auto_find: --auto-find
run_entry: run.sh
publish_keys: []
render_file_count: 11
```
<!-- AGENT_METADATA_END -->

Single-cell RNA-seq notebook pipeline (monolithic). This template mirrors the original module layout and runs the preprocessing and annotation notebooks.

## Render
Run from the project directory (where project.yaml lives).
```
bpm template render scrnaseq_pipeline
```

## Run
```
bpm template run scrnaseq_pipeline --dir /path/to/project
```

## Parameters
- dir_samples: overrides Cell Ranger count input directory.
- technology: 10x, ParseBio, or Singleron.
- organism: human or mouse.
- auto_find: auto-discover samples in dir_samples.
