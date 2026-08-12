# Bug Capture executable CLI playbook

Use this playbook from the repository root. `capture_bug_report.py` is the sole creation path; all checks below are required before handing work to a resolution workflow.

## 1. Input contract

| CLI field | Supply | Reject or ask when |
| --- | --- | --- |
| `--title` | A short observable failure, not a diagnosis | Blank, speculative, or only an error code |
| `--purpose` | Intended learner outcome | The intended outcome is unknown |
| `--expected` | Concrete correct behavior | Missing or merely says “it should work” |
| `--observed` | Concrete actual behavior | Missing or replaces facts with a suspected cause |
| `--step` (repeat) | Each immediately preceding operation, in order | No operation is known |
| `--affected-flow` | Named learner/system flow | Omit when unknown |
| `--timing` | Trigger, date/time, or occurrence window | Omit when unknown |
| `--reproducibility` | Frequency or conditions required to reproduce | Omit when unknown |
| `--impact` | Learner consequence or scope | Omit when unknown |
| `--attach` (repeat) | A safe, relevant evidence file | Raw audio, secret-like file/name, unsupported type, or over 10 MiB |

Do not pass a user’s absolute file path in the final report. The CLI intentionally records only the attachment name, stored relative path, MIME type, size, and checksum.

## 2. Command template

Run this command after replacing only the placeholders supported by known facts. Repeat `--step` and `--attach` rather than combining values.

```bash
python3 tools/capture_bug_report.py \
  --format json \
  --title "<observable failure>" \
  --purpose "<intended learner outcome>" \
  --expected "<expected behavior>" \
  --observed "<observed behavior>" \
  --step "<first preceding operation>" \
  --step "<next operation, if known>" \
  --affected-flow "<flow, if known>" \
  --timing "<trigger or time, if known>" \
  --reproducibility "<frequency, if known>" \
  --impact "<learner impact, if known>" \
  --attach "<safe evidence path, if any>"
```

Omit any optional argument whose fact is not known. Do not add `--include-git-diff` by default. If and only if a reviewed diff is needed and safe to retain, add both flags together:

```bash
--include-git-diff --confirm-safe-git-diff
```

`--include-git-diff` alone must fail; never work around that check.

## 3. Success contract

Parse the JSON receipt and require this shape:

```json
{
  "bug_id": "BUG-YYYYMMDD-NNN",
  "report_path": "tracker/bug-reports/BUG-YYYYMMDD-NNN",
  "ledger_path": "docs/superpowers/plans/2026-08-07-toefl-next-feature-roadmap.md",
  "attachment_count": 0,
  "privacy_flags": {"git_diff_retained": false},
  "report_digest": "sha256:…",
  "validation": {"passed": true, "problems": []}
}
```

The Bug ID is assigned by the CLI. Never predict, reuse, or manually choose it. The capture creates:

- `report.yaml`: immutable reported facts and attachment manifest;
- `snapshot.json`: capture time, runtime, branch, commit, worktree state, and an opt-in diff only when retained;
- `reproduction.md`: readable source-of-truth reproduction record;
- `attachments/`: copied evidence with SHA-256 checksums when supplied;
- `.ready`: digest marker for a complete initial artifact.

Immediately run:

```bash
python3 tools/verify_bug_reports.py --format json
```

Require exactly `{"passed": true, "problems": []}` semantically. Verification proves that each ready report has one roadmap link, its digest and schema version match, and no incomplete staging artifact remains.

## 4. Failure and recovery matrix

| Signal | Meaning | Required next action |
| --- | --- | --- |
| CLI rejects a required field or step | Capture packet is incomplete | Ask for/correct only that fact, then rerun capture |
| CLI rejects an attachment or diff flag | Evidence/retention violates policy | Remove or replace it; never bypass validation |
| Capture exits after artifact publication but says roadmap write was interrupted | A complete `.ready` artifact may lack its ledger row | Run `python3 tools/recover_bug_reports.py`, then verify |
| Verify returns `passed: false` | Artifact/roadmap integrity is not established | Report its exact `problems` and stop |
| Recovery reports no path and verify passes | Nothing was pending | Continue only to the normal stop condition |

Recovery links only complete `.ready` artifacts missing a ledger row. It never repairs a manually edited or incomplete artifact; no manual ledger or report edit is permitted.

## 5. Handoff contract

After a passed verification, report the Bug ID and the immutable reproduction path. Do not inspect implementation or formulate a root cause. A `bug-resolution` workflow can begin only after the user explicitly authorizes investigation or a fix.
