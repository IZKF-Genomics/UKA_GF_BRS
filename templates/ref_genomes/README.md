# ref_genomes (custom index builder)

This template downloads reference genomes, builds indices, and also builds
ERCC-augmented indices for each genome.

Quick start
1) Render into your references root (e.g., /data/genomes):
   bpm template render ref_genomes --out /data/genomes
2) Install tools with Pixi:
   cd /data/genomes
   pixi install
3) Edit genomes.yaml to add/remove genomes or tools.
4) Build:
   ./run.sh

Notes
- The script always builds both the base genome and a *_with_ERCC genome.
- Use FORCE=1 to re-download and rebuild indices.
