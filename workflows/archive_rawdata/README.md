# archive_rawdata


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: archive_rawdata
kind: workflow
description: Archive old raw sequencing run directories with rsync and verification, then write a cleanup manifest.
descriptor: workflows/archive_rawdata/workflow_config.yaml
required_params: []
optional_params:
- source_root
- target_root
- retention_days
- instrument_folders
- skip_runs
- non_interactive
- interactive
- yes
- dry_run
- min_free_gb
- manifest_path
- manifest_dir
- keep_rules_path
cli_flags:
  source_root: --source-root
  target_root: --target-root
  retention_days: --retention-days
  instrument_folders: --instrument-folders
  skip_runs: --skip-runs
  non_interactive: --non-interactive
  yes: --yes
  dry_run: --dry-run
  keep_rules_path: --keep-rules-path
run_entry: run.py
tools_required:
- python
- rsync
tools_optional: []
```
<!-- AGENT_METADATA_END -->

Archive old sequencing run directories from raw storage into archive storage.
This workflow does not delete source data. Cleanup is delegated to `archive_cleanup`.

## Default behavior
- Source root: `/data/raw`
- Target root: `/mnt/nextgen2/archive/raw`
- Manifest dir: `/data/shared/bpm_manifests`
- Keep rules: `/data/shared/bpm_manifests/keep_rules.yaml` (active keep entries are auto-skipped)
- Instrument allowlist:
  - `miseq1_M00818`
  - `miseq2_M04404`
  - `miseq3_M00403`
  - `nextseq500_NB501289`
  - `novaseq_A01742`
- Retention reference: prefer `bpm.meta.yaml -> export.last_exported_at`, fallback to run directory name prefix `YYMMDD_`
- Retention: keep recent 90 days; archive only runs strictly older than cutoff based on the retention reference
- Confirmation: one global confirmation for all selected runs

## Run
```bash
bpm workflow run archive_rawdata
```

## Common examples
```bash
# Cron-safe shortcut (implies --interactive false and --yes true)
bpm workflow run archive_rawdata --non-interactive true

# Keep defaults but skip selected old runs
bpm workflow run archive_rawdata --skip-runs 251030_A01742_0532_BH5MKFDRX7,260105_NB501289_0982_AHT27GBGYX

# Plan only (no copy)
bpm workflow run archive_rawdata --dry-run true
```

## Output manifest
- Writes a JSON manifest with per-run statuses (`copy_status`, `verify_status`, `cleanup_status`).
- Writes a text log file in the same folder and stores its path under `log_path` in the manifest.
- Performs an early writability preflight for manifest/log directories and fails before copy if not writable.
- Use `--manifest-dir` or `--manifest-path` only when you need to override the default location.
- `cleanup_status` is set to `pending_external_cleanup` for verified runs.

## Next step
Use `archive_cleanup` to consume this manifest and perform deletion safely, optionally under sudo.

## Safety checks
- Uses an allowlist of instrument folders.
- Requires global confirmation unless `yes=true`.
- Supports `non_interactive=true` as a cron-safe shortcut (`interactive=false`, `yes=true`).
- Performs preflight write checks on target root and instrument directories before any copy.
- Uses `rsync -a --human-readable --info=progress2 --no-inc-recursive --partial` for a single aggregated progress line (percent + ETA) per run.
- Verifies each copied run with `rsync -avhn --delete`.
- Uses lock file `/tmp/archive_rawdata.lock` to prevent concurrent runs.
- Automatically excludes run IDs protected by active keep-rules entries.

## CLI output
- Uses ANSI colors for headings, prompts, warnings, and final status in interactive terminals.
- Set `NO_COLOR=1` to disable colors.
