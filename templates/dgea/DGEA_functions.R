`%||%` <- function(x, y) if (is.null(x) || (is.character(x) && identical(x, ""))) y else x
null_if_na <- function(x) {
  if (is.null(x)) {
    return(NULL)
  }
  if (length(x) == 1 && is.na(x)) {
    return(NULL)
  }
  x
}

####################################################################
# Render DGEA reports (no hidden RData; pass params explicitly)
####################################################################

render_DGEA_report <- function(config) {
  stopifnot(!is.null(config$base_group), !is.null(config$target_group))

  filetag <- if (!is.null(config$additional_tag) &&
                  nzchar(config$additional_tag)) {
    paste0(config$target_group, "_vs_", config$base_group, "_", config$additional_tag)
  } else {
    paste0(config$target_group, "_vs_", config$base_group)
  }

  csv_path <- file.path(getwd(), paste0("DGEA_", filetag, "_samplesheet.csv"))
  config$samplesheet <- config$samplesheet[config$samplesheet$group %in% c(config$base_group, config$target_group),]
  utils::write.csv(config$samplesheet, csv_path, row.names = FALSE)
      
  execute_params <- list(
    salmon_dir = config$salmon_dir,
    samplesheet_path = csv_path,
    organism = config$organism,
    ercc = isTRUE(config$ercc),
    application = config$application,
    name = config$name %||% "project",
    authors = config$authors %||% "PROJECT_AUTHORS",
    base_group = config$base_group,
    target_group = config$target_group,
    additional_tag = null_if_na(config$additional_tag),
    design_formula = config$design_formula,
    paired = isTRUE(config$paired),
    go = isTRUE(config$go),
    gsea = isTRUE(config$gsea),
    cutoff_adj_p = config$cutoff_adj_p %||% 0.05,
    cutoff_log2fc = config$cutoff_log2fc %||% 1,
    pvalueCutoff_GO = config$pvalueCutoff_GO %||% 0.05,
    pvalueCutoff_GSEA = config$pvalueCutoff_GSEA %||% 0.05,
    highlighted_genes = null_if_na(config$highlighted_genes),
    tx2gene_file = config$tx2gene_file %||% file.path(config$salmon_dir, "tx2gene.tsv"),
    filetag = filetag
  )

  output_file <- paste0("DGEA_", filetag, ".html")
  message("Rendering DGEA report to: ", normalizePath(file.path(getwd(), output_file), winslash = "/", mustWork = FALSE))
  quarto::quarto_render(
    input = "DGEA_template.qmd",
    output_file = output_file,
    execute_params = execute_params,
    quiet = FALSE
  )
  invisible(output_file)
}

render_DGEA_all_sample <- function(config) {
  csv_path <- file.path(getwd(), paste0("DGEA_all_samplesheet.csv"))
  utils::write.csv(config$samplesheet, csv_path, row.names = FALSE)

  execute_params <- list(
    salmon_dir = config$salmon_dir,
    samplesheet_path = csv_path,
    organism = config$organism,
    ercc = isTRUE(config$ercc),
    application = config$application,
    name = config$name %||% "project",
    authors = config$authors %||% "PROJECT_AUTHORS"
  )

  output_file <- "DGEA_all_samples.html"
  message("Rendering DGEA all-samples report to: ", normalizePath(file.path(getwd(), output_file), winslash = "/", mustWork = FALSE))
  quarto::quarto_render(
    input = "DGEA_all_samples.qmd",
    output_file = output_file,
    execute_params = execute_params,
    quiet = FALSE
  )
  invisible(output_file)
}

####################################################################
# Optional: Simple comparison report (parameterised, no temp files)
####################################################################

render_simple_report <- function(config) {
  stopifnot(!is.null(config$sample1), !is.null(config$sample2))

  filetag <- paste0(config$sample2, "_vs_", config$sample1)
  execute_params <- list(
    salmon_dir = config$salmon_dir,
    samplesheet = config$samplesheet,
    organism = config$organism,
    ercc = isTRUE(config$ercc),
    application = config$application,
    name = config$name %||% "project",
    authors = config$authors %||% "PROJECT_AUTHORS",
    sample1 = config$sample1,
    sample2 = config$sample2,
    filetag = filetag
  )

  output_file <- paste0("SimpleComparison_", filetag, ".html")
  message("Rendering simple comparison report to: ", normalizePath(file.path(getwd(), output_file), winslash = "/", mustWork = FALSE))
  quarto::quarto_render(
    input = "SimpleComparison_template.qmd",
    output_file = output_file,
    execute_params = execute_params,
    quiet = TRUE
  )
  invisible(output_file)
}

####################################################################
# Utility functions for integrity checks
####################################################################

check_missing_dirs <- function(paths) {
  if (!is.character(paths)) {
    stop("`paths` must be a character vector.")
  }

  missing_dirs <- paths[!vapply(paths, dir.exists, logical(1))]

  if (length(missing_dirs) > 0) {
    message("⚠️ The following directories are missing:")
    for (d in missing_dirs) {
      message("  - ", d)
    }
  } else {
    message("✅ All directories exist.")
  }

  invisible(missing_dirs)
}
