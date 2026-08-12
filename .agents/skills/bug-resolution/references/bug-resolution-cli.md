# Bug Resolution executable CLI playbook

Run this playbook from the repository root after the authority and captured-artifact gates in `SKILL.md` pass. The resolution command is append-only; it never alters the initial capture.

## 1. Preflight contract

| Check | Required evidence | Stop condition |
| --- | --- | --- |
| Bug identity | A user-supplied `BUG-YYYYMMDD-NNN` | Missing or malformed Bug ID |
| Capture integrity | `report.yaml`, `snapshot.json`, `reproduction.md`, `.ready` and `verify_bug_reports --format json` with `passed: true` | Any missing artifact or verification problem |
| Closure authority | Explicit permission to append resolution evidence and change the derived roadmap status | User requested only diagnosis or a code fix |
| Fix authority | Explicit permission to modify the scoped implementation/tests | Fix is needed but not authorized |
| Commit/push authority | Explicit permission for the requested version-control action | A durable reference is needed but commit/PR is not authorized |

Read the immutable `reproduction.md` before inspecting behavior. Keep its expected/observed text and recorded steps unchanged; the diagnosis is new, append-only evidence.

## 2. Outcome selection

| Outcome | Use only when | Required evidence |
| --- | --- | --- |
| `fixed_verified` | Authorized scoped fix is complete and verifiably resolves the captured behavior | Concise cause, durable commit or PR `--fix-reference`, focused regression, relevant system validation |
| `duplicate` | Another captured Bug ID already represents the same defect | Other Bug ID and comparison evidence in `--diagnosis`; verification command/result |
| `cannot_reproduce` | Recorded steps were attempted with the documented environment and did not reproduce | Exact attempts/environment in `--diagnosis`; attempted command/result |
| `wont_fix` | Authorized product decision declines the behavior change | Decision rationale in `--diagnosis`; review/decision evidence in command/result |

`fixed_verified` requires `--fix-reference`; the other outcomes must omit it unless there is a useful, authorized reference. Never close a report solely because the symptom was not observed once.

## 3. Command templates

First verify without changing data:

```bash
python3 tools/verify_bug_reports.py --format json
```

For a verified fix, run only after an authorized durable reference exists:

```bash
python3 tools/resolve_bug_report.py \
  --bug-id "BUG-YYYYMMDD-NNN" \
  --outcome fixed_verified \
  --diagnosis "<evidence-based root cause>" \
  --fix-reference "<commit SHA or PR reference>" \
  --validation-command "<exact focused and relevant validation command>" \
  --validation-result "passed: <concise result>"
```

For an authorized non-fix closure, choose one supported outcome and do not invent a fix reference:

```bash
python3 tools/resolve_bug_report.py \
  --bug-id "BUG-YYYYMMDD-NNN" \
  --outcome "<duplicate|cannot_reproduce|wont_fix>" \
  --diagnosis "<concrete supporting evidence>" \
  --validation-command "<exact reproduction, comparison, or decision check>" \
  --validation-result "<actual result>"
```

The command prints the new immutable path, for example `tracker/bug-reports/BUG-YYYYMMDD-NNN/resolutions/RES-001.yaml`. It writes a new resolution rather than replacing an earlier one and updates the roadmap status to the latest resolution outcome.

## 4. Post-write verification and derived index

Immediately run:

```bash
python3 tools/verify_bug_reports.py --format json
```

Require semantic equality to `{"passed": true, "problems": []}`. This confirms the initial digest, resolution schema, Bug ID linkage, outcome, validation fields, and roadmap status all agree.

If a privacy-safe operations view is authorized or required, run:

```bash
python3 tools/rebuild_bug_report_index.py
```

It writes `tracker/bug-reports/index.yaml`. The index contains only operational fields such as Bug ID, status, affected flow, reproducibility, and completeness; it must not duplicate logs, screenshots, or learner content.

## 5. Failure and stop matrix

| Signal | Required response |
| --- | --- |
| Initial verification fails | Report exact `problems`; do not diagnose, fix, or append closure evidence |
| Reproduction disproves the hypothesis | Revise the hypothesis; do not close as fixed |
| Regression or relevant validation fails | Keep the bug open; do not run `resolve_bug_report.py` with `fixed_verified` |
| No commit/PR reference and commit/PR is not authorized | Report local validation and request direction; leave status `reported` |
| Resolution command rejects inputs | Correct the rejected closure input only if closure authority remains valid; never edit YAML or roadmap by hand |
| Post-write verification fails | Report exact `problems` and stop; do not repair immutable files manually |

## 6. Handoff contract

On an authorized closure, report the BUG-ID, resolution path, chosen outcome, durable reference when applicable, exact validation command/result, and post-write verification result. On any stop condition, report the current unmodified status and the minimal missing authority or evidence.
