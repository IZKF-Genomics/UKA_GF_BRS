#!/usr/bin/env bash
# Simple genome list for ref_genomes.
# Format per entry:
#   id|fasta|gtf
# - gtf can be empty

WITH_ERCC=true
NF_PIPELINE="nf-core/references"
NF_REVISION="dev"
NXF_PROFILE="docker"
NF_EXTRA_ARGS=""
TOOLS="bowtie1,bowtie2,bwamem1,bwamem2,faidx,gffread,hisat2,kallisto,salmon,sizes,star"

GENOMES=(
  "GRCh38|https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/GRCh38.primary_assembly.genome.fa.gz|https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/gencode.v49.primary_assembly.annotation.gtf.gz"
  "GRCm39|https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_mouse/release_M38/GRCm39.primary_assembly.genome.fa.gz|https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_mouse/release_M38/gencode.vM38.primary_assembly.annotation.gtf.gz"
  "mRatBN7.2|https://ftp.ensembl.org/pub/release-115/fasta/rattus_norvegicus/dna/Rattus_norvegicus.GRCr8.dna.toplevel.fa.gz|https://ftp.ensembl.org/pub/release-115/gtf/rattus_norvegicus/Rattus_norvegicus.GRCr8.115.gtf.gz"
)
