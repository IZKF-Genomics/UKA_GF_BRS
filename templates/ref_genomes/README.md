# ref_genomes (ad-hoc friendly)

This template manages reference genomes in a config-driven way and is optimized for ad-hoc usage (outside a BPM project directory).

Quick start
1) Render into your references root (e.g., /data/genomes):
   bpm template render ref_genomes --out /data/genomes
2) Edit /data/genomes/genomes.sh to set genomes, URLs, and indices.
3) Run the builder:
   (cd /data/genomes && ./run.sh)

What it does
- Downloads genome FASTA (and GTF if provided) per `genomes.sh`.
- Optionally appends ERCC92 (bundled) to produce an additional `<id>_with_ERCC.fa`.
- Optionally builds indices using `nf-core/references` for selected tools.
- Organizes outputs under the selected out root.

Notes
- ERCC files are bundled under `ERCC92/` for reproducibility.
- This template does not require a BPM project; `--out` renders files in-place.
- `genomes.sh` is plain Bash; no YAML parser required.
