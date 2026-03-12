# Keep Rules

This guide explains how to protect selected runs from `archive_rawdata`, `archive_fastq`, `clean_fastq`, and `archive_cleanup`.

Default rules file:
- `/data/shared/bpm_manifests/keep_rules.yaml`

## What Keep Rules Do
- If a run ID is in keep rules and active, archive/cleanup workflows skip it.
- Active means:
  - `keep: true`
  - `keep_until` is empty, or `keep_until >= today`
- Each entry records `set_by` and `set_at`.

## 1) TUI Mode (Recommended)
Run:
```bash
bpm workflow run keep_rules
```

Flow:
1. choose browse root (`/data/fastq`, `/data/projects`, `/data/raw`, or custom)
2. in TUI, navigate and mark runs
3. save changes

TUI keys:
- `Up/Down` or `k/j`: move
- `Space`: toggle keep on selected row
- `u`: set `keep_until` (`YYYY-MM-DD`, empty clears)
- `s`: save
- `q`: quit

Columns shown:
- `Sel`
- `Run ID`
- `Keep Until`
- `Set By`

## 2) Direct CLI Mode

List:
```bash
bpm workflow run keep_rules --action list
```

Add:
```bash
# one run
bpm workflow run keep_rules --action add --run-id 241120_A01742_0328_AHYC2WDMXY

# multiple runs
bpm workflow run keep_rules --action add --run-ids 250704_A01742_0465_AH227MDSXF,250818_LH00452_0279_B22YHHTLT4_6

# with expiry
bpm workflow run keep_rules --action add --run-id 241120_A01742_0328_AHYC2WDMXY --keep-until 2026-12-31
```

Remove:
```bash
# one run
bpm workflow run keep_rules --action remove --run-id 241120_A01742_0328_AHYC2WDMXY

# multiple runs
bpm workflow run keep_rules --action remove --run-ids 250704_A01742_0465_AH227MDSXF,250818_LH00452_0279_B22YHHTLT4_6
```

Prompt browser (non-TUI):
```bash
bpm workflow run keep_rules --tui false --action add
bpm workflow run keep_rules --tui false --action remove
```

## 3) Prune Stale Entries
Preview:
```bash
bpm workflow run keep_rules --action prune
```

Apply:
```bash
bpm workflow run keep_rules --action prune --apply true --yes true
```

Custom roots:
```bash
bpm workflow run keep_rules --action prune --source-roots /data/raw,/data/fastq,/data/projects
```

## 4) Override Rules File Path
```bash
bpm workflow run keep_rules --action list --rules-path /data/shared/bpm_manifests/keep_rules.yaml
```

## 5) Example YAML
```yaml
schema_version: 1
updated_at: "2026-03-12T12:00:00+01:00"
runs:
  241120_A01742_0328_AHYC2WDMXY:
    keep: true
    set_by: ckuo
    set_at: "2026-03-12T12:00:00+01:00"
    keep_until: null
  250704_A01742_0465_AH227MDSXF:
    keep: true
    set_by: ckuo
    set_at: "2026-03-12T12:05:00+01:00"
    keep_until: "2026-12-31"
```

## Notes
- If TUI cannot run (no TTY), workflow falls back to list mode.
- `set_by` uses `SUDO_USER` first, then `USER`.
- Keep rules are evaluated by run ID, not by full path.
