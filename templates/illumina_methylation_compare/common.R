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

load_sample_paths <- function(path = "config/samples_paths.csv") {
  p <- resolve_path(path)
  if (!file.exists(p)) return(tibble::tibble(sample_id = character(0)))
  readr::read_csv(p, show_col_types = FALSE)
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

normalize_group_value <- function(x) {
  gsub("[^a-z0-9]+", "", tolower(trimws(as.character(x))))
}

load_group_map <- function(path = "config/group_map.csv") {
  p <- resolve_path(path)
  if (!file.exists(p)) return(NULL)
  gm <- readr::read_csv(p, show_col_types = FALSE, comment = "#")
  required <- c("group_raw", "group_compare")
  missing <- setdiff(required, names(gm))
  if (length(missing) > 0) {
    log_error("group_map.csv missing required columns:", paste(missing, collapse = ", "))
  }
  if (!("enabled" %in% names(gm))) gm$enabled <- TRUE
  if (!("run_id" %in% names(gm))) gm$run_id <- ""
  if (!("dataset_id" %in% names(gm))) gm$dataset_id <- ""
  gm <- gm[vapply(gm$enabled, parse_bool, logical(1), default = TRUE), , drop = FALSE]
  gm$key_norm <- normalize_group_value(gm$group_raw)
  gm
}

apply_group_map <- function(samples, group_map = NULL, group_col = "group", run_col = "run_id", dataset_col = "dataset_id") {
  if (is.null(group_map) || nrow(group_map) == 0) return(samples)
  if (!(group_col %in% names(samples))) return(samples)
  mapped <- samples
  mapped$group_raw <- mapped[[group_col]]
  mapped$group_norm <- normalize_group_value(mapped$group_raw)
  mapped$group_compare <- NA_character_

  for (i in seq_len(nrow(group_map))) {
    row <- group_map[i, , drop = FALSE]
    match_idx <- mapped$group_norm == row$key_norm[[1]]
    rid <- coalesce_chr(row$run_id, "")
    did <- coalesce_chr(row$dataset_id, "")
    if (nzchar(rid) && (run_col %in% names(mapped))) {
      match_idx <- match_idx & (as.character(mapped[[run_col]]) == rid)
    }
    if (nzchar(did) && (dataset_col %in% names(mapped))) {
      match_idx <- match_idx & (as.character(mapped[[dataset_col]]) == did)
    }
    mapped$group_compare[match_idx] <- coalesce_chr(row$group_compare, "")
  }

  keep_raw <- is.na(mapped$group_compare) | trimws(mapped$group_compare) == ""
  mapped$group_compare[keep_raw] <- as.character(mapped$group_raw[keep_raw])
  mapped[[group_col]] <- mapped$group_compare
  mapped$group_norm <- NULL
  mapped
}

standardize_run_table <- function(df, source_label) {
  if (is.null(df) || nrow(df) == 0) return(NULL)
  if (!("processed_results_dir" %in% names(df))) {
    log_error(source_label, "must include 'processed_results_dir'")
  }
  if (!("run_id" %in% names(df))) df$run_id <- paste0("run", seq_len(nrow(df)))
  if (!("enabled" %in% names(df))) df$enabled <- TRUE
  if (!("include_samples" %in% names(df))) df$include_samples <- ""
  if (!("exclude_samples" %in% names(df))) df$exclude_samples <- ""
  if (!("array_type" %in% names(df))) df$array_type <- ""
  if (!("dataset_id" %in% names(df))) df$dataset_id <- ""
  if (!("process_template" %in% names(df))) df$process_template <- ""
  if (!("genome_build" %in% names(df))) df$genome_build <- ""
  if (!("samples_file" %in% names(df))) df$samples_file <- ""
  df
}

load_input_registry <- function(path = "config/input_registry.csv") {
  p <- resolve_path(path)
  if (!file.exists(p)) return(NULL)
  df <- readr::read_csv(p, show_col_types = FALSE)
  standardize_run_table(df, "input_registry.csv")
}

resolve_run_table <- function(cfg) {
  registry_file <- coalesce_chr(cfg$input$input_registry_file, "")
  if (nzchar(registry_file)) {
    runs_df <- load_input_registry(registry_file)
    if (!is.null(runs_df) && nrow(runs_df) > 0) {
      return(list(runs = runs_df, source = "input_registry", path = registry_file))
    }
  }
  list(runs = NULL, source = "input_registry", path = registry_file)
}

load_comparisons <- function(path = "config/comparisons.csv") {
  p <- resolve_path(path)
  if (!file.exists(p)) return(NULL)
  df <- readr::read_csv(p, show_col_types = FALSE)
  required <- c("comparison_id", "base_group", "target_group")
  missing <- setdiff(required, names(df))
  if (length(missing) > 0) log_error("comparisons.csv missing required columns:", paste(missing, collapse = ", "))
  if (!("name" %in% names(df))) df$name <- df$comparison_id
  if (!("enabled" %in% names(df))) df$enabled <- TRUE
  if (!("covariates" %in% names(df))) df$covariates <- ""
  if (!("alpha" %in% names(df))) df$alpha <- NA_real_
  if (!("delta_beta_min" %in% names(df))) df$delta_beta_min <- NA_real_
  df
}

sanitize_id <- function(x) {
  gsub("[^A-Za-z0-9._-]+", "_", trimws(as.character(x)))
}

resolve_input_roots <- function(processed_results_dir) {
  p <- coalesce_chr(processed_results_dir, "")
  if (!nzchar(p)) return(character(0))
  cands <- unique(c(p, resolve_path(p)))
  cands[nzchar(trimws(cands))]
}

find_upstream_rds <- function(processed_results_dir) {
  obj_names <- c("adjustedset.rds", "filteredset.rds", "normset.rds", "rgset.rds")
  roots <- resolve_input_roots(processed_results_dir)
  if (length(roots) == 0) return(NULL)
  for (root in roots) {
    for (nm in obj_names) {
      p <- file.path(root, nm)
      if (file.exists(p)) return(list(path = p, root = root))
    }
  }
  NULL
}

validate_config_schema <- function(cfg) {
  for (section in c("project", "input", "groups", "comparisons", "dmp", "dmr", "enrichment", "drilldown")) {
    if (is.null(cfg[[section]])) log_error("Missing config section [", section, "]")
  }
  valid_arrays <- c("450K", "EPIC", "EPIC_V2", "AUTO", "MIXED")
  if (!(cfg$project$array_type %in% valid_arrays)) log_error("Unsupported project.array_type:", cfg$project$array_type)
  if (!(cfg$dmp$adjust_method %in% p.adjust.methods)) {
    log_error("Unsupported dmp.adjust_method:", cfg$dmp$adjust_method)
  }
  has_registry <- !is.null(cfg$input$input_registry_file) && nzchar(trimws(as.character(cfg$input$input_registry_file)))
  has_comp <- !is.null(cfg$comparisons$comparisons_file) && nzchar(trimws(as.character(cfg$comparisons$comparisons_file)))
  if (!has_registry) {
    log_error("Configure input.input_registry_file")
  }
  if (!has_comp) {
    log_error("Configure comparisons.comparisons_file")
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
  invisible(table(samples[[group_col]]))
}

validate_comparisons <- function(cfg, samples) {
  comp_file <- coalesce_chr(cfg$comparisons$comparisons_file, "config/comparisons.csv")
  cmp <- load_comparisons(comp_file)
  if (is.null(cmp) || nrow(cmp) == 0) log_error("No rows found in comparisons file:", comp_file)
  enabled <- vapply(cmp$enabled, parse_bool, logical(1), default = TRUE)
  cmp <- cmp[enabled, , drop = FALSE]
  if (nrow(cmp) == 0) log_error("No enabled comparisons in", comp_file)
  bad <- cmp$comparison_id[duplicated(cmp$comparison_id)]
  if (length(bad) > 0) log_error("Duplicate comparison_id values:", paste(unique(bad), collapse = ", "))
  group_col <- cfg$groups$primary_group_col
  counts <- table(samples[[group_col]])
  for (i in seq_len(nrow(cmp))) {
    base <- as.character(cmp$base_group[[i]])
    target <- as.character(cmp$target_group[[i]])
    if (!(base %in% names(counts))) log_error("Comparison", cmp$comparison_id[[i]], "base_group not found:", base)
    if (!(target %in% names(counts))) log_error("Comparison", cmp$comparison_id[[i]], "target_group not found:", target)
    if (as.integer(counts[[base]]) < 2) log_error("Comparison", cmp$comparison_id[[i]], "base_group requires >=2 samples:", base)
    if (as.integer(counts[[target]]) < 2) log_error("Comparison", cmp$comparison_id[[i]], "target_group requires >=2 samples:", target)
  }
  invisible(cmp)
}

validate_input_sources <- function(cfg, samples) {
  run_info <- resolve_run_table(cfg)
  runs_df <- run_info$runs

  if (!is.null(runs_df) && nrow(runs_df) > 0) {
    enabled <- vapply(runs_df$enabled, parse_bool, logical(1), default = TRUE)
    if (!any(enabled)) log_error("No enabled rows in", run_info$path)

    for (i in which(enabled)) {
      row <- runs_df[i, , drop = FALSE]
      run_id <- coalesce_chr(row$run_id, paste0("run", i))
      pdir <- coalesce_chr(row$processed_results_dir, "")
      if (!nzchar(pdir)) {
        log_error("Enabled run", run_id, "is missing processed_results_dir")
      }
      hit <- find_upstream_rds(pdir)
      if (is.null(hit)) {
        log_error("No upstream methylation object found for run", run_id, "under:", pdir,
                  "(checked only configured path and its resolved project-relative form)")
      }

      at <- normalize_array_type_for_gometh(coalesce_chr(row$array_type, ""))
      if (is.na(at) && nzchar(coalesce_chr(row$array_type, ""))) {
        log_warn("run", run_id,
                 "has unsupported array_type:", coalesce_chr(row$array_type, ""),
                 "(supported: 450K, EPIC, EPIC_V2)")
      }

      sf <- coalesce_chr(row$samples_file, "")
      if (nzchar(sf) && !file.exists(resolve_path(sf))) {
        log_error("Run", run_id, "samples_file does not exist:", sf)
      }

      if ("sample_id" %in% names(samples)) {
        all_ids <- unique(samples$sample_id)
        missing_includes <- setdiff(parse_sample_list(row$include_samples[[1]]), all_ids)
        if (length(missing_includes) > 0) {
          log_warn("run", run_id,
                   "include_samples not found in samples.csv:",
                   paste(missing_includes, collapse = ", "))
        }
      }
    }
    return(invisible(TRUE))
  }

  log_error("No enabled runs found in", run_info$path)
}

validate_project <- function(cfg, samples) {
  validate_config_schema(cfg)
  gm <- load_group_map(coalesce_chr(cfg$input$group_map_file, ""))
  samples_norm <- apply_group_map(samples, gm, group_col = cfg$groups$primary_group_col)
  validate_samples_schema(samples_norm, cfg)
  validate_groups(cfg, samples_norm)
  validate_comparisons(cfg, samples_norm)
  validate_input_sources(cfg, samples_norm)
  invisible(TRUE)
}

save_plot <- function(plot_obj, path, width = 8, height = 5) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  ggplot2::ggsave(filename = path, plot = plot_obj, width = width, height = height)
  invisible(path)
}

select_report_columns <- function(df, preferred = NULL, max_extra = 0) {
  if (is.null(preferred) || length(preferred) == 0) return(df)
  keep <- intersect(preferred, names(df))
  if (max_extra > 0) {
    extras <- setdiff(names(df), keep)
    keep <- c(keep, head(extras, max_extra))
  }
  if (length(keep) == 0) return(df)
  df[, keep, drop = FALSE]
}

format_report_table <- function(df) {
  tbl <- as.data.frame(df, stringsAsFactors = FALSE)
  if (nrow(tbl) == 0) return(tbl)

  for (nm in names(tbl)) {
    col <- tbl[[nm]]
    if (!is.numeric(col)) next

    nm_lower <- tolower(nm)
    if (nm_lower %in% c("p.value", "adj.p.val", "fdr", "qvalue", "q.value", "pvalue", "p_val", "adj_p_val")) {
      tbl[[nm]] <- ifelse(is.na(col), NA_character_, formatC(col, format = "e", digits = 2))
      next
    }

    if (nm_lower %in% c("delta_beta", "logfc", "aveexpr", "estimate", "effect", "mean_beta", "median_beta")) {
      tbl[[nm]] <- ifelse(is.na(col), NA_character_, formatC(col, format = "f", digits = 3))
      next
    }

    if (nm_lower %in% c("pos", "start", "end", "width", "n", "n_samples", "n_common_probes")) {
      tbl[[nm]] <- ifelse(is.na(col), NA_character_, format(round(col, 0), big.mark = ",", trim = TRUE, scientific = FALSE))
      next
    }

    if (all(is.finite(col) | is.na(col)) && max(abs(col), na.rm = TRUE) >= 1000) {
      tbl[[nm]] <- ifelse(is.na(col), NA_character_, format(round(col, 0), big.mark = ",", trim = TRUE, scientific = FALSE))
      next
    }

    tbl[[nm]] <- ifelse(is.na(col), NA_character_, formatC(col, format = "f", digits = 3))
  }

  tbl
}

report_asset_href <- function(path) {
  p <- as.character(path[[1]])
  if (startsWith(p, "results/")) return(file.path("..", p))
  p
}

report_download_link <- function(path, label = "Download CSV") {
  p <- as.character(path[[1]])
  htmltools::tags$p(
    style = "margin: 0.5rem 0 1.5rem;",
    htmltools::tags$a(
      href = report_asset_href(p),
      download = basename(p),
      paste0(label, ": ", basename(p))
    )
  )
}

render_report_table <- function(df,
                                preferred = NULL,
                                page_length = 10,
                                max_extra = 0,
                                caption = NULL) {
  selected <- select_report_columns(df, preferred = preferred, max_extra = max_extra)
  numeric_cols <- names(selected)[vapply(selected, is.numeric, logical(1))]
  tbl <- format_report_table(selected)
  if (requireNamespace("DT", quietly = TRUE)) {
    use_scroll_x <- ncol(tbl) > 6 || any(nchar(names(tbl)) > 18) || sum(nchar(names(tbl))) > 80
    table_class <- if (use_scroll_x) "compact stripe hover nowrap" else "compact stripe hover"
    cap <- NULL
    if (!is.null(caption) && nzchar(caption)) {
      cap <- htmltools::tags$caption(
        style = "caption-side: top; text-align: left; font-weight: 600; padding-bottom: 0.5rem;",
        caption
      )
    }
    return(DT::datatable(
      tbl,
      rownames = FALSE,
      caption = cap,
      class = table_class,
      options = list(
        pageLength = page_length,
        lengthMenu = list(c(10, 20, 50, 100), c("10", "20", "50", "100")),
        scrollX = use_scroll_x,
        autoWidth = TRUE,
        dom = "tip",
        columnDefs = c(
          list(list(className = "dt-left", targets = "_all")),
          if (length(numeric_cols) > 0) list(list(className = "dt-right", targets = which(names(tbl) %in% numeric_cols) - 1)) else list()
        ),
        initComplete = DT::JS("function(settings){var api=this.api(); $(api.table().header()).find('th').css('text-align','left'); api.columns('.dt-right').header().to$().css('text-align','right'); api.columns.adjust();}"),
        drawCallback = DT::JS("function(){this.api().columns.adjust();}")
      ),
      fillContainer = FALSE
    ))
  }
  knitr::kable(tbl, format = "html", caption = caption)
}

load_single_input <- function(run_id,
                              processed_results_dir,
                              configured_array_type = "",
                              dataset_id = "",
                              process_template = "",
                              genome_build = "",
                              samples_file = "") {
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
    dataset_id = coalesce_chr(dataset_id, ""),
    process_template = coalesce_chr(process_template, ""),
    genome_build = coalesce_chr(genome_build, ""),
    samples_file = coalesce_chr(samples_file, ""),
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

normalize_probe_ids_for_compare <- function(probe_ids, array_type = "") {
  at <- normalize_array_type_for_gometh(array_type)
  ids <- as.character(probe_ids)
  if (identical(at, "EPIC_V2")) {
    ids <- sub("_[A-Za-z]+[0-9]+$", "", ids)
  }
  ids
}

collapse_matrix_rows_by_id <- function(mat, probe_ids) {
  ids <- as.character(probe_ids)
  if (length(ids) != nrow(mat)) {
    log_error("collapse_matrix_rows_by_id received mismatched probe_ids and matrix rows")
  }
  if (!anyDuplicated(ids)) {
    rownames(mat) <- ids
    return(mat)
  }
  sums <- rowsum(mat, group = ids, reorder = FALSE, na.rm = TRUE)
  counts <- as.numeric(table(ids)[rownames(sums)])
  collapsed <- sums / counts
  rownames(collapsed) <- rownames(sums)
  collapsed
}

collapse_annotation_by_id <- function(annotation, probe_ids) {
  ann <- tibble::as_tibble(annotation)
  probe_map <- tibble::tibble(
    Name_original = as.character(probe_ids),
    probe_id_compare = as.character(probe_ids)
  )
  if ("Name" %in% names(ann)) {
    ann$Name_original <- as.character(ann$Name)
    ann <- dplyr::left_join(ann, probe_map, by = "Name_original")
    ann <- ann[!is.na(ann$probe_id_compare), , drop = FALSE]
  } else if (nrow(ann) == nrow(probe_map)) {
    ann$Name_original <- probe_map$Name_original
    ann$probe_id_compare <- probe_map$probe_id_compare
  } else {
    log_error("Annotation table cannot be aligned to probe IDs for comparison")
  }
  ann <- ann[!duplicated(ann$probe_id_compare), , drop = FALSE]
  ann$Name <- ann$probe_id_compare
  ann$probe_id_compare <- NULL
  ann
}

normalize_run_probes_for_compare <- function(run) {
  probe_ids <- rownames(run$beta)
  if (is.null(probe_ids) || length(probe_ids) == 0) {
    log_error("Input run", run$run_id, "has no probe row names")
  }
  probe_ids_norm <- normalize_probe_ids_for_compare(probe_ids, run$configured_array_type)
  if (all(probe_ids_norm == probe_ids) && !anyDuplicated(probe_ids_norm)) {
    return(run)
  }

  dup_n <- sum(duplicated(probe_ids_norm))
  if (dup_n > 0) {
    log_info("Collapsing", dup_n, "duplicate normalized probes for run", run$run_id)
  }
  run$beta <- collapse_matrix_rows_by_id(run$beta, probe_ids_norm)
  run$m <- collapse_matrix_rows_by_id(run$m, probe_ids_norm)
  run$annotation <- collapse_annotation_by_id(run$annotation, probe_ids_norm)
  run
}

combine_inputs <- function(runs) {
  if (length(runs) == 0) log_error("No runs left after filtering")
  runs <- lapply(runs, normalize_run_probes_for_compare)
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
    dplyr::mutate(
      x$pdata,
      run_id = x$run_id,
      dataset_id = x$dataset_id,
      process_template = x$process_template,
      run_genome_build = x$genome_build,
      input_source = x$source_dir
    )
  }))
  ann <- runs[[1]]$annotation
  ann <- ann[match(common_probes, ann$Name), , drop = FALSE]
  summary_tbl <- tibble::tibble(
    run_id = vapply(runs, `[[`, character(1), "run_id"),
    dataset_id = vapply(runs, `[[`, character(1), "dataset_id"),
    process_template = vapply(runs, `[[`, character(1), "process_template"),
    run_genome_build = vapply(runs, `[[`, character(1), "genome_build"),
    source_dir = vapply(runs, `[[`, character(1), "source_dir"),
    object_path = vapply(runs, `[[`, character(1), "object_path"),
    configured_array_type = vapply(runs, `[[`, character(1), "configured_array_type"),
    configured_array_type_norm = vapply(runs, `[[`, character(1), "configured_array_type_norm"),
    n_samples = vapply(runs, function(x) ncol(x$beta), integer(1)),
    n_common_probes = length(common_probes)
  )
  write_table(summary_tbl, "results/tables/input_run_summary.csv")
  structure(
    list(beta = beta, m = mval, pdata = pdata, annotation = ann, run_summary = summary_tbl),
    class = c("combined_methylation_inputs", "list")
  )
}

build_runs_from_table <- function(runs_df, allowed_samples = character(0)) {
  enabled <- vapply(runs_df$enabled, parse_bool, logical(1), default = TRUE)
  runs_df <- runs_df[enabled, , drop = FALSE]
  runs <- lapply(seq_len(nrow(runs_df)), function(i) {
    row <- runs_df[i, , drop = FALSE]
    run_id <- coalesce_chr(row$run_id, paste0("run", i))
    run <- load_single_input(
      run_id = run_id,
      processed_results_dir = coalesce_chr(row$processed_results_dir),
      configured_array_type = coalesce_chr(row$array_type, ""),
      dataset_id = coalesce_chr(row$dataset_id, ""),
      process_template = coalesce_chr(row$process_template, ""),
      genome_build = coalesce_chr(row$genome_build, ""),
      samples_file = coalesce_chr(row$samples_file, "")
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
  Filter(Negate(is.null), runs)
}

load_analysis_inputs <- function(cfg, samples = NULL) {
  require_sheet <- parse_bool(cfg$input$require_samples_in_sheet, default = FALSE)
  allowed_samples <- character(0)
  if (!is.null(samples) && "sample_id" %in% names(samples) && isTRUE(require_sheet)) {
    allowed_samples <- unique(samples$sample_id)
  }

  run_info <- resolve_run_table(cfg)
  if (!is.null(run_info$runs) && nrow(run_info$runs) > 0) {
    runs <- build_runs_from_table(run_info$runs, allowed_samples = allowed_samples)
    return(combine_inputs(runs))
  }
  log_error("No enabled input runs found in", run_info$path)
}

split_sample_tables <- function(synced, group_col = "group") {
  tech_exact <- c(
    "sample_uid", "input_source", "input_object", "SentrixBarcode", "SentrixPosition",
    "idat_base_dir", "idat_basename", "Basename", "BasenameSource",
    "EffectiveIdatBaseDir", "filenames"
  )
  tech_patterns <- c(
    "\\.sheet$", "^Sentrix", "^idat_", "^Basename", "^EffectiveIdatBaseDir$", "^filenames$"
  )
  is_tech <- names(synced) %in% tech_exact
  for (pat in tech_patterns) {
    is_tech <- is_tech | grepl(pat, names(synced))
  }

  curated_first <- c("sample_id", group_col, "group_raw", "group_compare", "run_id", "dataset_id", "process_template", "array_type")
  curated_first <- unique(curated_first[curated_first %in% names(synced)])
  curated_other <- setdiff(names(synced)[!is_tech], curated_first)
  curated <- synced[, c(curated_first, curated_other), drop = FALSE]

  path_first <- c("sample_id", "sample_uid", "run_id", "dataset_id", "process_template", "array_type", "input_source", "input_object")
  path_first <- unique(path_first[path_first %in% names(synced)])
  path_other <- setdiff(names(synced)[is_tech], path_first)
  sample_paths <- synced[, c(path_first, path_other), drop = FALSE]

  list(samples = curated, sample_paths = sample_paths)
}

write_group_levels <- function(samples,
                               group_col = "group",
                               output_file = "config/group_levels.csv") {
  if (!(group_col %in% names(samples))) {
    log_error("Cannot write group levels: missing group column", group_col)
  }

  group_summary <- samples %>%
    dplyr::group_by(.data[[group_col]]) %>%
    dplyr::summarise(n_samples = dplyr::n(), .groups = "drop") %>%
    dplyr::rename(group = .data[[group_col]]) %>%
    dplyr::arrange(dplyr::desc(.data$n_samples), .data$group)

  write_table(group_summary, output_file)

  cat(sprintf("[INFO] Observed analysis groups (%s):\n", group_col))
  for (i in seq_len(nrow(group_summary))) {
    cat(sprintf("[INFO]   - %s (n=%s)\n", group_summary$group[[i]], group_summary$n_samples[[i]]))
  }
  cat(sprintf("[INFO] Wrote group summary to %s\n", output_file))
  cat("[INFO] Review config/comparisons.csv and set base_group/target_group using the group labels above before running the full compare pipeline.\n")

  invisible(group_summary)
}

sync_samples_from_inputs <- function(cfg,
                                     output_file = "config/samples.csv",
                                     paths_output_file = "config/samples_paths.csv",
                                     groups_output_file = "config/group_levels.csv",
                                     include_existing_columns = TRUE) {
  run_info <- resolve_run_table(cfg)
  if (is.null(run_info$runs) || nrow(run_info$runs) == 0) {
    log_error("sync_samples_from_inputs requires enabled input_registry entries")
  }

  runs <- build_runs_from_table(run_info$runs, allowed_samples = character(0))
  if (length(runs) == 0) {
    log_error("No runs with usable samples found while syncing sample sheet")
  }

  synced <- dplyr::bind_rows(lapply(runs, function(run) {
    pd <- run$pdata
    if (!("sample_id" %in% names(pd))) pd$sample_id <- colnames(run$beta)
    group_raw <- if ("group" %in% names(pd)) as.character(pd$group) else NA_character_
    pd <- dplyr::mutate(
      pd,
      run_id = run$run_id,
      dataset_id = run$dataset_id,
      process_template = run$process_template,
      array_type = run$configured_array_type,
      group_raw = group_raw,
      group = group_raw,
      input_source = run$source_dir,
      input_object = run$object_path,
      sample_uid = paste0(run$run_id, "::", .data$sample_id)
    )

    sf <- coalesce_chr(run$samples_file, "")
    if (nzchar(sf) && file.exists(resolve_path(sf))) {
      ext <- readr::read_csv(resolve_path(sf), show_col_types = FALSE)
      if ("sample_id" %in% names(ext)) {
        pd <- dplyr::left_join(pd, ext, by = "sample_id", suffix = c("", ".sheet"))
      }
    }

    pd
  }))

  gm <- load_group_map(coalesce_chr(cfg$input$group_map_file, "config/group_map.csv"))
  group_col <- coalesce_chr(cfg$groups$primary_group_col, "group")
  if (!(group_col %in% names(synced))) {
    synced[[group_col]] <- synced$group
  }
  synced <- apply_group_map(synced, gm, group_col = group_col, run_col = "run_id", dataset_col = "dataset_id")

  if (file.exists(output_file) && include_existing_columns) {
    existing <- readr::read_csv(output_file, show_col_types = FALSE)
    if ("sample_id" %in% names(existing)) {
      synced <- dplyr::left_join(synced, existing, by = "sample_id", suffix = c("", ".existing"))
      existing_cols <- names(synced)[grepl("\\.existing$", names(synced))]
      for (ec in existing_cols) {
        base <- sub("\\.existing$", "", ec)
        if (!(base %in% names(synced))) {
          synced[[base]] <- synced[[ec]]
        } else {
          missing_base <- is.na(synced[[base]]) | trimws(as.character(synced[[base]])) == ""
          synced[[base]][missing_base] <- synced[[ec]][missing_base]
        }
      }
      synced <- synced[, setdiff(names(synced), existing_cols), drop = FALSE]
    }
  }

  split_tbls <- split_sample_tables(synced, group_col = group_col)
  write_table(split_tbls$samples, output_file)
  write_table(split_tbls$sample_paths, paths_output_file)
  write_group_levels(split_tbls$samples, group_col = group_col, output_file = groups_output_file)
  log_info("Synced", nrow(split_tbls$samples), "samples into", output_file)
  log_info("Synced", nrow(split_tbls$sample_paths), "sample paths into", paths_output_file)
  invisible(split_tbls)
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

resolve_enabled_comparisons <- function(cfg, samples) {
  comp_file <- coalesce_chr(cfg$comparisons$comparisons_file, "config/comparisons.csv")
  cmp <- load_comparisons(comp_file)
  if (is.null(cmp) || nrow(cmp) == 0) log_error("No comparisons configured in", comp_file)
  cmp <- cmp[vapply(cmp$enabled, parse_bool, logical(1), default = TRUE), , drop = FALSE]
  if (nrow(cmp) == 0) log_error("No enabled comparisons in", comp_file)
  group_col <- cfg$groups$primary_group_col
  if (!(group_col %in% names(samples))) log_error("Group column not found in samples:", group_col)
  out <- lapply(seq_len(nrow(cmp)), function(i) {
    row <- cmp[i, , drop = FALSE]
    covars_raw <- parse_sample_list(coalesce_chr(row$covariates, ""))
    tibble::tibble(
      comparison_id = sanitize_id(coalesce_chr(row$comparison_id, paste0("cmp", i))),
      comparison_name = coalesce_chr(row$name, coalesce_chr(row$comparison_id, paste0("cmp", i))),
      base_group = coalesce_chr(row$base_group, ""),
      target_group = coalesce_chr(row$target_group, ""),
      covariates = I(list(covars_raw)),
      alpha = suppressWarnings(as.numeric(coalesce_chr(row$alpha, NA))),
      delta_beta_min = suppressWarnings(as.numeric(coalesce_chr(row$delta_beta_min, NA)))
    )
  })
  dplyr::bind_rows(out)
}

merge_input_metadata <- function(beta, pdata, samples) {
  meta <- tibble::as_tibble(pdata)
  if (!("sample_id" %in% names(meta))) {
    meta$sample_id <- colnames(beta)
  }
  meta$sample_col <- colnames(beta)
  meta <- dplyr::left_join(meta, samples, by = "sample_id", suffix = c("", ".sheet"))
  sample_paths <- load_sample_paths()
  if (!is.null(sample_paths) && nrow(sample_paths) > 0 && "sample_id" %in% names(sample_paths)) {
    meta <- dplyr::left_join(meta, sample_paths, by = "sample_id", suffix = c("", ".paths"))
  }
  sheet_cols <- names(meta)[grepl("\\.sheet$", names(meta))]
  for (sc in sheet_cols) {
    base <- sub("\\.sheet$", "", sc)
    if (!(base %in% names(meta))) {
      meta[[base]] <- meta[[sc]]
    } else {
      missing_base <- is.na(meta[[base]]) | trimws(as.character(meta[[base]])) == ""
      meta[[base]][missing_base] <- meta[[sc]][missing_base]
    }
  }
  path_cols <- names(meta)[grepl("\\.paths$", names(meta))]
  for (pc in path_cols) {
    base <- sub("\\.paths$", "", pc)
    if (!(base %in% names(meta))) {
      meta[[base]] <- meta[[pc]]
    } else {
      missing_base <- is.na(meta[[base]]) | trimws(as.character(meta[[base]])) == ""
      meta[[base]][missing_base] <- meta[[pc]][missing_base]
    }
  }
  meta[, setdiff(names(meta), c(sheet_cols, path_cols)), drop = FALSE]
}
