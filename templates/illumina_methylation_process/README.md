# illumina_methylation_process

Preprocessing + clustering template for Illumina methylation arrays.

Scope:
- 01 load IDAT
- 02 QC
- 03 normalization
- 04 filtering
- 05 batch/cell adjustments
- 06 clustering

This template is intentionally comparison-free (no DMP/DMR/enrichment/drilldown).
Use `illumina_methylation_compare` for downstream case-control analyses.

## Render

```bash
bpm template render illumina_methylation_process \
  --param study_name=MyStudy \
  --param authors="Your Name" \
  --param idat_base_dir=data/idat \
  --param array_type=EPIC_V2 \
  --dir /path/to/project
```

## Run

```bash
bpm template run illumina_methylation_process --dir /path/to/project
# or inside rendered folder
./run.sh
```
