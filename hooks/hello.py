"""
Hook: hello
Stage: post_run
Purpose: Demonstrate how a hook can access the BPM context (`ctx`)
         and write a simple log file into the template folder.
"""

from pathlib import Path

def main(ctx):
    # Access current project and template metadata
    project_name = ctx.project.name
    template_id = ctx.template.id
    params = dict(ctx.params)  # all CLI/template parameters

    # Write a small file into the template folder
    out_file = Path(template_id) / "hello_hook.txt"
    out_file.write_text(
        f"Hello from hook!\n"
        f"Project: {project_name}\n"
        f"Template: {template_id}\n"
        f"Params: {params}\n"
    )

    print(f"[hook:hello] Wrote {out_file}")