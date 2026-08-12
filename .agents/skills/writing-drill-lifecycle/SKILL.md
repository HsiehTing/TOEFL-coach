---
name: writing-drill-lifecycle
description: Generate, inspect, assess, register, and transfer TOEFL Writing targeted drills. Use when the user asks to start a recommended writing drill, submits drill responses, asks to review a generated drill pack, or is ready for a new-prompt transfer after a drill; do not use for ordinary Email or Academic Discussion scoring.
---

# Writing Drill Lifecycle

Use this skill only for a drill that is tied to a persisted Writing recommendation or source attempt. Keep drills non-scored and separate from formal Writing attempts.

## Intake gate

1. For generation, require either a recommendation ID or a source attempt ID. Read the active training plan when a recommendation is supplied.
2. For review or registration, require the exact drill-pack path. Read the learner drill; keep `answer-key.md` separate until the learner has attempted the pack.
3. For a transfer, require the completed drill attempt ID, a new prompt, learner response, and explicit confirmed opportunities for every target code.
4. Do not invent answers, item results, source IDs, or opportunities.

## Lifecycle

1. Generate with `python3 tools/generate_writing_drill.py` using exactly one recommendation ID or source attempt ID.
2. Before showing a pack, use `python3 tools/read_writing_drill.py --pack <path>` and present only `drill.md`; do not disclose `answer-key.md`.
3. When the learner submits responses, use `python3 tools/review_writing_drill.py --pack <path>` to inspect the pack and assess only the submitted items.
4. Register completed work only through `python3 tools/register_writing_drill.py`; provide the required feedback, events, and item results.
5. Register transfer only through `python3 tools/register_writing_transfer.py` after every target code has a confirmed opportunity and the drill's conditions are satisfied.
6. Run `python3 tools/validate_tracker.py` after each registration. Report the pack or attempt ID and any remaining transfer gate.

## Boundaries

- Do not edit drill packs, answer keys, assessment files, attempts, events, or derived tracker views by hand.
- Do not turn a drill score into a TOEFL Writing section score or formal attempt.
- Stop when the pack, recommendation, learner response, or target-code opportunity evidence is incomplete; request the missing artifact instead.
