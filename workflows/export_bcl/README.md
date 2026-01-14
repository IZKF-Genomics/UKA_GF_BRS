# export_bcl

Export raw BCL data from a sequencing run directory without demultiplexing.

## Run
```
bpm workflow run export_bcl --run-dir /absolute/path/to/run --project-name PROJECT_NAME
```

## Notes
- `--run-dir` should point to the sequencing run directory (the workflow exports the entire run directory).
- Use `--bcl-dir` to override the default directory if needed.
- See `workflow_config.yaml` for all parameters.
