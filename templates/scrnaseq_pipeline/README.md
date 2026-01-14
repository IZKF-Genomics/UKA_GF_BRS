# scrnaseq_pipeline

Single-cell RNA-seq notebook pipeline (monolithic). This template mirrors the original module layout and runs the preprocessing and annotation notebooks.

## Render
```
bpm template render scrnaseq_pipeline --dir /path/to/project
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
