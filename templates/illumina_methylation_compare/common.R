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
  RcppTOML::parseTOML(path)
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

validate_config_schema <- function(cfg) {
  for (section in c("project", "input", "groups", "dmp", "dmr", "enrichment", "drilldown")) {
    if (is.null(cfg[[section]])) log_error("Missing config section [", section, "]")
  }
  valid_arrays <- c("450K", "EPIC", "EPIC_V2", "AUTO", "MIXED")
  if (!(cfg$project$array_type %in% valid_arrays)) log_error("Unsupported project.array_type:", cfg$project$array_type)
  if (!(cfg$dmp$adjust_method %in% p.adjust.methods)) {
    log_error("Unsupported dmp.adjust_method:", cfg$dmp$adjust_method)
  }
  has_runs_file <- !is.null(cfg$input$input_runs_file) && nzchar(trimws(as.character(cfg$input$input_runs_file)))
  has_fallback_dir <- !is.null(cfg$input$processed_results_dir) && nzchar(trimws(as.character(cfg$input$processed_results_dir)))
  if (!has_runs_file && !has_fallback_dir) {
    log_error("Configure either input.input_runs_file or input.processed_results_dir")
  }
  invisible(TRUE)
}

validate_samples_schema <- function(samples, cfg) {
  missing <- setdiff(c("sample_id", cfg$groups$primary_group_col), names(samples))
  if (length(missing) > 0) log_error("samples.csv missing required columns:", paste(missing, collapse = ", "))
  dup_ids <- samples$sample_id[duplicated(samples$sample_id)]
  if (length(dup_ids) > 0) log_error("Duplicate sample_id values:", paste(unique(dup_ids), collapse = ", "))
  invisible(TRUE)
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

validate_project <- function(cfg, samples) {
  validate_config_schema(cfg)
  validate_samples_schema(samples, cfg)
  validate_groups(cfg, samples)
  validate_input_sources(cfg, samples)
  invisible(TRUE)
}

save_plot <- function(plot_obj, path, width = 8, height = 5) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  ggplot2::ggsave(filename = path, plot = plot_obj, width = width, height = height)
  invisible(path)
}

coalesce_chr <- function(x, default = "") {
  if (is.null(x) || length(x) == 0 || is.na(x)) return(default)
  as.character(x[[1]])
}

resolve_path <- function(path) {
  if (is.null(path) || !nzchar(trimws(as.character(path)))) return(path)
  if (file.exists(path)) return(path)
  alt <- file.path("..", path)
  if (file.exists(alt)) return(alt)
  path
}

parse_bool <- function(x, default = TRUE) {
  if (is.null(x) || length(x) == 0 || is.na(x)) return(default)
  if (is.logical(x)) return(isTRUE(x))
  v <- tolower(trimws(as.character(x[[1]])))
  if (v %in% c("true", "t", "1", "yes", "y")) return(TRUE)
  if (v %in% c("false", "f", "0", "no", "n")) return(FALSE)
  default
}

parse_sample_list <- function(x) {
  if (is.null(x) || length(x) == 0 || is.na(x)) return(character(0))
  raw <- trimws(as.character(x[[1]]))
  if (!nzchar(raw)) return(character(0))
  out <- unlist(strsplit(raw, "[,;]"))
  unique(trimws(out[nzchar(trimws(out))]))
}

resolve_input_roots <- function(processed_results_dir) {
  roots <- c(
    processed_results_dir,
    file.path("..", processed_results_dir),
    "../results/rds",
    "../../results/rds"
  )
  unique(roots[nzchar(trimws(roots))])
}

find_upstream_rds <- function(processed_results_dir) {
  obj_names <- c("adjustedset.rds", "filteredset.rds", "normset.rds", "rgset.rds")
  for (root in resolve_input_roots(processed_results_dir)) {
    for (nm in obj_names) {
      p <- file.path(root, nm)
      if (file.exists(p)) return(list(path = p, root = root))
    }
  }
  NULL
}

load_input_runs <- function(path = "config/input_runs.csv") {
  p <- resolve_path(path)
  if (!file.exists(p)) return(NULL)
  df <- readr::read_csv(p, show_col_types = FALSE)
  if (!("processed_results_dir" %in% names(df))) {
    log_error("input_runs.csv must include 'processed_results_dir'")
  }
  if (!("run_id" %in% names(df))) df$run_id <- paste0("run", seq_len(nrow(df)))
  if (!("enabled" %in% names(df))) df$enabled <- TRUE
  if (!("include_samples" %in% names(df))) df$include_samples <- ""
  if (!("exclude_samples" %in% names(df))) df$exclude_samples <- ""
  if (!("array_type" %in% names(df))) df$array_type <- ""
  df
}

validate_input_sources <- function(cfg, samples) {
  input_runs_file <- coalesce_chr(cfg$input$input_runs_file, "")
  runs_df <- if (nzchar(input_runs_file)) load_input_runs(input_runs_file) else NULL
  if (!is.null(runs_df) && nrow(runs_df) > 0) {
    enabled <- vapply(runs_df$enabled, parse_bool, logical(1), default = TRUE)
    if (!any(enabled)) log_error("No enabled rows in", input_runs_file)
    bad_dirs <- runs_df$processed_results_dir[enabled & !nzchar(trimws(as.character(runs_df$processed_results_dir)))]
    if (length(bad_dirs) > 0) log_error("Enabled rows in input_runs.csv require processed_results_dir")
    if ("sample_id" %in% names(samples)) {
      all_ids <- unique(samples$sample_id)
      for (i in which(enabled)) {
        missing_includes <- setdiff(parse_sample_list(runs_df$include_samples[[i]]), all_ids)
        if (length(missing_includes) > 0) {
          log_warn("run", coalesce_chr(runs_df$run_id[[i]], paste0("run", i)),
                   "include_samples not found in samples.csv:",
                   paste(missing_includes, collapse = ", "))
        }
      }
    }
    for (i in which(enabled)) {
      at <- normalize_array_type_for_gometh(coalesce_chr(runs_df$array_type[[i]], ""))
      if (is.na(at) && nzchar(coalesce_chr(runs_df$array_type[[i]], ""))) {
        log_warn("run", coalesce_chr(runs_df$run_id[[i]], paste0("run", i)),
                 "has unsupported array_type in input_runs.csv:", coalesce_chr(runs_df$array_type[[i]], ""),
                 "(supported: 450K, EPIC, EPIC_V2)")
      }
    }
    return(invisible(TRUE))
  }
  fallback_dir <- coalesce_chr(cfg$input$processed_results_dir, "")
  if (!nzchar(fallback_dir)) {
    log_error("No input_runs file and no fallback input.processed_results_dir configured")
  }
  invisible(TRUE)
}

load_single_input <- function(run_id, processed_results_dir, configured_array_type = "") {
  hit <- find_upstream_rds(processed_results_dir)
  if (is.null(hit)) {
    log_error("No upstream methylation object found for run", run_id, "under:", processed_results_dir)
  }
  obj <- readRDS(hit$path)
  beta <- get_beta_matrix(obj)
  mval <- get_m_matrix(obj)
  pdata <- get_pdata(obj)
  if (!("sample_id" %in% names(pdata))) pdata$sample_id <- colnames(beta)
  ann <- get_annotation_df(obj)
  if (!("Name" %in% names(ann))) ann$Name <- rownames(beta)
  list(
    run_id = run_id,
    source_dir = hit$root,
    object_path = hit$path,
    configured_array_type = coalesce_chr(configured_array_type, ""),
    configured_array_type_norm = normalize_array_type_for_gometh(coalesce_chr(configured_array_type, "")),
    beta = beta,
    m = mval,
    pdata = tibble::as_tibble(pdata),
    annotation = tibble::as_tibble(ann)
  )
}

subset_run_samples <- function(run, include_samples, exclude_samples, allowed_samples = character(0)) {
  sid <- as.character(run$pdata$sample_id)
  keep <- rep(TRUE, length(sid))
  includes <- parse_sample_list(include_samples)
  excludes <- parse_sample_list(exclude_samples)
  if (length(includes) > 0) keep <- keep & sid %in% includes
  if (length(excludes) > 0) keep <- keep & !(sid %in% excludes)
  if (length(allowed_samples) > 0) keep <- keep & sid %in% allowed_samples
  run$beta <- run$beta[, keep, drop = FALSE]
  run$m <- run$m[, keep, drop = FALSE]
  run$pdata <- run$pdata[keep, , drop = FALSE]
  run
}

combine_inputs <- function(runs) {
  if (length(runs) == 0) log_error("No runs left after filtering")
  common_probes <- Reduce(intersect, lapply(runs, function(x) rownames(x$beta)))
  if (length(common_probes) == 0) log_error("No shared probes across input runs")
  runs <- lapply(runs, function(x) {
    x$beta <- x$beta[common_probes, , drop = FALSE]
    x$m <- x$m[common_probes, , drop = FALSE]
    x$annotation <- dplyr::filter(x$annotation, .data$Name %in% common_probes)
    x
  })
  sample_ids <- unlist(lapply(runs, function(x) as.character(x$pdata$sample_id)))
  dup <- unique(sample_ids[duplicated(sample_ids)])
  if (length(dup) > 0) {
    log_error("Duplicate sample_id across runs:", paste(dup, collapse = ", "),
              ". Rename sample_id in config/samples.csv to make them unique.")
  }
  beta <- do.call(cbind, lapply(runs, `[[`, "beta"))
  mval <- do.call(cbind, lapply(runs, `[[`, "m"))
  pdata <- dplyr::bind_rows(lapply(runs, function(x) {
    dplyr::mutate(x$pdata, run_id = x$run_id, input_source = x$source_dir)
  }))
  ann <- runs[[1]]$annotation
  ann <- ann[match(common_probes, ann$Name), , drop = FALSE]
  summary_tbl <- tibble::tibble(
    run_id = vapply(runs, `[[`, character(1), "run_id"),
    source_dir = vapply(runs, `[[`, character(1), "source_dir"),
    object_path = vapply(runs, `[[`, character(1), "object_path"),
    configured_array_type = vapply(runs, `[[`, character(1), "configured_array_type"),
    configured_array_type_norm = vapply(runs, `[[`, character(1), "configured_array_type_norm"),
    n_samples = vapply(runs, function(x) ncol(x$beta), integer(1)),
    n_common_probes = length(common_probes)
  )
  write_table(summary_tbl, "../results/tables/input_run_summary.csv")
  structure(
    list(beta = beta, m = mval, pdata = pdata, annotation = ann, run_summary = summary_tbl),
    class = c("combined_methylation_inputs", "list")
  )
}

load_analysis_inputs <- function(cfg, samples = NULL) {
  require_sheet <- parse_bool(cfg$input$require_samples_in_sheet, default = TRUE)
  allowed_samples <- character(0)
  if (!is.null(samples) && "sample_id" %in% names(samples) && isTRUE(require_sheet)) {
    allowed_samples <- unique(samples$sample_id)
  }
  input_runs_file <- coalesce_chr(cfg$input$input_runs_file, "")
  runs_df <- if (nzchar(input_runs_file)) load_input_runs(input_runs_file) else NULL
  if (!is.null(runs_df) && nrow(runs_df) > 0) {
    enabled <- vapply(runs_df$enabled, parse_bool, logical(1), default = TRUE)
    runs_df <- runs_df[enabled, , drop = FALSE]
    runs <- lapply(seq_len(nrow(runs_df)), function(i) {
      row <- runs_df[i, , drop = FALSE]
      run_id <- coalesce_chr(row$run_id, paste0("run", i))
      run <- load_single_input(
        run_id = run_id,
        processed_results_dir = coalesce_chr(row$processed_results_dir),
        configured_array_type = coalesce_chr(row$array_type, "")
      )
      run <- subset_run_samples(
        run,
        include_samples = row$include_samples[[1]],
        exclude_samples = row$exclude_samples[[1]],
        allowed_samples = allowed_samples
      )
      if (ncol(run$beta) == 0) {
        log_warn("No samples left after filtering for run", run_id, "- skipping run.")
        return(NULL)
      }
      run
    })
    runs <- Filter(Negate(is.null), runs)
    return(combine_inputs(runs))
  }
  fallback <- coalesce_chr(cfg$input$processed_results_dir, "")
  if (!nzchar(fallback)) {
    log_error("No input runs configured and no input.processed_results_dir fallback set")
  }
  run <- load_single_input(run_id = "run1", processed_results_dir = fallback, configured_array_type = coalesce_chr(cfg$project$array_type, ""))
  run <- subset_run_samples(run, include_samples = "", exclude_samples = "", allowed_samples = allowed_samples)
  if (ncol(run$beta) == 0) log_error("No samples left after filtering for fallback input.processed_results_dir")
  combine_inputs(list(run))
}

get_beta_matrix <- function(obj) {
  if (inherits(obj, "combined_methylation_inputs")) return(obj$beta)
  if (!requireNamespace("minfi", quietly = TRUE)) log_error("Package 'minfi' is required")
  minfi::getBeta(obj)
}

get_m_matrix <- function(obj) {
  if (inherits(obj, "combined_methylation_inputs")) return(obj$m)
  if (!requireNamespace("minfi", quietly = TRUE)) log_error("Package 'minfi' is required")
  minfi::getM(obj)
}

get_pdata <- function(obj) {
  if (inherits(obj, "combined_methylation_inputs")) return(as.data.frame(obj$pdata))
  as.data.frame(SummarizedExperiment::colData(obj))
}

get_annotation_df <- function(obj) {
  if (inherits(obj, "combined_methylation_inputs")) return(tibble::as_tibble(obj$annotation))
  ann <- tryCatch(minfi::getAnnotation(obj), error = function(e) NULL)
  if (is.null(ann)) return(tibble(Name = rownames(obj)))
  ann_df <- as.data.frame(ann)
  ann_df$Name <- rownames(ann_df)
  as_tibble(ann_df)
}

normalize_array_type_for_gometh <- function(array_type) {
  at <- toupper(trimws(as.character(array_type)))
  dplyr::case_when(
    at %in% c("AUTO", "MIXED", "") ~ NA_character_,
    at %in% c("450K", "HM450", "HUMANMETHYLATION450", "HUMANMETHYLATION450K") ~ "450K",
    at %in% c("EPIC", "850K", "EPIC850K") ~ "EPIC",
    at %in% c("EPIC_V2", "EPICV2", "850K_V2") ~ "EPIC_V2",
    TRUE ~ NA_character_
  )
}

infer_gometh_array_type <- function(project_array_type, run_array_types = character(0)) {
  configured <- normalize_array_type_for_gometh(project_array_type)
  runs_norm <- unique(na.omit(vapply(run_array_types, normalize_array_type_for_gometh, character(1))))
  inferred <- NA_character_
  if (length(runs_norm) > 0) {
    if ("450K" %in% runs_norm) {
      inferred <- "450K"
    } else if (all(runs_norm == "EPIC_V2")) {
      inferred <- "EPIC_V2"
    } else if (all(runs_norm %in% c("EPIC", "EPIC_V2"))) {
      inferred <- "EPIC"
    } else if (length(runs_norm) == 1) {
      inferred <- runs_norm[[1]]
    }
  }
  if (!is.na(inferred) && !is.na(configured) && configured != inferred) {
    log_warn("project.array_type (", project_array_type, ") differs from inferred run composition (",
             inferred, "); enrichment will use inferred value.")
  }
  if (!is.na(inferred)) return(inferred)
  configured
}
