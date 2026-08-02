# {{PROJECT_TITLE}}

Created: {{CREATED_DATE}}

This workspace implements a three-layer research workflow:

1. Source layer: literature, metadata, protocols, and immutable raw data.
2. Execution layer: task cards, scripts, notebooks, logs, results, and figures.
3. Review layer: independent review, claim checks, privacy checks, and approvals.

## Start Here

1. Complete `project.yaml` and `governance/privacy-checklist.md`.
2. Register existing material in `inventory/assets.csv`.
3. Copy `tasks/TASK-TEMPLATE.yaml` for the first task and define acceptance criteria.
4. Run analysis only from versioned scripts; never edit `data/raw/` in place.
5. Copy `provenance/RUN-TEMPLATE.yaml` for every formal run.
6. Place reviewer findings in `review/`; do not silently overwrite reviewed outputs.
7. Record approved deliverables in `CHANGELOG.md` and `final-package/`.

## Directory Contract

```text
literature/       Search logs, references, notes, and evidence matrices
data/raw/         Immutable source data; normally excluded from Git
data/metadata/    Sample sheets, data dictionaries, and grouping decisions
data/interim/     Re-creatable intermediate data
data/processed/   Analysis-ready, re-creatable data
tasks/            One YAML task card per unit of work
scripts/          Versioned analysis and export scripts
notebooks/        Exploratory work; formal results must move into scripts
results/          Machine-readable result tables
figures/          Generated and manually edited figures
mechanism/        Mechanism elements, relations, and evidence review
presentations/    Slide storyboard, speaker notes, and PPTX files
provenance/       Run manifests, logs, environment and checksums
review/           Independent review reports and response records
server/           HPC/Slurm templates and remote execution notes
final-package/    Human-approved delivery package only
```

## Human Gates

Human approval is required before external data transfer, analysis-plan changes,
clinical interpretation, causal claims, and final submission. AI output is a draft
or review aid, not evidence by itself.
