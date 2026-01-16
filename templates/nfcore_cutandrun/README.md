# nfcore_cutandrun

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
