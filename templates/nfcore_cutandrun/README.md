# nfcore_cutandrun


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: nfcore_cutandrun
kind: template
description: nf-core/cutandrun wrapper; requires genome and a samplesheet.csv in the
  template directory.
descriptor: templates/nfcore_cutandrun/template_config.yaml
required_params:
- genome
optional_params:
- dedup_target_reads
- igg_scale_factor
- max_cpus
- max_memory
- normalisation_mode
- peakcaller
- spikein_bowtie2
- spikein_fasta
- use_control
cli_flags:
  genome: --genome
  normalisation_mode: --norm-mode
  peakcaller: --peakcaller
  use_control: --use_control
  igg_scale_factor: --igg-scale-factor
  dedup_target_reads: --dedup-target-reads
  spikein_fasta: --spikein-fasta
  spikein_bowtie2: --spikein-bowtie2
  max_cpus: --max-cpus
  max_memory: --max-memory
run_entry: run.sh
publish_keys:
- nfcore_multiqc
- nfcore_samplesheet
render_file_count: 2
```
<!-- AGENT_METADATA_END -->

nf-core/cutandrun wrapper for CUT&RUN and CUT&Tag data.

## Render
Run from the project directory (where project.yaml lives).
```
bpm template render nfcore_cutandrun --genome GRCh38 --agendo-id 12345
```

## Run
```
bpm template run nfcore_cutandrun --dir /path/to/project
```

## Notes
- Provide `samplesheet.csv` in the template directory (see nf-core/cutandrun samplesheet format).
- Spike-in normalization requires spike-in references; see `nextflow.config` for guidance.

## Parameters
See `template_config.yaml` for the full parameter list and defaults.
