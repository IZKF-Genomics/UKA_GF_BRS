# archive_cleanup


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: archive_cleanup
kind: workflow
description: Cleanup source run directories based on archive_rawdata manifest entries.
descriptor: workflows/archive_cleanup/workflow_config.yaml
required_params: []
optional_params:
- manifest_path
- manifest_dir
- allowed_source_roots
- instrument_folders
- non_interactive
- interactive
- yes
- dry_run
cli_flags:
  manifest_path: --manifest-path
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

Delete source run directories that were successfully copied and verified by `archive_rawdata`.

## Run
```bash
bpm workflow run archive_cleanup --manifest-path /data/raw/.archive_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json
```

## Common examples
```bash
# Use latest manifest from default manifest dir
bpm workflow run archive_cleanup

# Cron-safe non-interactive cleanup
bpm workflow run archive_cleanup --non-interactive true --manifest-path /data/raw/.archive_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json

# Dry-run cleanup validation
bpm workflow run archive_cleanup --manifest-path /data/raw/.archive_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json --dry-run true
```

## Safety model
- Only deletes entries with `status=copied_verified`, `copy_status=ok`, `verify_status=ok`.
- Enforces deletion allowlist by source roots and instrument folders.
- Refuses non-absolute paths, shallow paths, instrument roots, and source root.
- Records cleanup outcome back into the same manifest (`cleanup_status`, `cleanup_error`, `cleanup_attempted_at`).
- Uses lock file `/tmp/archive_cleanup.lock` to prevent concurrent cleanup runs.

## Sudo usage
Run this workflow under sudo if source deletion requires elevated permissions.
Keep `archive_rawdata` unprivileged.
