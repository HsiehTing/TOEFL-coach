---
name: toefl-speaking-coach
description: Use when the learner provides TOEFL 2026 speaking audio, a continuous prompt-and-answer recording, Listen and Repeat practice, an Interview set, a re-recording, a speaking diagnosis request, or a speaking progress review.
---

# TOEFL Speaking Coach

## Core rule

Separate audio quality from English performance, and complete speaker mapping before formal assessment.

## Intake gate

1. Read `standards/ets-2026/manifest.yaml`, `score-policy.md`, and `references/audio-intake.md`.
2. Run `tools/inspect_audio.py` on the source file.
3. Run `tools/prepare_speaking_session.py` to create a local transcript and TOEFL-structure role map.
4. Segment alternating examiner and learner speech; retain timestamps and confidence.
5. Present only ambiguous mappings for confirmation; clear rows do not need confirmation.
6. 配對完成前不得正式評估。
7. Keep raw audio external to the tracker. A partial or incomplete map is diagnostic only and cannot be registered as a formal session.
8. State which dimensions remain reliable when audio quality is limited.

## Route

- Seven Listen and Repeat items: read `references/listen-and-repeat.md`.
- Four Take an Interview questions: read `references/take-an-interview.md`.
- Counted speaking issues: read `references/speaking-error-taxonomy.md`.
- Do not load or apply the other route.

## First-round output

Give these parts in order:

1. File quality and examiner/learner mapping status.
2. Result labeled `diagnostic_only`, with confidence and one-sentence verdict.
3. Why this level of performance.
4. Why not the next performance level.
5. Timestamp evidence split into must-fix, should-fix, and polish.
6. 最多三個 priorities.
7. A bounded re-recording task.

Across these parts, name every dimension in the selected route's `Required evidence` and mark it as an observed strength, observed issue, no issue found, or unavailable; never silently omit a listed dimension.

Do not convert the session to a Speaking section band. Do not provide complete model responses before the learner re-records.

## Revision

Compare the assigned segments and priorities only. Report resolved, partly resolved, unresolved, and newly introduced issues. A partial re-recording is a revision and never a new formal session.

## Persist

預設不複製原始音檔。Store the source reference, inspection JSON, confirmed segment map, transcript, assessment, and timestamp events through `tools/register_speaking_session.py`. Register only a complete 7-item or 4-question formal original. Rebuild reports and run `tools/validate_tracker.py`.
