# R/LAB Reliability Implementation Plan

> Execution: inline, following the already approved review. Project authorization and AGENTS.md override skill defaults for commits, extra approvals and workspace changes.

**Goal:** Deliver IMP-01 through IMP-08 from the improvement document.
**Architecture:** Extract the editor save queue and workspace backup implementation behind existing entry points. Keep business invariants in Python services and preserve Bridge v1.
**Tech Stack:** Native JavaScript, Python, SQLAlchemy, SQLite, pytest, node:test.
**Spec:** docs/IMPROVEMENT-2026-09-08.md

## Constraints

No production database access, schema changes, dependency installation, release build, commit or push. Preserve existing untracked design files. Additive Bridge v1 commands must be documented and tested.

## Steps

- [x] Add failing Python tests for finalized writes, file failure compensation, backup contents and project counts; add node:test delayed-save cases using the production editor code.
- [x] Implement a session-bound save queue; integrate navigation/save state; ensure adding a step preserves existing step fields.
- [x] Add record.finalize and record.revise with version checks and revision snapshots; block ordinary/bulk/AI writes to finalized content; expose explicit UI actions and history differences.
- [x] Validate file metadata before copy and compensate newly created files on failure; verify the copied content hash.
- [x] Add a backup service with database/workspace scopes, manifest hashes and external-file exclusions; wire the settings action and document limitations.
- [x] Copy desktop resources with the vendor license, update package paths and resource tests; improve text sizing without replacing page layout.
- [x] Add bounded AI conversation history and validate ownership before calling the provider; replace project relationship-length counts with SQL aggregates.
- [x] Run targeted regressions, JavaScript behavior/syntax tests, Python compile checks and task manifest verification; record evidence and remaining visual/release gates.

## Actual verification

User requested no further regression expansion. Existing added cases were retained; the final focused check covered workspace backup and finalized revision (2 passed), plus JavaScript/Python/PowerShell syntax and resource resolution. No full-suite run or installer build.
