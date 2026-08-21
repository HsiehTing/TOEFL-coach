---
name: toefl-speaking-coach
description: Use when the learner provides TOEFL 2026 speaking audio or transcript, Listen and Repeat practice, an Interview set, a re-recording transcript, a speaking diagnosis request, or a speaking progress review. Local audio may be transcribed through the project-local ASR adapter; do not use cloud transcription or speaker identity data.
---

# TOEFL Speaking Coach

## Core rule

Treat an explicit learner transcript or the path-free output of the local ASR adapter as the textual record. A learner-provided transcript remains the fallback when local ASR is unavailable. Do not use cloud transcription, speaker enrollment, voiceprints, or generic diarization; do not infer missing words or roles from acoustics alone. ASR recognizability is a diagnostic proxy, not proof of phoneme-level pronunciation.

## Intake gate

1. Read `standards/ets-2026/manifest.yaml` and `score-policy.md`.
2. When the learner provides local audio, use `tools/prepare_speaking_item_batch.py` when each file is one complete prompt→learner item; use `tools/prepare_speaking_session.py` only when one file contains the complete session. Add `--include-segment-quality` when the file is being prepared for registration. These flows run local transcription, route-specific role mapping, and (when requested) learner-turn quality checks. If the adapter or model is unavailable, ask for a transcript instead. Never upload the audio.
3. Normalize the path-free ASR artifact, filter directions, and infer the task structure using `role_mapping.py`; preserve supplied transcript text verbatim when the learner provides one.
4. Require each item to identify the prompt and learner response. Timestamps from ASR are evidence; never invent missing boundaries.
5. Ask only about a missing or ambiguous prompt/response pairing. A complete transcript with explicit labels needs no reconfirmation.
6. 配對完成前不得正式評估。A partial 7-item Listen and Repeat set or 4-question Interview set is diagnostic only and cannot be registered as a formal session.
7. Keep `text_usable` and `acoustic_usable` separate for every learner segment. A low-volume but decodable turn may remain text-usable while acoustic dimensions are limited; ASR recognizability is a diagnostic proxy, not phoneme-level proof. Pronunciation, stress, rhythm, intonation, fluency, and intelligibility are unavailable for formal evidence unless the applicable audio evidence contract is satisfied.
8. When segment quality is available, insert the exact block produced by `tools/render_speaking_usability_feedback.py` under the first-round feedback. Keep its route focus unchanged: Listen and Repeat reports reconstruction availability; Interview reports content dimensions. The block is diagnostic only and must not be rewritten as a pronunciation score.

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

Do not convert the session to a Speaking section band. Do not provide complete model responses before the learner re-records. Do not persist raw audio, temporary audio, model absolute paths, or voice identity data.

## Revision

Compare the assigned segments and priorities only. Report resolved, partly resolved, unresolved, and newly introduced issues. A partial re-recording is a revision and never a new formal session.

## Persist

Use only the project CLIs for speaking persistence; never edit transcripts, events, attempts, or derived views by hand.

- Complete original session or transfer: `tools/register_speaking_session.py`; a prepared local-audio artifact may be supplied with `--prepared-session`, which carries the path-free ASR mapping and segment quality into registration. Store only the path-free transcript or ASR artifact, explicit prompt/learner segments, task mapping, segment-scoped `text_usable`／`acoustic_usable` quality, model provenance, assessment, and exact-excerpt events.
- Re-recording: `tools/validate_speaking_rerecording.py` before `tools/register_speaking_rerecording.py`.
- Targeted drill: `tools/validate_speaking_drill.py` before `tools/register_speaking_drill.py`.
- `tools/register_attempt.py` is a shared internal compatibility entry point; do not call it from this learner-facing skill.

Register a formal original only for a complete 7-item or 4-question set. After every state-changing CLI, run `tools/validate_tracker.py` and report the session or drill ID. Do not persist raw audio or audio-derived files; path-free transcript and mapping artifacts are allowed.
