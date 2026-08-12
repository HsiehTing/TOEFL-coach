# BUG-20260812-002 — Completed writing revision skips mandatory actionable follow-up

Status: `reported`
Reported at: `2026-08-12T05:48:52+00:00`
Intended purpose: After the learner completes the assigned writing revisions, provide a required naturalness-and-precision follow-up that helps move a stable response toward the next score level.
Affected flow: TOEFL Writing Academic Discussion revision completion and Naturalness and precision follow-up gate
Timing / trigger: Immediately after a revision is assessed as fully resolving all assigned priorities on 2026-08-12
Reproducibility: Observed in the supplied end-to-end test when all revision targets were marked resolved
Impact: The learner loses the required final refinement step and may be advanced to transfer before receiving naturalness and precision coaching.

## Expected behavior

When every preceding revision target is complete, the writing-coach flow must enter the follow-up stage and provide actionable naturalness or precision feedback; when any preceding revision target remains incomplete, the flow must stop before follow-up and continue the scored revision cycle.

## Observed behavior

After all three assigned revision targets were marked resolved, the feedback stated 'No naturalness or precision issue to flag.' and moved directly to a transfer suggestion, although genuine naturalness and precision issues remained; the learner had to request the missing follow-up.

## Steps immediately before the failure

1. Submit a complete Academic Discussion response and receive first-round feedback with three revision priorities.
2. Submit the first revision and receive a second rewrite assignment for the remaining language-control targets.
3. Submit the second revision; the assessment marks all three targets resolved with a 100% target-resolution rate.
4. Observe that the Naturalness and precision follow-up contains no actionable follow-up and proceeds to a transfer suggestion.

## Captured evidence

- `snapshot.json` records repository revision, worktree state, runtime, and capture time.
- `attachments/` contains user-supplied logs, screenshots, or artifacts with SHA-256 checksums.
- The roadmap ledger links this Bug ID; fix work must consult this artifact before changing behavior.
