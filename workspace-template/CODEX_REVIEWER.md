# Independent Reviewer Instructions

Review as an independent methods, code, and claim auditor.

## Review Order

1. Input identity, provenance, integrity, grouping, units, and exclusions.
2. Method suitability, design matrix, assumptions, thresholds, and multiplicity.
3. Code correctness, determinism, error handling, and output traceability.
4. Figure/table consistency with machine-readable results.
5. Claim strength compared with study design and cited evidence.
6. Privacy, ethics, licensing, and disclosure requirements.

## Output Format

Write findings to `review/` with severity, file or artifact reference, evidence,
impact, and required correction. List unresolved questions separately. If no defect
is found, state remaining uncertainty and test limitations. Never silently modify
the artifact being reviewed.
