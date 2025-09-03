"""
Resolver: get_project_template_path
Purpose: Always return the template's output folder as a hostname-aware path.
"""

def main(ctx) -> str:
    # Get project path and template id
    project_path = ctx.project.project_path   # e.g. /mnt/nextgen/projects/250901_Demo_UKA
    tpl_id = ctx.template.id                  # e.g. hello
    # Join them in a hostname-aware form
    return f"{ctx.hostname()}:{project_path}/{tpl_id}"