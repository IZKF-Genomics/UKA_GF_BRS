# ref_genome_blacklists


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: ref_genome_blacklists
kind: template
description: Download Boyle-Lab blacklist v2 BED files. Optimized for ad-hoc usage
  (--out).
descriptor: templates/ref_genome_blacklists/template_config.yaml
required_params: []
optional_params: []
cli_flags: {}
run_entry: run.sh
publish_keys: []
render_file_count: 2
```
<!-- AGENT_METADATA_END -->

Download Boyle-Lab blacklist v2 BED files.

Source:
- https://github.com/Boyle-Lab/Blacklist/tree/master/lists

## Usage
1) Render into your references root (e.g., /data/ref_genome_blacklists):
   `bpm template render ref_genome_blacklists --out /data/ref_genome_blacklists`
2) Download files:
   `./run.sh`

## Parameters
- None.

## Outputs
- v2 blacklist BED files under the output directory.
