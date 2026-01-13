# export_demux

Export FASTQs and MultiQC from an ad-hoc demux_bclconvert run.

## Run
```
bpm workflow run export_demux --run-dir /absolute/path/to/run --project-name PROJECT_NAME
```

## Notes
- `--run-dir` should point to a demux run directory containing `output/` and `multiqc/`
  (or a `bpm.meta.yaml` with published paths).
- See `workflow_config.yaml` for all parameters.
