# Task Board

| ID | Task | Owner | Status | Depends on | Human gate | Output |
|---|---|---|---|---|---|---|
| SETUP-001 | Complete project metadata and privacy review | Human owner | TODO | - | Yes | Approved project.yaml |
| INV-001 | Register existing research assets | Planner | TODO | SETUP-001 | Yes | inventory/assets.csv |
| ANALYSIS-001 | Define the first analysis task | Executor | TODO | INV-001 | Yes | tasks/ANALYSIS-001.yaml |

Allowed status values: `TODO`, `READY`, `IN_PROGRESS`, `REVIEW`, `BLOCKED`, `DONE`.
