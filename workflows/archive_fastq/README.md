# archive_fastq


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: archive_fastq
kind: workflow
description: Archive old FASTQ run directories with rsync, verification, and post-verify cleanup.
descriptor: workflows/archive_fastq/workflow_config.yaml
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
- cleanup
- min_free_gb
- manifest_path
- manifest_dir
- exclude_patterns
- keep_rules_path
- tui
- investigate
- investigate_top
cli_flags:
  source_root: --source-root
  target_root: --target-root
  retention_days: --retention-days
  instrument_folders: --instrument-folders
  skip_runs: --skip-runs
  non_interactive: --non-interactive
  yes: --yes
  dry_run: --dry-run
  cleanup: --cleanup
  exclude_patterns: --exclude-patterns
  keep_rules_path: --keep-rules-path
  tui: --tui
  investigate: --investigate
  investigate_top: --investigate-top
run_entry: run.py
tools_required:
- python
- rsync
tools_optional: []
```
<!-- AGENT_METADATA_END -->

Archive old sequencing run directories from FASTQ storage into archive storage, verify the copy, and then remove the original source run directory.

## Default behavior
- Source root: `/data/fastq`
- Target root: `/mnt/nextgen2/archive/fastq`
- Manifest dir: `/data/shared/bpm_manifests`
- Keep rules: `/data/shared/bpm_manifests/keep_rules.yaml` (editable in the integrated TUI before planning; active keep entries are auto-skipped)
- Source layout: flat run directories directly under `/data/fastq` (no instrument folders)
- Retention reference: prefer `bpm.meta.yaml -> export.last_exported_at`, fallback to run directory name prefix `YYMMDD_`
- Retention: keep recent 90 days; archive only runs strictly older than cutoff based on the retention reference
- Confirmation: one global confirmation for all selected runs
- Cleanup: enabled by default after successful verification; the original source run directory is removed

## Run
```bash
bpm workflow run archive_fastq
```

Interactive terminals open one archive-candidate list only. It already applies retention filtering, and you can keep/unkeep runs there. Some rows may appear as `cleanup-only` when the run is already archived on the target and only source removal remains. After the archive copy is verified, or for cleanup-only rows when the target already exists, the workflow removes the source run directory. Use `--tui false` to skip the list, or `--cleanup false` for archive-only mode.

## Common examples
```bash
# Cron-safe shortcut (implies --interactive false and --yes true)
bpm workflow run archive_fastq --non-interactive true

# Keep defaults but skip selected old runs
bpm workflow run archive_fastq --skip-runs 251030_A01742_0532_BH5MKFDRX7,260105_NB501289_0982_AHT27GBGYX

# Plan only (no copy or cleanup)
bpm workflow run archive_fastq --dry-run true

# Investigate one run's included/excluded size details (no copy)
bpm workflow run archive_fastq --investigate 250818_LH00452_0279_B22YHHTLT4_6

# Investigate with wider top lists
bpm workflow run archive_fastq --investigate 250818_LH00452_0279_B22YHHTLT4_6 --investigate-top 50
```

## Output manifest
- Writes a JSON manifest with per-run statuses (`copy_status`, `verify_status`, `cleanup_status`).
- Writes a text log file in the same folder and stores its path under `log_path` in the manifest.
- Performs an early writability preflight for manifest/log directories and fails before copy if not writable.
- Use `--manifest-dir` or `--manifest-path` only when you need to override the default location.
- Verified runs are cleaned in the same workflow by default with `cleanup_mode=full_run_directory`.
- Already-archived cleanup-only runs are recorded in the same manifest with `cleanup_only=true`.
- Always excludes these patterns from archive copy/verify:
  - `*.fastq.gz`
  - `*.fq.gz`
  - `.pixi`
  - `work`
  - `.renv`
  - `.Rproj.user`
  - `.nextflow`
  - `.nextflow.log*`
  - `nohup.out`
  - `Logs`
  - `Reports`
- Exclude patterns affect what is copied to archive, but they do not protect source files from cleanup.
- Set `--cleanup false` if you want archive-only behavior.


## Safety checks
- Uses flat run-directory discovery under `/data/fastq` (ignores instrument_folders filter).
- Requires global confirmation unless `yes=true`.
- Supports `non_interactive=true` as a cron-safe shortcut (`interactive=false`, `yes=true`).
- Performs preflight write checks on target root, instrument directories, and any pre-existing target run directories before any copy.
- Uses `rsync -a --human-readable --info=progress2 --no-inc-recursive --partial --omit-dir-times --no-perms --no-group` for archive copy, so target permission/group metadata is ignored.
- Verifies each copied run with `rsync -avhn --omit-dir-times --no-perms --no-group`.
- Uses lock file `/tmp/archive_fastq.lock` to prevent concurrent runs and automatically clears stale lock files when the recorded PID is gone.
- Automatically excludes run IDs protected by active keep-rules entries.

## CLI output
- Uses ANSI colors for headings, prompts, warnings, and final status in interactive terminals.
- Set `NO_COLOR=1` to disable colors.
- Archive plan table includes an `Owner` column (source run directory owner username) to help pre-check cleanup permissions.
- Archive plan and TUI include `Project ID` when it can be detected from local run metadata.
- `--investigate <RUN_ID>` prints detailed included/excluded size breakdown (patterns, top-level paths, and top files) and exits without archive/copy/verify.
