#!/usr/bin/env Rscript
suppressPackageStartupMessages({
  source("common.R")
})

cfg <- load_config("config/project.toml")
ensure_dirs(".")
sync_samples_from_inputs(
  cfg,
  output_file = "config/samples.csv",
  paths_output_file = "config/samples_paths.csv",
  groups_output_file = "config/group_levels.csv",
  include_existing_columns = TRUE
)
