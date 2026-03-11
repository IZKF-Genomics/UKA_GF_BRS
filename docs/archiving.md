# Archiving

This guide covers the two-step archive workflow pair:
- `archive_rawdata`: copy + verify + manifest/log generation
- `archive_cleanup`: source deletion based on manifest entries

## 1) Prepare manifest directory
If you do not want to write under `/data/raw/.archive_manifests`, use a shared writable path.

```bash
sudo mkdir -p /data/shared/archive_manifests
sudo chown root:bioinfo /data/shared/archive_manifests
sudo chmod 2775 /data/shared/archive_manifests
```

Optional write test as your normal user:
```bash
touch /data/shared/archive_manifests/.perm_test && rm /data/shared/archive_manifests/.perm_test
```

## 2) Run archive (copy + verify)
Interactive:
```bash
bpm workflow run archive_rawdata --manifest-dir /data/shared/archive_manifests
```

Non-interactive (cron-safe shortcut):
```bash
bpm workflow run archive_rawdata --non-interactive true --manifest-dir /data/shared/archive_manifests
```

Typical output files:
- `/data/shared/archive_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json`
- `/data/shared/archive_manifests/archive_rawdata_YYYYMMDD_HHMMSS.log`

## 3) Run cleanup from manifest
Dry-run first:
```bash
bpm workflow run archive_cleanup \
  --manifest-path /data/shared/archive_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json \
  --dry-run true
```

Real cleanup:
```bash
bpm workflow run archive_cleanup \
  --non-interactive true \
  --manifest-path /data/shared/archive_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json
```

## 4) Cron examples
Use full paths and dedicated log files.

Edit crontab:
```bash
crontab -e
```

Archive every day at 01:30:
```cron
30 1 * * * /opt/miniforge3/envs/bio/bin/bpm workflow run archive_rawdata --non-interactive true --manifest-dir /data/shared/archive_manifests >> /data/shared/archive_manifests/cron_archive_rawdata.log 2>&1
```

Cleanup every day at 03:00 using latest manifest (wrapper script pattern below):
```cron
0 3 * * * /usr/local/bin/archive_cleanup_latest.sh >> /data/shared/archive_manifests/cron_archive_cleanup.log 2>&1
```

## 5) Sudo cleanup pattern (recommended)
Keep archive unprivileged. If deletion needs elevated rights, run only cleanup via sudo.

Create `/usr/local/bin/archive_cleanup_latest.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
MANIFEST_DIR="/data/shared/archive_manifests"
LATEST_MANIFEST="$(ls -1 ${MANIFEST_DIR}/archive_rawdata_*.json | tail -n1)"
/opt/miniforge3/envs/bio/bin/bpm workflow run archive_cleanup \
  --non-interactive true \
  --manifest-path "${LATEST_MANIFEST}" \
  --allowed-source-roots /data/raw
```

Make executable:
```bash
sudo chmod 755 /usr/local/bin/archive_cleanup_latest.sh
```

Allow only this command in sudoers (`visudo`):
```sudoers
ckuo ALL=(root) NOPASSWD: /usr/local/bin/archive_cleanup_latest.sh
```

Then cron entry can call:
```cron
0 3 * * * sudo /usr/local/bin/archive_cleanup_latest.sh >> /data/shared/archive_manifests/cron_archive_cleanup.log 2>&1
```

## 6) Update BRS cache before running new workflow code
If BPM runs from `~/.bpm_cache/brs/...`, update the resource after changes:
```bash
bpm resource update UKA_GF_BRS
```

## Notes
- `archive_cleanup` only deletes records that are `copied_verified` with `copy_status=ok` and `verify_status=ok`.
- Cleanup writes status back into the same manifest (`cleanup_status`, `cleanup_error`, `cleanup_attempted_at`).
- Always run cleanup dry-run first after workflow updates.
