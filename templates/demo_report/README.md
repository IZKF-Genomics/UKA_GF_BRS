# demo_report

Generate a small demo report with example parameters and outputs.

## Usage
1) Render into a project:
   `bpm template render demo_report --dir /path/to/project --param sample_id=NA12878`
2) Run:
   `bpm template run demo_report --dir /path/to/project`

## Parameters
- `sample_id` (required, str): Example sample identifier.
- `threads` (int): Number of threads to report in the demo output.
- `trim` (bool): Whether trimming is enabled in the demo output.
- `cutoff` (float): Example cutoff value.
- `contact_email` (str): Optional contact email.

## Outputs
- `results.txt`: summary of run inputs and environment.
- `metrics.json`: machine-readable summary used by the publish resolver.
- `README.md`: rendered report summary in the output folder.

## Notes
- This template renders `README.md` from `README.md.j2` at render time.
