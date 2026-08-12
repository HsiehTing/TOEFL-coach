---
name: bug-resolution
description: Investigate, fix, validate, and append a resolution for a previously captured TOEFL coach bug. Use when the user provides a BUG-ID or asks to diagnose, fix, or resolve an existing captured defect; require an intact bug report and explicit authority before modifying code, tracker data, commits, or remotes.
---

# Bug Resolution

Use this skill only for an existing captured BUG. Before taking action, read [the executable resolution playbook](references/bug-resolution-cli.md) in full. It defines authority gates, outcome selection, command templates, verification, and stop conditions.

## 1. Separate authority from diagnosis

Classify the user’s request before modifying anything:

| User authority | Permitted work | Must not do |
| --- | --- | --- |
| Review / diagnose | Verify, read the immutable record, reproduce safely, inspect code, report hypotheses | Edit code or tracker records; commit; push |
| Fix | Diagnose and make scoped code/test changes | Create a resolution record, commit, or push unless also authorized |
| Resolve / close | Append an immutable resolution and update its derived roadmap status | Make code changes, commit, or push unless also authorized |
| Commit / push | Perform only the explicitly requested version-control action after validation | Infer broader remote or tracker authority |

Do not treat a request to diagnose as authority to fix. Do not treat a request to fix as authority to commit, push, or write an immutable closure record. Ask for the missing explicit authority when an action would cross one of these boundaries.

## 2. Verify the captured source of truth

1. Require a valid `BUG-YYYYMMDD-NNN` identifier.
2. Confirm `tracker/bug-reports/<BUG-ID>/report.yaml`, `snapshot.json`, `reproduction.md`, and `.ready` exist.
3. Run `python3 tools/verify_bug_reports.py --format json`. Continue only when `passed` is `true` and `problems` is empty.
4. Read `reproduction.md` before diagnosis. Preserve its reported facts; call later conclusions hypotheses until supported by evidence.
5. If the artifact is incomplete or missing a roadmap link, stop the resolution workflow. Use `bug-capture` recovery only for an interrupted initial capture; never repair report files or the roadmap manually.

## 3. Diagnose and validate the smallest scoped change

1. Reproduce the recorded behavior using its exact steps where safe and within the evidence scope. Do not expose raw audio, credentials, or unrelated learner material.
2. Form a diagnosis that explains the observed behavior and identifies the smallest responsible behavior, not merely a symptom.
3. If a fix is authorized, change only the implementation and tests necessary for the captured defect. Never edit `report.yaml`, `snapshot.json`, `reproduction.md`, `.ready`, attachments, or the roadmap ledger by hand.
4. Add or update regression coverage that fails for the reported behavior and passes for the intended behavior. Run the focused regression test and all relevant tracker/report validation.
5. Record the exact validation command and its result verbatim enough to reproduce the assertion. A successful build alone never proves `fixed_verified`.

## 4. Choose and append the correct outcome

Use `tools/resolve_bug_report.py` as the only closure path. It appends `resolutions/RES-NNN.yaml` and derives the roadmap status. Choose exactly one outcome using the decision table in the playbook.

- Use `fixed_verified` only after an authorized fix, passed regression and system validation, and a durable commit or PR reference.
- Use `duplicate`, `cannot_reproduce`, or `wont_fix` only with explicit authority to close the Bug ID and concrete evidence recorded as the diagnosis and validation result.
- If a fix is validated locally but there is no authorized commit/PR reference, report the state and stop; leave the bug `reported` rather than misusing `fixed_verified`.

After appending, run `python3 tools/verify_bug_reports.py --format json` and require a passed JSON result. Run `python3 tools/rebuild_bug_report_index.py` only when rebuilding the derived operational index is authorized or in scope; report its output path without copying private evidence into the response.

## 5. Report the precise end state

Report the BUG-ID, whether the initial artifact remained intact, diagnosis or reason for non-closure, changed files when applicable, exact validation evidence, appended `RES-NNN` path when one was authorized, derived index status when rebuilt, and commit/push status. State any remaining limitation. Stop after the authorized endpoint.

## Boundaries

- Never overwrite an immutable capture or a prior resolution; each closure is append-only. Do not edit `report.yaml`, `snapshot.json`, `reproduction.md`, `.ready`, attachments, or the roadmap ledger by hand.
- Do not claim `fixed_verified` without regression coverage, relevant validation, and a fix reference.
- Do not create a new bug record here; hand incomplete capture context to `bug-capture`.
- Do not write a closure merely to reflect an uncommitted local change when the user has not authorized a durable fix reference.
