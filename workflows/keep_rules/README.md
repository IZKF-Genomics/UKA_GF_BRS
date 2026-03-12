# keep_rules


<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: keep_rules
kind: workflow
description: Manage keep rules (list/add/remove/prune) in /data/shared/bpm_manifests/keep_rules.yaml.
descriptor: workflows/keep_rules/workflow_config.yaml
required_params: []
optional_params:
- action
- tui
- browse_root
- run_id
- run_ids
- keep_until
- rules_path
- source_roots
- apply
- non_interactive
- interactive
- yes
cli_flags:
  action: --action
  tui: --tui
  browse_root: --browse-root
  run_id: --run-id
  run_ids: --run-ids
  keep_until: --keep-until
  rules_path: --rules-path
  source_roots: --source-roots
  apply: --apply
  non_interactive: --non-interactive
  yes: --yes
run_entry: run.py
tools_required:
- python
tools_optional: []
```
<!-- AGENT_METADATA_END -->

Manage keep rules in `/data/shared/bpm_manifests/keep_rules.yaml`.

## Actions
- `list`: show current keep entries.
- `add`: add or update keep entries for one or more run IDs.
- `remove`: delete keep entries for one or more run IDs.
- `prune`: remove stale keep entries that are no longer found under source roots.

## Default UX
- Running `bpm workflow run keep_rules` starts a TUI browser by default (`--tui true`).
- Before TUI starts, it asks which browse root to scan (`/data/fastq`, `/data/projects`, `/data/raw`, or custom path).
- TUI keys:
  - `Up/Down` (or `k/j`): move cursor
  - `Space`: toggle keep/unkeep
- `u`: set `keep_until` for current run (`YYYY-MM-DD`, empty clears)
  - `s`: save all changes
- `q`: quit (asks before discarding unsaved changes)
- If TUI is unavailable (non-TTY), workflow falls back to `list`.
- TUI rows show existing `set_by` and `keep_until` values from `keep_rules.yaml`.

## Run
```bash
bpm workflow run keep_rules
```

## Common examples
```bash
# List rules
bpm workflow run keep_rules --action list

# TUI on raw data path
bpm workflow run keep_rules --browse-root /data/raw

# Add one run
bpm workflow run keep_rules --action add --run-id 241120_A01742_0328_AHYC2WDMXY

# Add multiple runs (optional keep_until)
bpm workflow run keep_rules --action add --run-ids 250704_A01742_0465_AH227MDSXF,250818_LH00452_0279_B22YHHTLT4_6 --keep-until 2027-12-31

# Remove one run
bpm workflow run keep_rules --action remove --run-id 241120_A01742_0328_AHYC2WDMXY

# Add/remove using prompt browser (non-TUI path)
bpm workflow run keep_rules --tui false --action add
bpm workflow run keep_rules --tui false --action remove

# Preview prune (dry-run behavior by default)
bpm workflow run keep_rules --action prune

# Apply prune
bpm workflow run keep_rules --action prune --apply true --yes true
```

## Rule format
Each run entry records who set the rule and when:
```yaml
runs:
  241120_A01742_0328_AHYC2WDMXY:
    keep: true
    set_by: ckuo
    set_at: "2026-03-12T11:30:00+01:00"
    keep_until: null
```

## Notes
- `set_by` uses `SUDO_USER` first, then `USER`.
- `prune` scans source roots (default: `/data/raw,/data/fastq`) and removes run IDs not found there.
- `prune` is safe by default (`--apply false` unless explicitly enabled).
- You can disable TUI and use prompt/CLI actions directly with `--tui false`.
