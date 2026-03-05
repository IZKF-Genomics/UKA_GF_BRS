# ref_genomes


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: ref_genomes
kind: template
description: 'Reference genomes manager: download FASTA/annotation, build indices
  with local tools, and create ERCC-augmented indices. Optimized for ad-hoc usage
  (--out).'
descriptor: templates/ref_genomes/template_config.yaml
required_params: []
optional_params: []
cli_flags: {}
run_entry: run.sh
publish_keys: []
render_file_count: 7
```
<!-- AGENT_METADATA_END -->

Download reference genomes, build indices, and create ERCC-augmented indices.

## Usage
1) Render into your references root (e.g., /data/genomes):
   `bpm template render ref_genomes --out /data/genomes`
2) Install tools with Pixi:
   `cd /data/genomes && pixi install`
3) Edit `genomes.yaml` to add/remove genomes or tools.
4) Build:
   `./run.sh`

## Parameters
- None. Configure inputs in `genomes.yaml`.

## Outputs
- Reference genome downloads and indices under the output directory.
- ERCC-augmented indices for each genome.

## Notes
- Use `FORCE=1` to re-download and rebuild indices.
