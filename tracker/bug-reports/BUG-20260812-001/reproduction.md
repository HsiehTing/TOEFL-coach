# BUG-20260812-001 — Revision follow-up repeats prior scored advice instead of advancing toward score 5

Status: `reported`
Reported at: `2026-08-12T01:18:06+00:00`
Intended purpose: Give the learner novel, high-value naturalness and precision feedback after a Writing revision so a stable score-4 Email can move closer to score 5.
Affected flow: Writing Email revision completion to naturalness and precision follow-up
Timing / trigger: 2026-08-12, after the latest Email revision assessment
Reproducibility: Observed once in normal learner testing; broader reproduction has not yet been confirmed.
Impact: The learner receives duplicate, lower-value advice and cannot rely on the follow-up to identify the refinements needed to move a stable score-4 response toward score 5.

## Expected behavior

The follow-up should appear after the revision assessment and use only previously unaddressed excerpts or issues. It should not repeat the committee-name advice already given in the scored assessment, and it should offer a precise next-step improvement toward score 5.

## Observed behavior

For revision W-EM-20260811-001-R3, the requested follow-up repeated `a member of the campus and library committee`, although that exact issue was already listed in the scored Evidence section. The follow-up therefore did not provide a new, high-value improvement toward score 5.

## Steps immediately before the failure

1. Submit the original Writing Email about library construction noise.
2. Submit revisions through W-EM-20260811-001-R3 and receive its scored assessment.
3. Request the naturalness and precision follow-up for the latest revision.
4. Compare the follow-up excerpt with the revision feedback Evidence section.

## Captured evidence

- `snapshot.json` records repository revision, worktree state, runtime, and capture time.
- `attachments/` contains user-supplied logs, screenshots, or artifacts with SHA-256 checksums.
- The roadmap ledger links this Bug ID; fix work must consult this artifact before changing behavior.
