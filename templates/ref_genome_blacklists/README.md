# ref_genome_blacklists

Download Boyle-Lab blacklist v2 BED files.

Source:
- https://github.com/Boyle-Lab/Blacklist/tree/master/lists

## Usage
1) Render into your references root (e.g., /data/ref_genome_blacklists):
   `bpm template render ref_genome_blacklists --out /data/ref_genome_blacklists`
2) Download files:
   `./run.sh`

## Parameters
- None.

## Outputs
- v2 blacklist BED files under the output directory.
