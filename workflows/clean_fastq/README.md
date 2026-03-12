# clean_fastq


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: clean_fastq
kind: workflow
description: Clean FASTQ run folders by removing pattern-matched content without archiving.
descriptor: workflows/clean_fastq/workflow_config.yaml
required_params: []
optional_params:
- source_root
- retention_days
- clean_patterns
- skip_runs
- non_interactive
- interactive
- yes
- dry_run
- manifest_path
- manifest_dir
- keep_rules_path
cli_flags:
  source_root: --source-root
  retention_days: --retention-days
  clean_patterns: --clean-patterns
  skip_runs: --skip-runs
  non_interactive: --non-interactive
  yes: --yes
  dry_run: --dry-run
  keep_rules_path: --keep-rules-path
run_entry: run.py
tools_required:
- python
tools_optional: []
```
<!-- AGENT_METADATA_END -->

Remove pattern-matched files/directories directly from `/data/fastq` run folders without any archive step.

## Default behavior
- Source root: `/data/fastq`
- Source layout: flat run directories directly under source root
- Keep rules: `/data/shared/bpm_manifests/keep_rules.yaml` (active keep entries are auto-skipped)
- Retention reference: prefer `bpm.meta.yaml -> export.last_exported_at`, fallback to run directory name prefix `YYMMDD_`
- Retention: keep recent 90 days; clean only runs strictly older than cutoff based on the retention reference
- Default clean patterns:
  - `*.fastq.gz`
  - `*.fq.gz`
  - `.pixi`
  - `work`
  - `.renv`
  - `.Rproj.user`
  - `.nextflow`
  - `.nextflow.log*`

## Run
```bash
bpm workflow run clean_fastq
```

## Common examples
```bash
# Cron-safe shortcut
bpm workflow run clean_fastq --non-interactive true

# Dry-run only
bpm workflow run clean_fastq --dry-run true

# Keep defaults but skip selected runs
bpm workflow run clean_fastq --skip-runs 250704_A01742_0465_AH227MDSXF,250818_LH00452_0279_B22YHHTLT4_6
```

## Output
- Writes a manifest JSON with per-run cleanup status.
- Writes a text log file in the same folder.
- Uses lock file `/tmp/clean_fastq.lock`.

## Safety
- Global confirmation required unless `yes=true`.
- Supports `non_interactive=true` for cron-safe execution.
- Uses retention-days filtering and explicit skip-runs.
- Automatically excludes run IDs protected by active keep-rules entries.
- Default clean patterns are always enforced.
