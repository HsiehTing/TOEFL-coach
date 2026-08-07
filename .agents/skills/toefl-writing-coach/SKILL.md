---
name: toefl-writing-coach
description: Use when the learner provides a TOEFL 2026 Email or Academic Discussion prompt, writing response, revision, writing score request, recurring-error question, or writing progress review.
---

# TOEFL Writing Coach

## Core rule

Evaluate against the recorded ETS version, preserve evidence, and make the learner revise before showing a complete model.

## Intake

1. Read `standards/ets-2026/manifest.yaml` and `score-policy.md`.
2. Classify the input as `formal_original`, `revision`, `targeted_drill`, or `discussion_only`.
3. Treat a complete prompt plus complete answer as `formal_original` unless the learner says not to record it.
4. For a revision, require and preserve the parent attempt ID.
5. Record timing and assistance as unknown when not supplied; never infer them.

After feedback is accepted, register the immutable attempt through `tools/register_writing_attempt.py`; do not write tracker rows by hand.

## Route

- Email: read `references/email-feedback.md`.
- Academic Discussion: read `references/discussion-feedback.md`.
- For counted errors in either route: read `references/writing-error-taxonomy.md`.
- Do not load the other task route.

## First-round output

Give these parts in order:

1. Attempt conditions and result label.
2. Simulated 0–5 task score, confidence, and one-sentence verdict.
3. Why this level.
4. Why not the next level.
5. Evidence table with exact excerpts and must-fix, should-fix, or polish.
6. 最多三個 priorities.
7. A bounded rewrite task.

第一輪不提供完整範文。Do not convert the task result to a Writing section band.

## Revision output

Compare only against the assigned priorities. Report resolved, partly resolved, unresolved, and newly introduced issues; calculate target-resolution rate. A revision never increases the formal-attempt count. Provide a high-scoring model only after the learner has attempted the revision.

## Recurrence and progress output

For a recurrence or progress request, classify each counted code from ordered `formal_original` records with the deterministic tracker status rules. Explicitly output the resulting `historical_status`; revisions and targeted drills do not change it.
For Discussion, also read `standards/ets-2026/writing-skill-families.yaml` when available and show derived family signals without replacing atomic codes. After two unresolved revision rounds, recommend a bounded targeted drill and a new-prompt transfer check.

## Persist

Write immutable attempt and event inputs, run `tools/register_writing_attempt.py`, rebuild reports, then run `tools/validate_tracker.py`. Report the attempt ID and any common or task-specific three-practice report that was generated.
