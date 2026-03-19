#!/usr/bin/env Rscript

required_pkgs <- c(
  "missMethyl",
  "GO.db",
  "org.Hs.eg.db",
  "IlluminaHumanMethylation450kmanifest",
  "IlluminaHumanMethylationEPICmanifest",
  "IlluminaHumanMethylationEPICv2manifest",
  "IlluminaHumanMethylation450kanno.ilmn12.hg19",
  "IlluminaHumanMethylationEPICanno.ilm10b4.hg19",
  "IlluminaHumanMethylationEPICv2anno.20a1.hg38"
)

missing_pkgs <- required_pkgs[!vapply(required_pkgs, requireNamespace, logical(1), quietly = TRUE)]
if (!length(missing_pkgs)) {
  message("[INFO] Bioconductor annotation packages already available")
  quit(status = 0)
}

lib <- .libPaths()[1]
dir.create(lib, recursive = TRUE, showWarnings = FALSE)

if (!requireNamespace("BiocManager", quietly = TRUE)) {
  install.packages("BiocManager", repos = "https://cloud.r-project.org", lib = lib)
}

message("[INFO] Installing missing Bioconductor packages: ", paste(missing_pkgs, collapse = ", "))
BiocManager::install(missing_pkgs, ask = FALSE, update = FALSE, lib = lib)

still_missing <- required_pkgs[!vapply(required_pkgs, requireNamespace, logical(1), quietly = TRUE)]
if (length(still_missing)) {
  stop("Packages still unavailable after repair: ", paste(still_missing, collapse = ", "), call. = FALSE)
}

message("[INFO] Bioconductor annotation repair complete")
