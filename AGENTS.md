# AGENTS.md

<INSTRUCTIONS>
## Scope
- This file applies to all work under `/data/shared/repos/UKA_GF_BRS/`, including templates, hooks, resolvers, workflows, and supporting scripts.

## Core principles
- Integrity first: never fabricate facts, file contents, command output, or test results. If you did not verify something, say so and suggest how to verify it.
- Be explicit about uncertainty and assumptions. Ask questions when requirements or conventions are unclear.
- Preserve existing behavior unless a change is requested. Avoid silent behavior changes.
- Keep implementations minimal, focused, and consistent with existing BPM/BRS patterns.

## BPM/BRS implementation clarity
- Explain how the BPM and BRS pieces fit together for any change: inputs, outputs, data flow, and where the change is applied.
- Use precise, consistent terminology for template, hook, resolver, and workflow responsibilities.
- When adding or editing templates, include a short rationale for parameters and defaults.
- When editing hooks/resolvers, describe how they are invoked and how errors are handled.

## Repo conventions
- Prefer `rg` for searching; use targeted reads rather than bulk loading.
- Default to ASCII when editing files; introduce non-ASCII only if the file already uses it.
- Use `apply_patch` for single-file edits when practical.
- Avoid destructive commands unless explicitly requested.

## Documentation
- Always update `/data/shared/repos/UKA_GF_BRS/readme.md` when adding a new template or workflow, and when making changes that affect existing templates or workflows.

## Quality bar
- Keep changes small and reviewable.
- Call out edge cases and integration risks.
- Suggest tests or validation steps when relevant.
</INSTRUCTIONS>
