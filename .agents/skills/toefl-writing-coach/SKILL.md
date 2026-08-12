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

## Source fidelity

Treat the learner's submitted response as the source of truth. If the learner also provides a correction table, use it only as a draft; the response overrides it. Copy every `原句` excerpt verbatim, without silently repairing articles, capitalization, word forms, or punctuation. If no complete response is available, use the table's left-hand text verbatim and do not infer omitted words.

Before delivering a correction table, verify each row: the quoted original contains the diagnosed problem, the minimal correction changes that problem, and the reason matches the exact change. Omit a row that fails this check rather than reporting an error already absent from the quoted original.

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

For every counted sentence-level issue, give only the minimal correction in the evidence table. Explain the error before the learner revises; do not provide a clearer alternative phrasing in first-round feedback. Keep each diagnosis to one short sentence naming the main error and rule; add a second sentence only when the correction changes the task meaning.

## Revision output

Compare only against the assigned priorities. Report resolved, partly resolved, unresolved, and newly introduced issues; calculate target-resolution rate. A revision never increases the formal-attempt count. Provide a high-scoring model only after the learner has attempted the revision.

After the priority comparison, add `# Naturalness and precision follow-up`. This is a non-scoring revision-completion artifact, not a targeted drill and not a new error table: it must not change task score, formal count, counted events, error rates, historical status, mastery, training plan, or transfer gates.

- Treat the follow-up as a final-step quality pass for moving a stable 4-level response closer to 5, not as a second list of basic corrections. It must identify one to three previously unaddressed, non-scoring opportunities in precision, concise flow, causal logic, register, or controlled variety.
- Do not repeat a source excerpt, correction, diagnosis, or priority already given in the current scored assessment or its parent feedback.
- When task completion and the core causal/logic relationship are already clear, prioritize sentence flow or reference, then natural grammar/collocation, precise wording, and unnecessary repetition; do not ask for extra ideas merely to fill this follow-up. If one of those core elements blocks reader understanding or the score ceiling, treat it through the existing must-fix/should-fix route instead.
- If there are issues, give one to three numbered entries in the form `Excerpt: \`exact learner text\``. Each entry identifies either nearby repeated meaning/structure, unclear flow/reference, an overly broad or imprecise word, or an understandable but non-idiomatic construction; explain the reader effect and give one single-sentence option that preserves the learner's meaning. Never combine options into a complete model post.
- Then add `## Mini-practice` with two to four numbered, answer-hidden five-minute prompts. Reuse the learner's route and original scenario; ask for a rewrite of the learner's own sentence or a more precise choice. Do not give a key, sample answer, or ETS score.
- If no genuine issue exists, write exactly `No naturalness or precision issue to flag.` and give one non-scoring new-prompt transfer suggestion. Do not invent feedback to fill the section.

For remaining or newly introduced counted errors, give only the minimal correction and one short diagnosis.

## Recurrence and progress output

For a recurrence or progress request, classify each counted code from ordered `formal_original` records with the deterministic tracker status rules. Explicitly output the resulting `historical_status`; revisions and targeted drills do not change it.
For Discussion, also read `standards/ets-2026/writing-skill-families.yaml` when available and show derived family signals without replacing atomic codes. After two unresolved revision rounds, recommend a bounded targeted drill and a new-prompt transfer check.
Targeted drills use `record_type: targeted_drill`: they are non-scored practice records, never formal attempts, and must include bounded `drill` metadata (`set_id`, target codes, item/correct counts, and source attempt IDs). After registration, read `tracker/writing/mastery.md`; treat its state as derived coaching evidence, not a replacement for each event's `historical_status`.
When `tracker/writing/training-plan.md` contains a recommendation, follow its route, target codes, bounded item count, and new-prompt transfer check; do not skip directly to another revision.
Generate the learner drill with `tools/generate_writing_drill.py`; show `drill.md` first and keep `answer-key.md` separate until the learner has attempted it. Register a transfer only through `tools/register_writing_transfer.py`, with a new prompt and explicit confirmed opportunities for every target code.

## Persist

Write immutable attempt and event inputs, run `tools/register_writing_attempt.py`, rebuild reports, then run `tools/validate_tracker.py`. Report the attempt ID and any common or task-specific three-practice report that was generated.
