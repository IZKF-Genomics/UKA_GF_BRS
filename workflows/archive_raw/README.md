# archive_raw

Archive old raw sequencing run directories from `/data/raw` into archive storage.

This is the user-facing raw-data archive workflow.

Behavior:
- shows one retention-filtered archive list in the TUI
- lets you keep/unkeep runs in the same list
- copies and verifies selected runs
- writes a manifest and log
- does not delete source raw data

Run with:
```bash
bpm workflow run archive_raw
```
