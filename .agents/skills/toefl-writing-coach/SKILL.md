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

Lock the assigned priorities to the parent feedback before assessing the revision. New issues never increase `revision_outcomes.assigned`, never lower the target-resolution rate, and never retroactively make a resolved parent target unresolved. When `new_errors > 0`, add `## New issues (not assigned targets)` inside `# Evidence`; keep each exact excerpt there. Do not add a new issue to `# Priorities`, `# Rewrite task`, or drill targets in the same round. It may become a focus only when it is explicitly assigned in a later feedback scope.

Make revision feedback constructive, not merely corrective. For each unresolved assigned priority, state what is already acceptable, then name the one change that improves clarity, naturalness, precision, logic, or control and why it helps the reader. For at most two high-leverage items, add a compact comparison: `Keep` (the learner's valid intention), `Adjust` (the exact structural or wording choice), and `Direction` (a reusable pattern or one bounded sentence-level option). Distinguish a hard error from an acceptable-but-less-natural choice; identify the relevant mechanism such as parallelism, redundancy, reference, collocation, specificity, or cause-and-effect. Do not turn every row into a long lecture, supply a complete post, or add unassigned issues to the current revision targets.

Follow this state machine in order: `revision_targets → targeted_drill_gate → naturalness_follow_up → transfer`.

After `# Rewrite task`, always add `# Targeted drill` and one exact status line. A drill is learner-directed practice, never a penalty: before finalizing an incomplete second revision, first give exact-excerpt feedback and a bounded rewrite direction, then ask whether the learner wants the drill. Do not generate or register a drill unless the learner explicitly opts in.

- Revision round 1 incomplete: set `Drill status` to `not_required_yet`. Explain that the third-revision gate has not been reached. Do not add follow-up.
- Revision round 1 or 2 fully resolves all assigned priorities: set `Drill status` to `skipped`. Explain that the third revision was not triggered, then add follow-up in the same output.
- Revision round 2 remains partly resolved or unresolved: first give the exact-excerpt feedback and bounded rewrite direction, then ask the learner whether they want the targeted drill. When finalizing the record after their reply, add exactly `Invitation: After reviewing the exact-excerpt feedback and bounded rewrite direction, learner was asked whether to start this targeted drill.` If they opt in, set `Drill status` to `required`, add `Decision: learner opted in ...`, list `Source`, `Targets`, `Items`, and `Completion`, then use `writing-drill-lifecycle` to generate, assess, and register the bounded drill. Do not add follow-up.
- Revision round 2 remains partly resolved or unresolved and the learner declines the drill: set `Drill status` to `declined`. Add the same `Invitation` record and `Decision: learner declined ...`, then provide the mandatory naturalness and precision follow-up. Do not generate a drill, offer a transfer, or accept a third revision in that chain.
- A later revision after the required persisted drill: set `Drill status` to `completed`. Cite the `Drill attempt`; reject a third revision without that drill. Add follow-up only when all assigned priorities are now resolved.

A targeted drill does not itself resolve revision priorities. After the learner completes it, require a bounded revision check for the remaining targets. Do not create a drill when the first or second revision has already resolved every target. While asking for the learner's choice, hold the second-revision registration open; finalize it as `required` or `declined` only after the learner responds.

Add `# Naturalness and precision follow-up` after all assigned priorities are fully resolved and any required drill is completed or legally skipped. It is also mandatory when the learner declines the drill after an incomplete second revision; in that case it concludes the chain and must not open a transfer or third revision. This follow-up is a non-scoring revision-completion artifact, not a targeted drill and not a new error table: it must not change task score, formal count, counted events, error rates, historical status, mastery, training plan, or transfer gates.

When follow-up is blocked, do not emit the follow-up heading or a placeholder follow-up status. Explain the block inside `# Targeted drill`. Likewise, do not emit a transfer heading or suggestion until after a completed follow-up; a declined drill never unlocks transfer.

- Treat the follow-up as a final-step quality pass for moving a stable 4-level response closer to 5, not as a second list of basic corrections. It must identify one to three previously unaddressed, non-scoring opportunities in precision, concise flow, causal logic, register, or controlled variety.
- Do not repeat a source excerpt, correction, diagnosis, or priority already given in the current scored assessment or its parent feedback.
- When task completion and the core causal/logic relationship are already clear, prioritize sentence flow or reference, then natural grammar/collocation, precise wording, and unnecessary repetition; do not ask for extra ideas merely to fill this follow-up. If one of those core elements blocks reader understanding or the score ceiling, treat it through the existing must-fix/should-fix route instead.
- If there are issues, give one to three numbered entries in the form `Excerpt: \`exact learner text\``. Each entry identifies either nearby repeated meaning/structure, unclear flow/reference, an overly broad or imprecise word, or an understandable but non-idiomatic construction; explain the reader effect and give one single-sentence option that preserves the learner's meaning. Never combine options into a complete model post.
+- End an actionable follow-up after those suggestions. Do not add a `Mini-practice`, a rewrite request, answer-hidden questions, or an answer key. Learner questions and assessed practice belong only to a learner-approved targeted drill.
- If no genuine issue exists, write exactly `No naturalness or precision issue to flag.` only after a documented audit of one to three plausible candidate excerpts. Add `## Naturalness audit`; format each numbered row with `Candidate:`, the exact learner text in backticks, an em dash, and the reason it needs no action. Then add `## Transfer suggestion` with one non-scoring new-prompt transfer suggestion. Do not invent feedback to fill the section or use the zero-item result to skip a real issue.

Transfer is available only after the follow-up. Never jump from resolved priorities or a completed drill directly to a transfer suggestion.

For remaining or newly introduced counted errors, give only the minimal correction and one short diagnosis.

## Recurrence and progress output

For a recurrence or progress request, classify each counted code from ordered `formal_original` records with the deterministic tracker status rules. Explicitly output the resulting `historical_status`; revisions and targeted drills do not change it.
For Discussion, also read `standards/ets-2026/writing-skill-families.yaml` when available and show derived family signals without replacing atomic codes. After two unresolved revision rounds, require a bounded targeted drill before a third revision; do not recommend a transfer check until the later revision completes its targets and the mandatory follow-up is delivered.
Targeted drills use `record_type: targeted_drill`: they are non-scored practice records, never formal attempts, and must include bounded `drill` metadata (`set_id`, target codes, item/correct counts, and source attempt IDs). Use `writing-drill-lifecycle` for generation, review, registration, and transfer; after registration, read `tracker/writing/mastery.md` as derived coaching evidence, not a replacement for each event's `historical_status`.
When `tracker/writing/training-plan.md` contains a recommendation, follow its route, target codes, bounded item count, and new-prompt transfer check; do not skip directly to another revision.
Generate the learner drill with `tools/generate_writing_drill.py`; show `drill.md` first and keep `answer-key.md` separate until the learner has attempted it. Register a transfer only through `tools/register_writing_transfer.py`, with a new prompt and explicit confirmed opportunities for every target code.

## Persist

Use only the project CLIs for writing persistence; never edit tracker attempts, events, reports, or derived views by hand.

- Original or revision: `tools/register_writing_attempt.py`.
- Targeted drill and new-prompt transfer: use `writing-drill-lifecycle`, which owns pack generation, review, registration, and transfer gates.
- `tools/register_attempt.py` is a shared internal compatibility entry point; do not call it from this learner-facing skill.

After every state-changing CLI, run `tools/validate_tracker.py`; report the immutable attempt or drill ID and any common or task-specific three-practice report generated. Use `tools/validate_writing_calibration.py` only for maintainer-requested rubric calibration, not learner feedback.
