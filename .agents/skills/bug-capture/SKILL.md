---
name: bug-capture
description: Capture a reproducible, immutable bug record for a defect the learner discovers while normally using this TOEFL coach. Use after confirming the complete bug context and before investigating or fixing the reported normal-use defect; the capture CLI writes the linked project-roadmap record. Do not use for planned development, roadmap cleanup, implementation-time test failures, or feature-gap audits.
---

# Bug Capture

Create a normal-use bug record only through `tools/capture_bug_report.py`. Before executing it, read [the executable CLI playbook](references/bug-capture-cli.md) in full. It defines the intake-to-argument mapping, receipt checks, recovery path, and stop conditions.

## 1. Classify before collecting or changing anything

Capture only unexpected behavior encountered while using the coach. Treat a user-declared learning test environment as normal use; do not reclassify it as an implementation-time failure merely because the learner is testing a newly developed feature. Do not begin a code fix before a successful capture.

Do not use it for planned feature work, a developer-only test failure, roadmap cleanup, or an intended fail-closed capability gap. Do **not** create a Bug ID for those cases; record them in the relevant development roadmap instead. Do not investigate, diagnose, alter code, alter tracker data, or change a test before a successful capture.

## 2. Build a complete capture packet

Extract facts without filling gaps. The packet must contain:

| Capture field | Required content | CLI argument |
| --- | --- | --- |
| Title | Short, observable failure label | `--title` |
| Purpose | The intended purpose: learner outcome the flow is meant to provide | `--purpose` |
| Expected | What should happen | `--expected` |
| Observed | What actually happened | `--observed` |
| Steps | One or more operations immediately before the failure, in order | one `--step` per operation |
| Context | Affected flow, timing/trigger, reproducibility, impact when known | optional context arguments |
| Evidence | Safe, relevant user-provided artifacts only | repeatable `--attach` |

If purpose, expected behavior, observed behavior, or every preceding operation is unknown, ask only for the missing fact and do not run the CLI. Use `unspecified` only for genuinely unavailable optional context, never for a required field. Preserve learner wording in evidence and distinguish facts from later hypotheses.

## 3. Preflight the evidence and retention decision

1. Attach only relevant `.txt`, `.log`, `.md`, `.json`, `.yaml`, `.yml`, `.csv`, `.png`, `.jpg`, `.jpeg`, or `.webp` files that are at most 10 MiB.
2. Exclude raw audio, credentials, keys, `.env` files, secrets, tokens, passwords, and unrelated learner records. The CLI copies approved attachments into the immutable report and stores their checksums.
3. Default to the repository snapshot without a diff. Add **both** `--include-git-diff` and `--confirm-safe-git-diff` only after confirming that the current staged/unstaged diff is necessary for reproduction and contains no sensitive or unrelated content.

## 4. Capture and Read the Receipt

Run the capture command from the repository root with `--format json`, using the exact template in the playbook. Treat its JSON output as the machine receipt, not merely terminal text.

Continue only if all of these are true:

1. The command exits successfully.
2. The receipt contains a `bug_id`, a `report_path`, and the expected `ledger_path`.
3. `validation.passed` is `true` and `validation.problems` is empty.
4. The reported `attachment_count` and `privacy_flags.git_diff_retained` match the requested inputs.

Then confirm the report directory contains `report.yaml`, `snapshot.json`, `reproduction.md`, and `.ready`; run `python3 tools/verify_bug_reports.py --format json`; require its `passed` value to be `true` and `problems` to be empty. Read the captured `reproduction.md` before any later investigation; it is the immutable source of truth.

## 5. Handle failure without corrupting the record

- If intake or attachment validation fails before publication, correct only the rejected capture input and rerun; do not create files by hand.
- If the capture fails after publishing the artifact because its roadmap link was interrupted, run `python3 tools/recover_bug_reports.py`, then rerun `python3 tools/verify_bug_reports.py --format json`. Do not edit the ledger or artifact manually.
- If verification still fails, report the exact JSON problems and stop. Do not begin diagnosis or a fix.

## 6. Report and stop

Report the Bug ID, immutable report path, roadmap link confirmation, retained-evidence summary, and verification result. Do not claim a cause or a fix. Stop after capture and verification; use `bug-resolution` only if the user explicitly authorizes investigation or a fix.

## Boundaries

- Keep the full artifact under `tracker/bug-reports/`; the roadmap stores only ID, status, summary, and link.
- Never overwrite `report.yaml`, `snapshot.json`, `reproduction.md`, `.ready`, attachments, or the roadmap ledger status by hand.
- The capture skill owns only `reported` records. `bug-resolution` owns diagnosis, code changes, `tools/resolve_bug_report.py`, and all closure validation.
