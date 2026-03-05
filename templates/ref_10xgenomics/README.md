# ref_10xgenomics


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: ref_10xgenomics
kind: template
description: Download and extract 10x Genomics reference indices. Optimized for ad-hoc
  usage (--out).
descriptor: templates/ref_10xgenomics/template_config.yaml
required_params: []
optional_params: []
cli_flags: {}
run_entry: run.sh
publish_keys: []
render_file_count: 2
```
<!-- AGENT_METADATA_END -->

Download and extract 10x Genomics reference indices.

## Usage
1) Render into your references root (e.g., /data/shared/10xGenomics):
   `bpm template render ref_10xgenomics --out /data/shared/10xGenomics`
2) Download and extract:
   `./run.sh`

## Parameters
- None.

## Outputs
- 10x reference tarballs and extracted reference folders under the output directory.
