# Keep Rules

This guide explains how to protect selected runs from `archive_raw` and `archive_fastq`.

Default rules file:
- `/data/shared/bpm_manifests/keep_rules.yaml`

## What Keep Rules Do
- If a run ID is in keep rules and active, archive workflows skip it.
- Active means:
  - `keep: true`
  - `keep_until` is empty, or `keep_until >= today`
- Each entry records `set_by` and `set_at`.

## 1) Integrated TUI Mode (Recommended)

Keep rules are normally edited inside:
```bash
bpm workflow run archive_raw
bpm workflow run archive_fastq
```

Flow:
1. open the archive workflow
2. review the single archive-candidate list
3. toggle keep status or set `keep_until`
4. save and continue

TUI keys:
- `Up/Down` or `j`: move
- `k`: toggle keep on selected row
- `u`: set `keep_until` (`YYYY-MM-DD`, empty clears)
- `s`: save and continue
- `q`: quit

Columns shown:
- `Keep`
- `Archive`
- `Run ID`
- `Owner`
- `Keep Until`
- `Set By`

`archive_fastq` may also show cleanup-only rows when the run is already archived on the target and only source removal remains.

## 2) Rules File

The rules are stored in:
- `/data/shared/bpm_manifests/keep_rules.yaml`

The archive workflows read this file automatically and update it when you save from the TUI.

## 3) Example YAML
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
- `set_by` uses `SUDO_USER` first, then `USER`.
- Keep rules are evaluated by run ID, not by full path.
