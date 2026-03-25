# contamination_db

<!-- AGENT_METADATA_START -->
## Agent Metadata
```yaml
id: contamination_db
kind: template
description: Shared contamination database builder for Kraken2, Bracken, and FastQ Screen.
descriptor: templates/contamination_db/template_config.yaml
required_params: []
optional_params: []
cli_flags: {}
run_entry: run.sh
publish_keys: []
render_file_count: 5
```
<!-- AGENT_METADATA_END -->

Build shared Kraken2, Bracken, and FastQ Screen contamination databases from directly downloaded FASTA inputs.

## Usage
1. Render into the target database root:
   `bpm template render contamination_db --out /data/shared/contamination_db`
2. Install the Pixi environment:
   `cd /data/shared/contamination_db && pixi install`
3. Edit `contamination_db.yaml`:
   - choose `panel_name` and `db_version`
   - choose `kraken2_base` (`none` for a custom panel built only from the configured FASTAs; `standard` to additionally include the official Kraken2 standard content)
   - leave `kraken2_use_ftp: true` unless you know rsync works reliably on your network
   - set species FASTA URLs and taxids
   - choose Bracken read lengths
4. Run:
   `./run.sh`

## What It Builds
- `kraken2/<panel_name>/<db_version>/`
- `bracken/<panel_name>/<db_version>/`
- `fastq_screen/<panel_name>/<db_version>/`

The template also updates `current` symlinks under each tool root:
- `kraken2/<panel_name>/current`
- `bracken/<panel_name>/current`
- `fastq_screen/<panel_name>/current`

## Design Notes
- This template downloads FASTA files directly and does not depend on `ref_genomes`.
- `kraken2_base: standard` starts from the official Kraken2 standard database, then adds the configured vertebrates/PhiX panel.
- Extracted and normalized staging FASTA files are removed after a successful build by default, but downloaded source FASTAs are kept and reused on the next run.
- Provenance is preserved in:
  - `results/db_build_info.yaml`
  - `results/genome_manifest_resolved.csv`
  - `results/run.log`
- Downloaded FASTAs are recorded with their resolved final URL and SHA256 checksum, and existing downloads are reused on subsequent runs.
- Kraken2 FASTA headers are normalized with `kraken:taxid` tags before the library build.
- Bracken assets are built against the exact Kraken2 DB produced in the same run.
- FastQ Screen Bowtie2 indexes and `fastq_screen.conf` are generated from the same species panel.

## Config Highlights
- `cleanup_staging: true`
  Removes extracted and normalized staging FASTA files after a successful build while keeping the downloaded source FASTAs as a cache for the next run.
- `kraken2_base: none`
  Downloads taxonomy only, then builds the database from the configured FASTAs. This is the safest default for a curated contamination panel because it avoids transient upstream failures in Kraken2's `--standard` library download.
- `kraken2_base: standard`
  Starts from the official Kraken2 standard database, which already includes bacteria, archaea, viral references, human, and UniVec_Core. Use this only if you explicitly want that extra content and accept dependence on Kraken2's upstream library mirror state.
- `kraken2_use_ftp: true`
  Uses Kraken2's official `--use-ftp` fallback to avoid rsync-related build failures on restricted networks.
- `force: false`
  Prevents accidental overwrite of an existing `<panel>/<version>` build.
- `species`
  Each enabled entry must provide:
  - `label`
  - `taxid`
  - `fasta_url`
  - optional `filename`
  - optional `fastq_screen_label`

## Outputs
- `results/db_build_info.yaml`
- `results/genome_manifest_resolved.csv`
- `results/run.log`

## Notes
- Use a curated vertebrate panel rather than “all vertebrates” unless you truly need it.
- The starter species panel includes human, mouse, rat, zebrafish, pig, cow, chicken, dog, cat, and PhiX. Replace the placeholder FASTA URLs with your chosen sources before running.
- Keep `db_version` immutable once built; update the `current` symlink by building a new version.
- If you need to inspect staged FASTAs for debugging, set `cleanup_staging: false`.
