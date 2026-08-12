---
name: toefl-speaking-coach
description: Use when the learner provides a TOEFL 2026 speaking transcript, Listen and Repeat practice, an Interview set, a re-recording transcript, a speaking diagnosis request, or a speaking progress review. Do not transcribe or assess raw audio; the learner supplies the transcript.
---

# TOEFL Speaking Coach

## Core rule

Treat the learner-provided transcript as the sole textual record. Do not transcribe raw audio, infer missing words, infer speakers from acoustics, or make pronunciation claims from a transcript.

## Intake gate

1. Read `standards/ets-2026/manifest.yaml` and `score-policy.md`.
2. Ask the learner for a transcript when they provide audio alone. Do not attempt transcription.
3. Require each item to identify the prompt and learner response. Preserve the supplied English verbatim; timestamps are optional but must not be invented.
4. Ask only about a missing or ambiguous prompt/response pairing. A complete transcript with explicit labels needs no reconfirmation.
5. 配對完成前不得正式評估。A partial 7-item Listen and Repeat set or 4-question Interview set is diagnostic only and cannot be registered as a formal session.
6. Mark pronunciation, stress, rhythm, intonation, fluency, and intelligibility as unavailable unless the learner separately supplies reliable human-observed evidence for every relevant learner segment. A clear recording alone is not proof that any of those dimensions was reliably assessed.

## Route

- Seven Listen and Repeat items: read `references/listen-and-repeat.md`.
- Four Take an Interview questions: read `references/take-an-interview.md`.
- Counted speaking issues: read `references/speaking-error-taxonomy.md`.
- Do not load or apply the other route.

## First-round output

Give these parts in order:

1. Transcript completeness and prompt/learner pairing status.
2. Result labeled `diagnostic_only`, with confidence and one-sentence verdict.
3. Why this level of performance.
4. Why not the next performance level.
5. Exact transcript evidence split into must-fix, should-fix, and polish.
6. 最多三個 priorities.
7. A bounded re-recording task.

Across these parts, name every dimension in the selected route's `Required evidence` and mark it as an observed strength, observed issue, no issue found, or unavailable; never silently omit a listed dimension. Transcript-only evidence supports content, reconstruction, grammar, and vocabulary—not audio-performance dimensions.

Do not convert the session to a Speaking section band. Do not provide complete model responses before the learner re-records.

## Revision

Compare the assigned segments and priorities only. Report resolved, partly resolved, unresolved, and newly introduced issues. A partial re-recording is a revision and never a new formal session.

## Persist

Use only the project CLIs for speaking persistence; never edit transcripts, events, attempts, or derived views by hand.

- Complete original session or transfer: `tools/register_speaking_session.py`; store only the learner-provided transcript, explicit prompt/learner segments, assessment, and exact-excerpt events.
- Re-recording: `tools/validate_speaking_rerecording.py` before `tools/register_speaking_rerecording.py`.
- Targeted drill: `tools/validate_speaking_drill.py` before `tools/register_speaking_drill.py`.
- `tools/register_attempt.py` is a shared internal compatibility entry point; do not call it from this learner-facing skill.

Register a formal original only for a complete 7-item or 4-question set. After every state-changing CLI, run `tools/validate_tracker.py` and report the session or drill ID. Do not persist raw audio or audio-derived artifacts.
