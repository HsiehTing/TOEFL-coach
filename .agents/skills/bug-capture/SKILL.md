---
name: bug-capture
description: Capture a reproducible, immutable bug record for a defect the learner discovers while normally using this TOEFL coach. Use after confirming the complete bug context and before investigating or fixing the reported normal-use defect; the capture CLI writes the linked project-roadmap record. Do not use for planned development, roadmap cleanup, implementation-time test failures, or feature-gap audits.
---

# Bug Capture

Use `tools/capture_bug_report.py` as the only creation path for a normal-use bug record. Do not begin a code fix, alter tracker data, or write a speculative diagnosis before the user context is complete and the roadmap record succeeds.

## Scope gate

Use this skill only when the learner encounters unexpected behavior while normally using the coach. Do not use it for planned feature work, a developer's implementation-time test failure, roadmap status cleanup, or an unsupported capability that intentionally fails closed. Record those items in the relevant development roadmap without creating a Bug Capture.

## Required intake

Collect only facts that are known:

1. Intended purpose or learner outcome, expected behavior, and observed behavior.
2. The operations immediately before the error, in order, plus the affected learner/system flow.
3. Timing or trigger, reproducibility, impact, and available evidence, when known.

If intended purpose, expected behavior, observed behavior, or at least one preceding operation is unknown, ask for the missing fact. Do not invent reproduction steps. Mark timing, impact, or flow as unspecified only when they are genuinely unavailable.

## Capture workflow

1. Turn the confirmed purpose, expected behavior, observed behavior, context, reproduction, impact, and evidence into the capture inputs. Do not alter product code or test behavior before the roadmap record exists.
2. Preserve user-provided logs, screenshots, command output, or relevant artifacts as explicit `--attach` inputs. Do not attach raw audio, credentials, or unrelated learner data.
3. Run `python3 tools/capture_bug_report.py --format json` from the repository root with `--title`, `--expected`, `--observed`, and one or more `--step` values. Include `--affected-flow` and `--timing` whenever known; read the receipt and stop if its validation is not passed.
4. Use both `--include-git-diff` and `--confirm-safe-git-diff` only when the uncommitted diff is necessary to reproduce the failure and contains no unrelated or sensitive content. The default snapshot already records branch, commit, and worktree status.
5. Confirm that `tracker/bug-reports/<BUG-ID>/report.yaml`, `snapshot.json`, `reproduction.md`, and `.ready` exist. Run `python3 tools/verify_bug_reports.py --format json` to confirm the artifact hash and the single roadmap link.
6. If capture reports a roadmap-write interruption after publishing the artifact, do not edit the ledger by hand. Run `python3 tools/recover_bug_reports.py`, then rerun `python3 tools/verify_bug_reports.py`.
7. Read the captured `reproduction.md` before investigating. Treat it as the source of truth; record later hypotheses separately and do not rewrite the captured facts.

## Boundaries

- Keep the full artifact under `tracker/bug-reports/`; roadmap entries contain only ID, status, summary, and a link.
- Do not overwrite a captured report or copy its full snapshot into the roadmap.
- Do not claim a fix is verified merely because it builds. Add regression coverage and run the relevant validation before reporting a resolution.
- The capture command creates `reported` records. After a fix, use `tools/resolve_bug_report.py` to append evidence; never edit `report.yaml`, `snapshot.json`, `reproduction.md`, or the ledger status by hand. `fixed_verified` requires a fix reference and validation command/result.

Read [the CLI contract](references/bug-capture-cli.md) only when a field, attachment, or privacy decision is unclear.
