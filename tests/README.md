Simple test recipes for this BRS. Keep these files in sync with your templates.

Files
- templates.txt: generated list of templates (ordered by dependencies), with optional CLI params.
- params.yaml: optional per-template params used when generating templates.txt.
- gen_templates_txt.py: script to generate templates.txt by scanning templates/*/template_config.yaml.
- smoke.sh: renders each template in templates.txt into a fresh project (no runs).

Running
1) Ensure BPM is available on PATH.
2) From the repo root (/Users/ckuo/github/UKA_GF_BRS), run:
   - python3 tests/gen_templates_txt.py && cat tests/templates.txt
   - bash tests/smoke.sh

Notes
- Smoke tests exercise Jinja rendering and file mappings only (no external tools).
- If a template needs params to render, add them under tests/params.yaml and re-run the generator.
