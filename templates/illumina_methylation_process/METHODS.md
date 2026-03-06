Illumina Infinium methylation array preprocessing was performed using a BPM-managed workflow that ingests raw IDAT files and project-level sample metadata. Data import, quality-control summarization, and preprocessing were executed in R/Bioconductor under a reproducible Pixi environment.

Probe- and sample-level quality metrics were computed prior to normalization. Signal processing and filtering were then applied according to configured project parameters, including array platform selection, genome build annotation context, and user-defined grouping variables for downstream stratified summaries.

Exploratory sample-structure analyses were generated from processed methylation matrices using dimensionality reduction and clustering outputs for quality assessment and cohort overview. Execution metadata, selected runtime parameters, and software/package versions were recorded in `results/run_info.yaml` to support reproducibility and publication reporting.
