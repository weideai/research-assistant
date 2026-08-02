# Module 1: Research AI Workbench

This implementation turns the five lessons in module 1 into a reusable operating
system for research projects. It complements the Research Assistant web app: the
app manages projects, experiments, records, attachments, knowledge bases, AI
proposals, exports, and PPT reports; the filesystem workspace manages code, large
data, analysis provenance, mechanism evidence, and independent review.

## Create a Workspace

From the repository root:

```powershell
.\scripts\new_research_workspace.ps1 `
  -Destination "..\my-research-project" `
  -ProjectTitle "My Research Project"

.\scripts\validate_research_workspace.ps1 `
  -Workspace "..\my-research-project"
```

The validator intentionally warns that privacy approval and project ownership are
unfinished. These warnings disappear only after the responsible person completes
the governance records.

## Lesson Mapping

### Lesson 1: Workbench Deployment

- `project.yaml` stores project identity, governance, reproducibility, and status.
- `AGENTS.md`, `CLAUDE.md`, and `CODEX_REVIEWER.md` define role boundaries.
- `TASK_BOARD.md`, task cards, and `CHANGELOG.md` provide visible project state.
- `governance/privacy-checklist.md` blocks unsafe external transfer by default.

### Lesson 2: Mechanism Figures

- `mechanism/elements.csv` defines biological entities and context.
- `mechanism/relations.csv` defines arrows, direction, evidence, and visual style.
- `mechanism/evidence-check.csv` maps every arrow to quoted source evidence.
- Generate Mermaid/SVG only after these tables pass human review.

### Lesson 3: Presentations

- Register source figures and tables in `inventory/assets.csv`.
- Build the slide argument in `presentations/storyboard.csv` before creating PPTX.
- Use the web app's presentation report to generate editable evidence-based PPTX.
- Review every slide title as a scientific claim, not merely as design copy.

### Lesson 4: File and Knowledge Management

- Keep original data immutable and separate it from derived data.
- Register files, identifiers, ownership, versions, hashes, licenses, and tasks.
- Use the app's private knowledge bases for local literature retrieval with source
  markers; use the workspace for source-of-truth files and analysis code.
- Export `.ralab` packages for structured application data and archive large files
  separately using the asset manifest and checksums.

### Lesson 5: Integrated Analysis and HPC

- Every formal analysis starts from a task card and ends with a run manifest.
- Save stdout/stderr and package locks under `provenance/`.
- Use `server/slurm-job.sh` as the starting point for approved HPC jobs.
- Place reviewer findings in `review/`; only approved deliverables enter
  `final-package/`.

## Recommended First Exercise

Use a public, small bulk-expression dataset. Register the paper and accession,
write one task card, audit the grouping, run one versioned script, record one run
manifest, generate one figure, and ask a separate reviewer to verify the comparison
direction and claim. This tests the complete workflow without clinical privacy risk
or expensive single-cell computation.

