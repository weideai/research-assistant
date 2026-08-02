# Agent Rules

## Non-negotiable Rules

- Never fabricate citations, identifiers, sample sizes, measurements, or results.
- Treat `data/raw/` as immutable. Derive new files under `interim/` or `processed/`.
- Do not send identifiable, sensitive, restricted, or unpublished data externally
  unless the project owner has explicitly approved the destination and scope.
- Separate observed results, external evidence, interpretation, and speculation.
- Preserve commands, parameters, software versions, random seeds, and logs.
- Stop and request human review when grouping, units, endpoints, consent, or data
  provenance is ambiguous.

## Work Protocol

1. Read `project.yaml`, the relevant task card, and applicable governance files.
2. Audit declared inputs before analysis.
3. State the plan and expected outputs.
4. Work only inside the task's allowed paths.
5. Create a run record from `provenance/RUN-TEMPLATE.yaml`.
6. Validate outputs against the task acceptance criteria.
7. Submit results for independent review before moving them to `final-package/`.

## Role Boundaries

- Planner: scopes tasks and assembles evidence; does not approve its own claims.
- Executor: writes and runs code; does not silently redefine the research question.
- Reviewer: reports defects and claim limits; does not overwrite executor artifacts.
- Human owner: approves sensitive transfers, methods, interpretations, and release.
