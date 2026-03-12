# Archiving

This guide covers the two-step archive workflow pair:
- `archive_rawdata`: copy + verify + manifest/log generation
- `archive_fastq`: copy + verify + manifest/log generation for `/data/fastq`
- `archive_cleanup`: source deletion based on manifest entries

Additional direct-clean workflow:
- `clean_fastq`: remove pattern-matched content in `/data/fastq` without archiving.

## 1) Prepare manifest directory
Use a shared writable manifest path for both workflows.

```bash
sudo mkdir -p /data/shared/bpm_manifests
sudo chown root:bioinfo /data/shared/bpm_manifests
sudo chmod 2775 /data/shared/bpm_manifests
```

Optional write test as your normal user:
```bash
touch /data/shared/bpm_manifests/.perm_test && rm /data/shared/bpm_manifests/.perm_test
```

## 2) Run archive (copy + verify)
Interactive raw-data archive:
```bash
bpm workflow run archive_rawdata
```

Interactive FASTQ archive:
```bash
bpm workflow run archive_fastq
```

Non-interactive raw-data archive (cron-safe shortcut):
```bash
bpm workflow run archive_rawdata --non-interactive true
```

Non-interactive FASTQ archive (always excludes `*.fastq.gz` and `*.fq.gz`):
```bash
bpm workflow run archive_fastq --non-interactive true
```
Default FASTQ archive excludes also include `.pixi`, `work`, `.renv`, `.Rproj.user`, `.nextflow`, `.nextflow.log*`.

Typical output files:
- `/data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json`
- `/data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.log`
- `/data/shared/bpm_manifests/archive_fastq_YYYYMMDD_HHMMSS.json`
- `/data/shared/bpm_manifests/archive_fastq_YYYYMMDD_HHMMSS.log`

## 3) Run cleanup from manifest
Dry-run first:
```bash
bpm workflow run archive_cleanup \
  --manifest-path /data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json \
  --dry-run true
```

Real cleanup:
```bash
bpm workflow run archive_cleanup \
  --non-interactive true \
  --manifest-path /data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json
```

Real-world raw-data sequence (interactive archive + sudo cleanup):
```bash
bpm workflow run archive_rawdata
sudo env PATH="$PATH" BPM_CACHE="$BPM_CACHE" bpm workflow run archive_cleanup --manifest-path /data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json
```

If sudo reports `No active BRS`, ensure `BPM_CACHE` is set in your shell first:
```bash
echo "$BPM_CACHE"
```

## 4) Cron examples
Use full paths and dedicated log files.

Edit crontab:
```bash
crontab -e
```

Archive raw-data every day at 01:30:
```cron
30 1 * * * /opt/miniforge3/envs/bio/bin/bpm workflow run archive_rawdata --non-interactive true >> /data/shared/bpm_manifests/cron_archive_rawdata.log 2>&1
```

Archive FASTQ every day at 02:00:
```cron
0 2 * * * /opt/miniforge3/envs/bio/bin/bpm workflow run archive_fastq --non-interactive true >> /data/shared/bpm_manifests/cron_archive_fastq.log 2>&1
```

Cleanup every day at 03:00 using latest manifest (wrapper script pattern below):
```cron
0 3 * * * /usr/local/bin/archive_cleanup_latest.sh >> /data/shared/bpm_manifests/cron_archive_cleanup.log 2>&1
```

## 5) Sudo cleanup pattern (recommended)
Keep archive unprivileged. If deletion needs elevated rights, run only cleanup via sudo.

Create `/usr/local/bin/archive_cleanup_latest.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
MANIFEST_DIR="/data/shared/bpm_manifests"
LATEST_MANIFEST="$(ls -1 ${MANIFEST_DIR}/archive_rawdata_*.json ${MANIFEST_DIR}/archive_fastq_*.json 2>/dev/null | tail -n1)"
/opt/miniforge3/envs/bio/bin/bpm workflow run archive_cleanup \
  --non-interactive true \
  --manifest-path "${LATEST_MANIFEST}" \
  --allowed-source-roots /data/raw,/data/fastq
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
0 3 * * * sudo /usr/local/bin/archive_cleanup_latest.sh >> /data/shared/bpm_manifests/cron_archive_cleanup.log 2>&1
```

## 6) Update BRS cache before running new workflow code
If BPM runs from `~/.bpm_cache/brs/...`, update the resource after changes:
```bash
bpm resource update UKA_GF_BRS
```

## 7) Direct clean without archiving (`clean_fastq`)
Dry-run:
```bash
bpm workflow run clean_fastq --dry-run true
```

Real run:
```bash
bpm workflow run clean_fastq --non-interactive true
```

Default clean patterns:
- `*.fastq.gz`
- `*.fq.gz`
- `.pixi`
- `work`
- `.renv`
- `.Rproj.user`
- `.nextflow`
- `.nextflow.log*`

## Notes
- `archive_cleanup` only deletes records that are `copied_verified` with `copy_status=ok` and `verify_status=ok`.
- `archive_fastq` excludes `*.fastq.gz` and `*.fq.gz` from archive copy/verify.
- For `archive_fastq` manifests, `archive_cleanup` uses `cleanup_mode=non_fastq_only` and preserves FASTQ files while removing archived non-FASTQ content.
- Cleanup writes status back into the same manifest (`cleanup_status`, `cleanup_error`, `cleanup_attempted_at`).
- On first permission-denied failure, `archive_cleanup` prints an inline sudo re-run hint with the exact `--manifest-path`.
- Always run cleanup dry-run first after workflow updates.

## Manifest retention policy
Recommended housekeeping:
- Keep manifest JSON files for 12-24 months (audit/recovery trail).
- Gzip workflow and cron logs older than 30 days.
- Delete compressed logs older than 6-12 months.

Example housekeeping commands:
```bash
# Compress old logs
find /data/shared/bpm_manifests -maxdepth 1 -type f -name "*.log" -mtime +30 -exec gzip -f {} \;

# Remove very old compressed logs
find /data/shared/bpm_manifests -maxdepth 1 -type f -name "*.log.gz" -mtime +365 -delete

# Remove very old manifests (keep 24 months)
find /data/shared/bpm_manifests -maxdepth 1 -type f -name "*.json" -mtime +730 -delete
```
