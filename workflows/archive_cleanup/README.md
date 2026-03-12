# archive_cleanup


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: archive_cleanup
kind: workflow
description: Cleanup source data based on archive_rawdata/archive_fastq manifest entries.
descriptor: workflows/archive_cleanup/workflow_config.yaml
required_params: []
optional_params:
- manifest_path
- manifest_dir
- keep_rules_path
- allowed_source_roots
- instrument_folders
- non_interactive
- interactive
- yes
- dry_run
cli_flags:
  manifest_path: --manifest-path
  keep_rules_path: --keep-rules-path
  instrument_folders: --instrument-folders
  non_interactive: --non-interactive
  yes: --yes
  dry_run: --dry-run
run_entry: run.py
tools_required:
- python
tools_optional: []
```
<!-- AGENT_METADATA_END -->

Delete source data that was successfully copied and verified by `archive_rawdata` or `archive_fastq`.

## Run
```bash
bpm workflow run archive_cleanup --manifest-path /data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json
```

## Common examples
```bash
# Use latest manifest from default manifest dir
bpm workflow run archive_cleanup

# Cron-safe non-interactive cleanup
bpm workflow run archive_cleanup --non-interactive true --manifest-path /data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json

# Dry-run cleanup validation
bpm workflow run archive_cleanup --manifest-path /data/shared/bpm_manifests/archive_fastq_YYYYMMDD_HHMMSS.json --dry-run true

# Typical raw-data cleanup flow (as executed)
bpm workflow run archive_rawdata
sudo env PATH="$PATH" BPM_CACHE="$BPM_CACHE" bpm workflow run archive_cleanup --manifest-path /data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json
```

## Safety model
- Only deletes entries with `status=copied_verified`, `copy_status=ok`, `verify_status=ok`.
- Respects `/data/shared/bpm_manifests/keep_rules.yaml` by default and marks protected records as `skipped_keep_rules`.
- If a manifest record contains `cleanup_mode=non_fastq_only`, cleanup removes archived non-FASTQ content and preserves `cleanup_preserve_patterns` (for example `*.fastq.gz`, `*.fq.gz`).
- Backward compatibility: if a record contains `cleanup_patterns`, only matching files are removed.
- Enforces deletion allowlist by source roots and instrument folders.
- Refuses non-absolute paths, shallow paths, instrument roots, and source root.
- Records cleanup outcome back into the same manifest (`cleanup_status`, `cleanup_error`, `cleanup_attempted_at`).
- Uses lock file `/tmp/archive_cleanup.lock` to prevent concurrent cleanup runs.

## Sudo usage
Run this workflow under sudo if source deletion requires elevated permissions.
Keep `archive_rawdata` unprivileged.

If sudo shows `No active BRS`, make sure `BPM_CACHE` is set:
```bash
echo "$BPM_CACHE"
```
