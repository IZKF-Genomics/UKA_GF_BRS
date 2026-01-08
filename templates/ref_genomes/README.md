# ref_genomes

Download reference genomes, build indices, and create ERCC-augmented indices.

## Usage
1) Render into your references root (e.g., /data/genomes):
   `bpm template render ref_genomes --out /data/genomes`
2) Install tools with Pixi:
   `cd /data/genomes && pixi install`
3) Edit `genomes.yaml` to add/remove genomes or tools.
4) Build:
   `./run.sh`

## Parameters
- None. Configure inputs in `genomes.yaml`.

## Outputs
- Reference genome downloads and indices under the output directory.
- ERCC-augmented indices for each genome.

## Notes
- Use `FORCE=1` to re-download and rebuild indices.
