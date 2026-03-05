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
  dirs <- c("results/rds", "results/tables", "results/figures", "results/logs")
  for (d in dirs) dir.create(file.path(root, d), recursive = TRUE, showWarnings = FALSE)
  invisible(TRUE)
}

load_config <- function(path = "project.toml") {
  if (!file.exists(path)) log_error("Config not found:", path)
  RcppTOML::parseTOML(path)
}

load_samples <- function(path = "samples.csv") {
  if (!file.exists(path)) log_error("Sample sheet not found:", path)
  readr::read_csv(path, show_col_types = FALSE)
}

ensure_array_support_packages <- function(array_type) {
  pkg_map <- list(
    "450K" = c("IlluminaHumanMethylation450kmanifest", "IlluminaHumanMethylation450kanno.ilmn12.hg19"),
    "EPIC" = c("IlluminaHumanMethylationEPICmanifest", "IlluminaHumanMethylationEPICanno.ilm10b4.hg19"),
    "EPIC_V2" = c("IlluminaHumanMethylationEPICv2manifest", "IlluminaHumanMethylationEPICv2anno.20a1.hg38")
  )
  # Mixed historical datasets can trigger any Illumina manifest at QC time.
  needed <- unique(unlist(pkg_map, use.names = FALSE))
  missing <- needed[!vapply(needed, requireNamespace, quietly = TRUE, FUN.VALUE = logical(1))]
  if (length(missing) == 0) return(invisible(TRUE))
  log_error(
    "Missing array support package(s): ",
    paste(missing, collapse = ", "),
    ". Install them via pixi dependencies (pixi.toml), then run `pixi install`."
  )
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

validate_samples_schema <- function(samples) {
  missing <- setdiff(c("sample_id"), names(samples))
  if (length(missing) > 0) log_error("samples.csv missing required columns:", paste(missing, collapse = ", "))
  if (!all(c("SentrixBarcode", "SentrixPosition") %in% names(samples)) &&
      !("idat_basename" %in% names(samples))) {
    log_error("samples.csv must contain either (SentrixBarcode, SentrixPosition) or idat_basename for each sample")
  }
  dup_ids <- samples$sample_id[duplicated(samples$sample_id)]
  if (length(dup_ids) > 0) log_error("Duplicate sample_id values:", paste(unique(dup_ids), collapse = ", "))
  invisible(TRUE)
}

validate_config_schema <- function(cfg) {
  for (section in c("project", "idat", "groups", "qc", "normalization", "filter", "batch", "cell_counts", "clustering")) {
    if (is.null(cfg[[section]])) log_error("Missing config section [", section, "]")
  }
  valid_norm <- c("noob", "quantile", "swan", "funnorm")
  if (!(cfg$normalization$method %in% valid_norm)) log_error("Unsupported normalization.method:", cfg$normalization$method)
  valid_arrays <- c("450K", "EPIC", "EPIC_V2")
  if (!(cfg$project$array_type %in% valid_arrays)) log_error("Unsupported project.array_type:", cfg$project$array_type)
  valid_layouts <- c("flat", "per_barcode_subdir")
  if (!(cfg$idat$layout %in% valid_layouts)) log_error("Unsupported idat.layout:", cfg$idat$layout)
  invisible(TRUE)
}

validate_group_column <- function(cfg, samples) {
  group_col <- cfg$groups$primary_group_col
  if (!(group_col %in% names(samples))) log_error("groups.primary_group_col not found in samples.csv:", group_col)
  if (any(is.na(samples[[group_col]]) | trimws(as.character(samples[[group_col]])) == "")) {
    log_error("Grouping column contains missing/empty values:", group_col)
  }
  invisible(TRUE)
}

resolve_idat_basenames <- function(samples, cfg) {
  base_dir <- cfg$idat$base_dir
  layout <- cfg$idat$layout
  samples <- as_tibble(samples)
  has_pair <- all(c("SentrixBarcode", "SentrixPosition") %in% names(samples))
  sample_base_dir <- rep(base_dir, nrow(samples))
  if ("idat_base_dir" %in% names(samples)) {
    override <- as.character(samples$idat_base_dir)
    idx <- which(!is.na(override) & trimws(override) != "")
    sample_base_dir[idx] <- override[idx]
  }
  from_pair <- rep(NA_character_, nrow(samples))
  if (has_pair) {
    barcode <- as.character(samples$SentrixBarcode)
    pos <- as.character(samples$SentrixPosition)
    valid_pair <- !is.na(barcode) & !is.na(pos) & trimws(barcode) != "" & trimws(pos) != ""
    from_pair_calc <- if (layout == "flat") {
      file.path(sample_base_dir, paste0(barcode, "_", pos))
    } else {
      file.path(sample_base_dir, barcode, paste0(barcode, "_", pos))
    }
    from_pair[valid_pair] <- from_pair_calc[valid_pair]
  }
  from_override <- rep(NA_character_, nrow(samples))
  if ("idat_basename" %in% names(samples)) {
    from_override <- as.character(samples$idat_basename)
    from_override[is.na(from_override) | trimws(from_override) == ""] <- NA_character_
  }
  samples$Basename <- dplyr::coalesce(from_override, from_pair)
  samples$BasenameSource <- ifelse(!is.na(from_override), "idat_basename_override", "sentrix_pair")
  samples$EffectiveIdatBaseDir <- sample_base_dir
  if (any(is.na(samples$Basename) | trimws(samples$Basename) == "")) {
    bad <- samples %>% dplyr::filter(is.na(Basename) | trimws(Basename) == "")
    log_error("Could not resolve IDAT basename for sample_id(s):", paste(bad$sample_id, collapse = ", "))
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

validate_project <- function(cfg, samples, fail_on_missing_idats = TRUE) {
  validate_config_schema(cfg)
  validate_samples_schema(samples)
  validate_group_column(cfg, samples)
  resolved <- resolve_idat_basenames(samples, cfg)
  dup_basenames <- resolved$Basename[duplicated(resolved$Basename)]
  if (length(dup_basenames) > 0) {
    log_error("Duplicate resolved Basename values:", paste(unique(dup_basenames), collapse = ", "))
  }
  status <- check_idat_pairs(resolved)
  if (fail_on_missing_idats && any(!status$red_exists | !status$grn_exists)) {
    bad <- status %>% filter(!red_exists | !grn_exists)
    write_table(bad, "results/tables/missing_idats.csv")
    log_error("Missing IDAT pairs detected. See results/tables/missing_idats.csv")
  }
  invisible(list(samples_resolved = resolved, idat_status = status))
}

save_plot <- function(plot_obj, path, width = 8, height = 5) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  ggplot2::ggsave(
    filename = path,
    plot = plot_obj,
    width = width,
    height = height,
    units = "in",
    dpi = 320,
    bg = "white"
  )
  invisible(path)
}

publication_palette <- c(
  "#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
  "#17becf", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"
)

theme_publication <- function(base_size = 13) {
  ggplot2::theme_minimal(base_size = base_size) +
    ggplot2::theme(
      plot.title = ggplot2::element_text(face = "bold", hjust = 0),
      axis.title = ggplot2::element_text(face = "bold"),
      legend.title = ggplot2::element_text(face = "bold"),
      panel.grid.minor = ggplot2::element_blank(),
      panel.grid.major.x = ggplot2::element_blank(),
      panel.border = ggplot2::element_rect(color = "#D0D0D0", fill = NA, linewidth = 0.4),
      axis.line = ggplot2::element_line(color = "#707070", linewidth = 0.3)
    )
}

scale_color_publication <- function(...) {
  ggplot2::scale_color_manual(values = publication_palette, ...)
}

scale_fill_publication <- function(...) {
  ggplot2::scale_fill_manual(values = publication_palette, ...)
}

pretty_table <- function(x, caption = NULL) {
  df <- as.data.frame(x)
  knitr::kable(
    df,
    format = "html",
    caption = caption,
    row.names = FALSE,
    table.attr = 'class="table table-sm table-striped table-hover"'
  )
}

load_analysis_inputs <- function() {
  rel_roots <- c("results/rds", "../results/rds", "../../results/rds")
  obj_names <- c("adjustedset.rds", "filteredset.rds", "normset.rds", "rgset.rds")
  for (root in rel_roots) {
    for (nm in obj_names) {
      p <- file.path(root, nm)
      if (file.exists(p)) return(readRDS(p))
    }
  }
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

safe_top_var_rows <- function(mat, n = 5000) {
  v <- apply(mat, 1, stats::var, na.rm = TRUE)
  ord <- order(v, decreasing = TRUE)
  mat[head(ord, min(n, nrow(mat))), , drop = FALSE]
}
