# illumina_methylation_array

Config-driven Illumina Infinium methylation array pipeline template built with:
- Quarto (`.qmd`) for step execution + HTML reporting
- R/Bioconductor (`minfi`, `limma`, `missMethyl`) for array analysis
- Pixi for environment management and reproducible tasks

## What this template provides

This template scaffolds a full Quarto project with the required repo layout from the proposal:
- `config/` for study config + sample sheet
- `steps/` for sequential `.qmd` reports (load -> QC -> normalize -> filter -> DMP/DMR -> enrichment -> drilldown -> index)
- `lib/` shared R helpers for config parsing, validation, artifact IO, plotting, and logging
- `run.sh` for one-command execution with logging

## Current status

This is a production-oriented scaffold with the core contracts implemented:
- Config + sample sheet loading/validation
- SentrixBarcode/SentrixPosition -> IDAT basename resolution
- Missing IDAT pair checks
- Artifact persistence (`results/rds`, `results/tables`, `results/figures`, `results/logs`)
- Quarto project output to `reports/`
- DMP and enrichment step skeletons wired to config

Some domain-specific filters (SNP/cross-reactive list sourcing) and optional DMR/cell-composition details are left as documented extension points in `lib/` and the `.qmd` steps.

## Render the template

```bash
bpm template render illumina_methylation_array   --param study_name=MyStudy   --param idat_base_dir=data/idat   --param array_type=EPIC   --dir /path/to/project
```

## Run

```bash
bpm template run illumina_methylation_array --dir /path/to/project
```

Or inside the rendered folder:

```bash
./run.sh
```

## Configure before running

1. Edit `config/project.toml`.
2. Fill `config/samples.csv` with real metadata including:
   - `sample_id`
   - `group`
   - `SentrixBarcode`
   - `SentrixPosition`
3. Place IDAT files under the configured `idat.base_dir`.

## Notes

- `pixi.lock` is not shipped in this scaffold. Generate it after rendering with `pixi lock` (or `pixi install`) in your environment and commit it for reproducibility.
- `missMethyl::gometh` enrichment is the default and includes methylation-specific bias correction. The template warns/guards around `EPIC_V2` support depending on installed package versions.
