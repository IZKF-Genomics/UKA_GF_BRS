suppressPackageStartupMessages({
  library(RcppTOML)
  library(readr)
  library(dplyr)
  library(tibble)
  library(stringr)
  library(ggplot2)
})

log_info <- function(...) cat(sprintf("[INFO] %s\n", paste(..., collapse = " ")))
log_warn <- function(...) warning(paste(..., collapse = " "), call. = FALSE)
log_error <- function(...) stop(paste(..., collapse = " "), call. = FALSE)

ensure_dirs <- function(root = ".") {
  dirs <- c("results/rds", "results/tables", "results/figures", "results/logs", "reports")
  for (d in dirs) dir.create(file.path(root, d), recursive = TRUE, showWarnings = FALSE)
  invisible(TRUE)
}

load_config <- function(path = "config/project.toml") {
  if (!file.exists(path)) log_error("Config not found:", path)
  cfg <- RcppTOML::parseTOML(path)
  cfg
}

load_samples <- function(path = "config/samples.csv") {
  if (!file.exists(path)) log_error("Sample sheet not found:", path)
  readr::read_csv(path, show_col_types = FALSE)
}

save_rds <- function(object, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  saveRDS(object, path)
  invisible(path)
}

read_rds <- function(path) {
  if (!file.exists(path)) log_error("Required artifact missing:", path)
  readRDS(path)
}

write_table <- function(df, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  readr::write_csv(as_tibble(df), path)
  invisible(path)
}

required_sample_cols <- function() c("sample_id", "group", "SentrixBarcode", "SentrixPosition")

validate_samples_schema <- function(samples) {
  missing <- setdiff(required_sample_cols(), names(samples))
  if (length(missing) > 0) log_error("samples.csv missing required columns:", paste(missing, collapse = ", "))
  dup_ids <- samples$sample_id[duplicated(samples$sample_id)]
  if (length(dup_ids) > 0) log_error("Duplicate sample_id values:", paste(unique(dup_ids), collapse = ", "))
  key <- paste(samples$SentrixBarcode, samples$SentrixPosition, sep = "::")
  dup_pairs <- key[duplicated(key)]
  if (length(dup_pairs) > 0) log_error("Duplicate SentrixBarcode/SentrixPosition pairs:", paste(unique(dup_pairs), collapse = ", "))
  invisible(TRUE)
}

validate_config_schema <- function(cfg) {
  for (section in c("project", "idat", "groups", "qc", "normalization", "filter", "dmp", "enrichment", "drilldown")) {
    if (is.null(cfg[[section]])) log_error("Missing config section [", section, "]")
  }
  valid_norm <- c("noob", "quantile", "swan", "funnorm")
  method <- cfg$normalization$method
  if (!(method %in% valid_norm)) log_error("Unsupported normalization.method:", method)
  valid_arrays <- c("450K", "EPIC", "EPIC_V2")
  if (!(cfg$project$array_type %in% valid_arrays)) log_error("Unsupported project.array_type:", cfg$project$array_type)
  valid_layouts <- c("flat", "per_barcode_subdir")
  if (!(cfg$idat$layout %in% valid_layouts)) log_error("Unsupported idat.layout:", cfg$idat$layout)
  invisible(TRUE)
}

resolve_idat_basenames <- function(samples, cfg) {
  base_dir <- cfg$idat$base_dir
  layout <- cfg$idat$layout
  samples <- as_tibble(samples)
  if (layout == "flat") {
    samples <- samples %>% mutate(Basename = file.path(base_dir, paste0(SentrixBarcode, "_", SentrixPosition)))
  } else {
    samples <- samples %>% mutate(Basename = file.path(base_dir, SentrixBarcode, paste0(SentrixBarcode, "_", SentrixPosition)))
  }
  samples
}

idat_pair_paths <- function(basename) {
  c(red = paste0(basename, "_Red.idat"), grn = paste0(basename, "_Grn.idat"))
}

check_idat_pairs <- function(samples_resolved) {
  status <- lapply(seq_len(nrow(samples_resolved)), function(i) {
    b <- samples_resolved$Basename[[i]]
    p <- idat_pair_paths(b)
    tibble(
      sample_id = samples_resolved$sample_id[[i]],
      Basename = b,
      red_path = p[["red"]],
      grn_path = p[["grn"]],
      red_exists = file.exists(p[["red"]]),
      grn_exists = file.exists(p[["grn"]])
    )
  })
  bind_rows(status)
}

validate_groups <- function(cfg, samples) {
  group_col <- cfg$groups$primary_group_col
  if (!(group_col %in% names(samples))) log_error("groups.primary_group_col not found in samples.csv:", group_col)
  case_label <- cfg$groups$case
  control_label <- cfg$groups$control
  counts <- table(samples[[group_col]])
  if (!(case_label %in% names(counts))) log_error("Case label not found:", case_label)
  if (!(control_label %in% names(counts))) log_error("Control label not found:", control_label)
  if (as.integer(counts[[case_label]]) < 2) log_error("Case group must contain at least 2 samples")
  if (as.integer(counts[[control_label]]) < 2) log_error("Control group must contain at least 2 samples")
  invisible(counts)
}

warn_enrichment_support <- function(cfg) {
  if (identical(cfg$project$array_type, "EPIC_V2") && identical(cfg$enrichment$method, "missMethyl_gometh")) {
    log_warn("EPIC_V2 with missMethyl::gometh may require newer package support; enrichment step will warn/skip if unsupported.")
  }
}

validate_project <- function(cfg, samples, fail_on_missing_idats = TRUE) {
  validate_config_schema(cfg)
  validate_samples_schema(samples)
  validate_groups(cfg, samples)
  resolved <- resolve_idat_basenames(samples, cfg)
  status <- check_idat_pairs(resolved)
  warn_enrichment_support(cfg)
  if (fail_on_missing_idats && any(!status$red_exists | !status$grn_exists)) {
    bad <- status %>% filter(!red_exists | !grn_exists)
    write_table(bad, "results/tables/missing_idats.csv")
    log_error("Missing IDAT pairs detected. See results/tables/missing_idats.csv")
  }
  invisible(list(samples_resolved = resolved, idat_status = status))
}

save_plot <- function(plot_obj, path, width = 8, height = 5) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  ggplot2::ggsave(filename = path, plot = plot_obj, width = width, height = height)
  invisible(path)
}

source_optional <- function(path) {
  if (file.exists(path)) source(path, local = TRUE)
}

load_analysis_inputs <- function() {
  paths <- c(
    adjusted = "results/rds/adjustedset.rds",
    filtered = "results/rds/filteredset.rds",
    norm = "results/rds/normset.rds",
    rg = "results/rds/rgset.rds"
  )
  for (nm in names(paths)) if (file.exists(paths[[nm]])) return(readRDS(paths[[nm]]))
  log_error("No upstream methylation object found (expected adjustedset/filter/norm/rgset)")
}

get_beta_matrix <- function(obj) {
  if (!requireNamespace("minfi", quietly = TRUE)) log_error("Package 'minfi' is required")
  minfi::getBeta(obj)
}

get_m_matrix <- function(obj) {
  if (!requireNamespace("minfi", quietly = TRUE)) log_error("Package 'minfi' is required")
  minfi::getM(obj)
}

get_detp <- function(rgset) {
  if (!requireNamespace("minfi", quietly = TRUE)) log_error("Package 'minfi' is required")
  minfi::detectionP(rgset)
}

get_pdata <- function(obj) {
  as.data.frame(SummarizedExperiment::colData(obj))
}

get_annotation_df <- function(obj) {
  ann <- tryCatch(minfi::getAnnotation(obj), error = function(e) NULL)
  if (is.null(ann)) return(tibble(Name = rownames(obj)))
  ann_df <- as.data.frame(ann)
  ann_df$Name <- rownames(ann_df)
  as_tibble(ann_df)
}

normalize_array_type_for_gometh <- function(array_type) {
  dplyr::case_when(
    array_type == "450K" ~ "450K",
    array_type == "EPIC" ~ "EPIC",
    TRUE ~ NA_character_
  )
}

safe_top_var_rows <- function(mat, n = 5000) {
  v <- apply(mat, 1, stats::var, na.rm = TRUE)
  ord <- order(v, decreasing = TRUE)
  mat[head(ord, min(n, nrow(mat))), , drop = FALSE]
}
