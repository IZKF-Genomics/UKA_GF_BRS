# Archiving

This guide covers:
- `archive_rawdata`: copy + verify + manifest/log generation
- `archive_fastq`: copy + verify + manifest/log generation for `/data/fastq`
- `archive_cleanup`: source deletion based on archive manifests
- `clean_fastq`: direct pattern cleanup in `/data/fastq` (no archive step)

Related guide:
- [Keep Rules](./keep_rules.md)

## 1) Prepare manifest directory

```bash
sudo mkdir -p /data/shared/bpm_manifests
sudo chown root:bioinfo /data/shared/bpm_manifests
sudo chmod 2775 /data/shared/bpm_manifests
```

Optional write test:
```bash
touch /data/shared/bpm_manifests/.perm_test && rm /data/shared/bpm_manifests/.perm_test
```

## 2) Archive runs (copy + verify)

Raw data:
```bash
bpm workflow run archive_rawdata
```

FASTQ:
```bash
bpm workflow run archive_fastq
```

Cron-safe mode:
```bash
bpm workflow run archive_rawdata --non-interactive true
bpm workflow run archive_fastq --non-interactive true
```

Default keep behavior:
- All archive/clean workflows read `/data/shared/bpm_manifests/keep_rules.yaml`.
- Active keep entries are skipped automatically.

Default FASTQ excludes in `archive_fastq`:
- `*.fastq.gz`
- `*.fq.gz`
- `.pixi`
- `work`
- `.renv`
- `.Rproj.user`
- `.nextflow`
- `.nextflow.log*`

Typical outputs:
- `/data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json`
- `/data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.log`
- `/data/shared/bpm_manifests/archive_fastq_YYYYMMDD_HHMMSS.json`
- `/data/shared/bpm_manifests/archive_fastq_YYYYMMDD_HHMMSS.log`

## 3) Cleanup from manifest

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

Typical flow with sudo cleanup:
```bash
bpm workflow run archive_rawdata
sudo env PATH="$PATH" BPM_CACHE="$BPM_CACHE" bpm workflow run archive_cleanup --manifest-path /data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json
```

If sudo reports `No active BRS`, verify:
```bash
echo "$BPM_CACHE"
```

## 4) clean_fastq (no archive)

Dry-run:
```bash
bpm workflow run clean_fastq --dry-run true
```

Real run:
```bash
bpm workflow run clean_fastq --non-interactive true
```

## 5) Cron examples

Edit crontab:
```bash
crontab -e
```

Archive raw-data at 01:30:
```cron
30 1 * * * /opt/miniforge3/envs/bio/bin/bpm workflow run archive_rawdata --non-interactive true >> /data/shared/bpm_manifests/cron_archive_rawdata.log 2>&1
```

Archive FASTQ at 02:00:
```cron
0 2 * * * /opt/miniforge3/envs/bio/bin/bpm workflow run archive_fastq --non-interactive true >> /data/shared/bpm_manifests/cron_archive_fastq.log 2>&1
```

Cleanup at 03:00 (wrapper script):
```cron
0 3 * * * /usr/local/bin/archive_cleanup_latest.sh >> /data/shared/bpm_manifests/cron_archive_cleanup.log 2>&1
```

## 6) Recommended sudo wrapper for cleanup

`/usr/local/bin/archive_cleanup_latest.sh`:
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

```bash
sudo chmod 755 /usr/local/bin/archive_cleanup_latest.sh
```

Sudoers (minimal scope):
```sudoers
ckuo ALL=(root) NOPASSWD: /usr/local/bin/archive_cleanup_latest.sh
```

## 7) Refresh BRS cache after local changes

```bash
bpm resource update UKA_GF_BRS
```

## Notes
- `archive_cleanup` only processes records with `status=copied_verified`, `copy_status=ok`, `verify_status=ok`.
- For `archive_fastq` manifests, `archive_cleanup` uses `cleanup_mode=non_fastq_only` and preserves FASTQ files while removing archived non-FASTQ content.
- Archive plan tables include source run directory owner usernames (`Owner`) for permission visibility before cleanup.
- Cleanup status is written back into the same manifest (`cleanup_status`, `cleanup_error`, `cleanup_attempted_at`).
- Run cleanup dry-run after workflow updates before destructive cleanup.
