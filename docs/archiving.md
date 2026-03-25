# Archiving

User-facing archive workflows:
- `archive_raw`
- `archive_fastq`
- `archive_projects`

Related guide:
- [Keep Rules](./keep_rules.md)

`archive_raw` is archive-only. It copies old raw runs, verifies the archive copy, and writes a manifest/log.

`archive_fastq` is archive plus source removal. It copies old FASTQ runs, verifies the archive copy, and then removes the original source run directory in the same workflow.

`archive_projects` follows the same archive-plus-removal model for `/data/projects`.

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

## 2) Keep Rules

Both archive workflows read `/data/shared/bpm_manifests/keep_rules.yaml`.

Keep rules are edited inside the integrated archive TUI:
- `k`: keep/unkeep the selected run
- `u`: set `keep_until`
- `s`: save and continue
- `q`: quit

Active keep entries are skipped automatically for archive or source removal.

## 3) Run The Workflows

Raw data:
```bash
bpm workflow run archive_raw
```

FASTQ:
```bash
bpm workflow run archive_fastq
```

Projects:
```bash
bpm workflow run archive_projects
```

Cron-safe mode:
```bash
bpm workflow run archive_raw --non-interactive true
bpm workflow run archive_fastq --non-interactive true
bpm workflow run archive_projects --non-interactive true
```

## 4) Workflow Behavior

`archive_raw`
- scans `/data/raw`
- shows one retention-filtered list in the TUI
- lets you keep/unkeep runs in the same list
- copies and verifies selected runs
- writes a manifest and log
- does not delete source raw data

`archive_fastq`
- scans `/data/fastq`
- shows one retention-filtered list in the TUI
- applies keep/unkeep decisions in the same list
- copies and verifies selected runs
- removes the source run directory after verification when cleanup is enabled
- also supports cleanup-only reruns for already-archived FASTQ-only or empty source folders when the target archive already exists

`archive_projects`
- scans `/data/projects`
- shows one retention-filtered list in the TUI
- applies keep/unkeep decisions in the same list
- copies and verifies selected project directories
- removes the source directory after verification when cleanup is enabled
- uses project-specific excludes such as `work`, `.pixi`, `.renv`, `.nextflow`, `results`, and `*.fastq.gz`

Default FASTQ excludes in `archive_fastq`:
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

These exclude patterns affect archive copy and verify only. They do not protect source files from removal when `archive_fastq` cleanup is enabled.

## 5) Common Examples

Skip selected old runs:
```bash
bpm workflow run archive_raw --skip-runs 251030_A01742_0532_BH5MKFDRX7
bpm workflow run archive_fastq --skip-runs 251030_A01742_0532_BH5MKFDRX7,260105_NB501289_0982_AHT27GBGYX
```

Plan only:
```bash
bpm workflow run archive_raw --dry-run true
bpm workflow run archive_fastq --dry-run true
```

Archive-only FASTQ mode:
```bash
bpm workflow run archive_fastq --cleanup false
```

Investigate one FASTQ run before archiving:
```bash
bpm workflow run archive_fastq --investigate 250818_LH00452_0279_B22YHHTLT4_6
```

Investigate one project directory before archiving:
```bash
bpm workflow run archive_projects --investigate 250818_LH00452_0279_B22YHHTLT4_6
```

## 6) Output Files

Typical outputs:
- `/data/shared/bpm_manifests/archive_raw_YYYYMMDD_HHMMSS.json` or `/data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.json`
- `/data/shared/bpm_manifests/archive_raw_YYYYMMDD_HHMMSS.log` or `/data/shared/bpm_manifests/archive_rawdata_YYYYMMDD_HHMMSS.log`
- `/data/shared/bpm_manifests/archive_fastq_YYYYMMDD_HHMMSS.json`
- `/data/shared/bpm_manifests/archive_fastq_YYYYMMDD_HHMMSS.log`
- `/data/shared/bpm_manifests/archive_projects_YYYYMMDD_HHMMSS.json`
- `/data/shared/bpm_manifests/archive_projects_YYYYMMDD_HHMMSS.log`

`archive_fastq` writes archive and removal status into the same manifest:
- `copy_status`
- `verify_status`
- `cleanup_status`
- `cleanup_error`
- `cleanup_attempted_at`

## 7) Cron Examples

Edit crontab:
```bash
crontab -e
```

Archive raw data at 01:30:
```cron
30 1 * * * /opt/miniforge3/envs/bio/bin/bpm workflow run archive_raw --non-interactive true >> /data/shared/bpm_manifests/cron_archive_raw.log 2>&1
```

Archive and remove FASTQ at 02:00:
```cron
0 2 * * * /opt/miniforge3/envs/bio/bin/bpm workflow run archive_fastq --non-interactive true >> /data/shared/bpm_manifests/cron_archive_fastq.log 2>&1
```

Archive and remove projects at 02:30:
```cron
30 2 * * * /opt/miniforge3/envs/bio/bin/bpm workflow run archive_projects --non-interactive true >> /data/shared/bpm_manifests/cron_archive_projects.log 2>&1
```

## 8) Refresh BRS Cache After Local Changes

```bash
bpm resource update UKA_GF_BRS
```

## Notes
- `archive_raw` remains archive-only.
- `archive_fastq` removes the source run directory only after archive verification succeeds, unless `--cleanup false` is used.
- `archive_projects` follows the same cleanup rule for `/data/projects`.
- `archive_fastq` verify is one-way archive verification; target-only files do not fail verification.
- Archive tables include source owner usernames (`Owner`) and FASTQ project IDs (`Project ID`) where available.
