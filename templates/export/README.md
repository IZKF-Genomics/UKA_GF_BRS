# export

Build and submit an export engine job spec from a mapping table and project.yaml
state.

## Usage
1) Render into a project (run from the project directory):
   `bpm template render export`
2) Inspect `export_job_spec.json` and confirm fields/paths.
3) Submit to the export engine:
   `bpm template run export --dir /path/to/project`
4) Check `project.yaml` for `templates[].published.export_job_id`.

## Parameters
- `export_engine_api_url` (str): Base URL for the export engine API (no trailing `/export`).
- `export_engine_backends` (str): Comma-separated backends for the job spec.
- `export_expiry_days` (int): Expiry days for the job spec.

## Outputs
- `export_job_spec.json`: JSON payload sent to the export engine.

## Mapping Table
The mapping table lives at `export_mapping.table.yaml`. Each entry becomes one
export spec entry. Report links are emitted into `export_list[].report_links`.

### Required Keys
```
template_id: <template id>
dest: <relative destination path>
```

### Source Keys (pick one)
```
src: <relative or absolute source path>        # default: {template_root}
src_project_key: <path in project.yaml>
src_published_key: <key under templates[].published>  # legacy shortcut
```
Precedence: `src_project_key` -> `src_published_key` -> `src`.

### Report Links
```
report_links:
  - path: <relative path in export dest>       # required; supports glob patterns
    src_project_key: <path in project.yaml>    # optional; resolves to a source path
    section: raw|processed|analysis|reports|general[/subsection...]
    description: <report link description>
    link_name: <report link display name>
```

### Optional Keys
```
mode: symlink|copy|...                          # default: symlink
project: <override project name>
host: <override host>
```

### Placeholders
- `{template_id}`: the template id from the mapping entry.
- `{template_root}`: the resolved template folder path in the project.

### src_project_key Path Syntax
`src_project_key` points into `project.yaml` using dot + selector syntax.

Examples:
- `project_name`
- `authors[0].name`
- `templates[id=nfcore_rnaseq].params.output_dir`
- `templates[id=demux_bclconvert].published.FASTQ_dir`

The resolved value must be a string path. If it includes a host prefix
(e.g. `host:/abs/path`), the host is preserved.

### Behavior Notes
- Only entries whose `template_id` exists in `project.yaml` are processed.
- Missing sources are skipped silently.
- `src` defaults to `{template_root}` when omitted.
- Report links are validated against the source path (not the export dest).
- Report links can use src_project_key; resolved absolute paths are made relative
  to the export source when possible.
- src_project_key values may include a host prefix (e.g., nextgen:/path); the
  host prefix is stripped before resolving a relative path.
- For remote sources (host != project host), report links are emitted as-is
  without local existence checks; glob patterns are ignored.
- Report links are emitted only for local sources (host == project host).
- Glob patterns expand to one link per matched file or folder.
- If `link_name` is omitted, it defaults to the basename with underscores
  replaced by spaces.
- Empty glob matches are ignored.

## Example Mapping
```
mappings:
  - template_id: nfcore_rnaseq
    dest: "2_Processed_data/nfcore_rnaseq"
    report_links:
      - path: "results*/multiqc/star_salmon/multiqc_report.html"
        section: processed
        description: "MultiQC report of nfcore_rnaseq"

  - template_id: demux_bclconvert
    src_project_key: "templates[id=demux_bclconvert].published.multiqc_report"
    src: demux_bclconvert/multiqc/multiqc_report.html
    dest: "1_Raw_data/demultiplexing_multiqc_report.html"
    report_links:
      - path: "."
        section: raw
        description: "MultiQC report"
```

## Notes
- `export_job_spec.json` is created by the post-render hook.
- Authors are taken from `project.yaml` and formatted as `Name, Affiliation`.
- `src` values that are relative are resolved against the project root.
