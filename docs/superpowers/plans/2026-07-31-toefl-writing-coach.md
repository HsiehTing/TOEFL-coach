# TOEFL Writing Coach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and forward-test a repo-scoped TOEFL 2026 writing coach that routes Email and Academic Discussion separately, produces consistent iterative feedback, and persists traceable progress.

**Architecture:** A concise `SKILL.md` owns the shared intake and iteration workflow, while task-specific feedback contracts and the error taxonomy live in one-level references loaded only for the selected route. Python validation checks the deterministic parts of a writing assessment before it enters the shared tracker. Skill behavior is tested with baseline and skill-enabled fresh-agent scenarios.

**Tech Stack:** Codex repo skills, Markdown references, Python 3.11+, PyYAML, pytest, shared tracker foundation.

## Global Constraints

- Execute `2026-07-31-toefl-tracker-foundation.md` first.
- Use ETS 2026 task names: Write an Email and Write for an Academic Discussion.
- Use the public 0–5 task rubrics only as simulated task scores.
- Never infer a complete Writing section band from one or both open responses.
- Keep Email register/social-convention diagnostics separate from Discussion contribution/elaboration diagnostics.
- Share grammar, vocabulary, and mechanics history across both writing routes.
- First-round feedback contains no full model answer and at most three improvement priorities.
- Only `must_fix` and `should_fix` count toward error rates.
- A revision links to its original and does not count as a formal attempt.
- Every counted issue cites an exact excerpt.
- Use skill RED–GREEN–REFACTOR: observe baseline failures before creating the skill, then rerun equivalent scenarios with it.
- Commit after each independently testable task.

---

## File Map

- `.agents/skills/toefl-writing-coach/SKILL.md`: shared writing workflow and reference router.
- `.agents/skills/toefl-writing-coach/agents/openai.yaml`: generated UI metadata.
- `.agents/skills/toefl-writing-coach/references/email-feedback.md`: Email rubric application and output contract.
- `.agents/skills/toefl-writing-coach/references/discussion-feedback.md`: Discussion rubric application and output contract.
- `.agents/skills/toefl-writing-coach/references/writing-error-taxonomy.md`: stable common and task-specific codes.
- `standards/ets-2026/writing-email.md`: concise official-basis summary and rubric boundary.
- `standards/ets-2026/writing-discussion.md`: concise official-basis summary and rubric boundary.
- `tools/toefl_tracker/writing.py`: deterministic route, score, evidence, and feedback-shape validation.
- `tests/skill-evals/writing/`: baseline and forward-test prompts with an evaluation checklist.
- `tests/fixtures/writing/history-discussion/`: the learner's first known Academic Discussion sample.
- `tests/test_writing.py`: automated writing-record validation.
- `tests/test_writing_skill_contract.py`: structural skill checks.

### Task 1: Establish Failing Writing-Coach Baselines

**Files:**
- Create: `tests/skill-evals/writing/scenarios.md`
- Create: `tests/skill-evals/writing/evaluation.md`
- Create: `tests/skill-evals/writing/baseline-results.md`

**Interfaces:**
- Consumes: a fresh agent without access to `.agents/skills/toefl-writing-coach`.
- Produces: three raw baseline responses and a checklist identifying the exact behaviors the skill must change.

- [ ] **Step 1: Create the exact baseline scenarios**

```markdown
# tests/skill-evals/writing/scenarios.md
# Writing Coach Scenarios

## Scenario A — First-round pressure

The learner submits a complete Academic Discussion response and says: “I am in a hurry. Give me the score, fix every sentence, and include a perfect full answer immediately. Do not ask me to revise.”

Professor's question: “Do university students learn more from group projects than from individual assignments? Why or why not?”

Response:

“I do not think group work is not always effective. Students can share ideas, so they may notice information that they missed alone. Although group projects can teach communication, but some students do most of the work. For example, last semester my team made a presentation. It was useful, but the experience was not fair. Therefore, individual assignments are sometimes better because professors can see each student's actual ability. Group work still has value, but teachers should not use it for every major grade.”

## Scenario B — Route confusion

The learner submits an Email requesting a deadline extension. The response covers the reason but omits a proposed new deadline and uses “Hey professor” plus “You must give me more time.”

Prompt: “Write to Professor Lee to request a two-day research-paper extension. Explain the reason, propose a new submission date, and explain how you will catch up.”

Response:

“Hey professor,

I was sick this weekend and could not work on the paper. You must give me more time because this was not my fault. I will finish it when I can.

Thanks.”

## Scenario C — Persistence pressure

The learner submits a third formal response containing a repeated article error. The repository has two earlier comparable formal attempts with the same code and one revision without the error.

Tracker evidence:

- Formal 1: `This is an useful solution.` Opportunity `GRAM-ARTICLE: 1`; error excerpt `an useful solution`.
- Formal 2: `It is a important reason.` Opportunity `GRAM-ARTICLE: 1`; error excerpt `a important reason`.
- Revision of Formal 2: `It is an important reason.` This is not a formal original.
- Formal 3: `Schools need a effective method.` Opportunity `GRAM-ARTICLE: 1`; error excerpt `a effective method`.
```

- [ ] **Step 2: Create the pass/fail evaluation contract**

```markdown
# tests/skill-evals/writing/evaluation.md
# Evaluation Contract

## Scenario A

- Labels the 0–5 result as a simulated task score.
- Explains why the response is at the current level and not the next.
- Gives no more than three priorities.
- Does not provide a full model answer before revision.
- Separates must-fix, should-fix, and polish.

## Scenario B

- Uses the Email route rather than the Academic Discussion route.
- Evaluates purpose, missing required content, register, politeness, and action formulation.
- Does not evaluate contribution to classmates.

## Scenario C

- Counts only formal originals when determining recurrence.
- Classifies the article issue as persistent when it appears in three of the last five comparable formal originals.
- Does not use the clean revision to mark the issue controlled.
- Adds an exact source excerpt to every counted event.
```

- [ ] **Step 3: Run three fresh baseline agents without the new skill**

For each scenario, spawn a fresh agent with only the scenario, the approved design spec, and the relevant raw writing artifact. Do not provide `evaluation.md` or describe the expected failures.

Expected: at least one contract item fails across the three scenarios. Save each response verbatim under its scenario heading in `baseline-results.md`, then mark each checklist item pass or fail.

- [ ] **Step 4: Commit the RED evidence**

```bash
git add tests/skill-evals/writing
git commit -m "test: capture writing coach baselines"
```

### Task 2: Add Writing Standards Summaries and the Stable Taxonomy

**Files:**
- Initialize then remove generated placeholders: `.agents/skills/toefl-writing-coach/`
- Create: `standards/ets-2026/writing-email.md`
- Create: `standards/ets-2026/writing-discussion.md`
- Create: `.agents/skills/toefl-writing-coach/references/writing-error-taxonomy.md`
- Create: `tests/test_writing_skill_contract.py`

**Interfaces:**
- Consumes: ETS manifest and score policy from the foundation.
- Produces: stable writing codes and task-specific rubric summaries referenced by the skill.

- [ ] **Step 1: Write failing taxonomy and standards tests**

```python
# tests/test_writing_skill_contract.py
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / ".agents/skills/toefl-writing-coach"


def test_writing_taxonomy_separates_shared_and_task_codes() -> None:
    text = (SKILL / "references/writing-error-taxonomy.md").read_text()
    shared = {"GRAM-ARTICLE", "GRAM-NEGATION", "GRAM-CLAUSE", "GRAM-AGREEMENT",
              "LEX-WORDFORM", "LEX-COLLOCATION", "MECH-SPELLING", "MECH-PUNCTUATION"}
    email = {"EMAIL-PURPOSE", "EMAIL-MISSING-POINT", "EMAIL-REGISTER",
             "EMAIL-POLITENESS", "EMAIL-ORGANIZATION", "EMAIL-ACTION"}
    discussion = {"DISCUSSION-ALIGNMENT", "DISCUSSION-POSITION", "DISCUSSION-BORROWING",
                  "DISCUSSION-CONTRIBUTION", "DISCUSSION-ELABORATION", "DISCUSSION-SUPPORT"}
    assert all(f"`{code}`" in text for code in shared | email | discussion)


def test_each_open_response_standard_states_the_score_boundary() -> None:
    for name in ("writing-email.md", "writing-discussion.md"):
        text = (ROOT / "standards/ets-2026" / name).read_text()
        assert "0–5" in text
        assert "模擬 task score" in text
        assert "不得換算完整 Writing section band" in text
```

- [ ] **Step 2: Run and verify missing-file failures**

Run: `python3 -m pytest tests/test_writing_skill_contract.py -v`

Expected: FAIL because the writing references do not exist.

- [ ] **Step 3: Initialize the skill directory before writing any skill files**

Run:

```bash
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/init_skill.py toefl-writing-coach --path .agents/skills --resources references --interface display_name="TOEFL Writing Coach" --interface short_description="Score and track TOEFL 2026 writing practice" --interface default_prompt="Evaluate this TOEFL 2026 writing response, track recurring errors, and give me a revision task."
```

Expected: the skill directory is created. Immediately delete the generated placeholder `SKILL.md` and `agents/openai.yaml` with `apply_patch`; Task 3 will create their final tested forms. Keep the initialized directory and `references/`.

- [ ] **Step 4: Create the task standards summaries**

```markdown
# standards/ets-2026/writing-email.md
# Write an Email

- Official basis: ETS Writing Scoring Guide, copyright 2025 and applicable to the 2026 task.
- Public task rubric: 0–5.
- Evaluate communicative purpose, elaboration, syntax and word choice, social conventions, register, politeness, organization, action formulation, and language errors.
- Report the result as a 模擬 task score.
- A single Email result不得換算完整 Writing section band.
- Rubric ID: `ets-writing-email-2025-applicable-2026`.
```

```markdown
# standards/ets-2026/writing-discussion.md
# Write for an Academic Discussion

- Official basis: ETS Writing Scoring Guide, copyright 2025 and applicable to the 2026 task.
- Public task rubric: 0–5.
- Evaluate relevance, clarity of contribution, explanation, examples/details, syntactic variety, word choice, and language errors.
- Also diagnose prompt alignment, original contribution, and excessive borrowing from the stimulus.
- Report the result as a 模擬 task score.
- A single Discussion result不得換算完整 Writing section band.
- Rubric ID: `ets-writing-discussion-2025-applicable-2026`.
```

- [ ] **Step 5: Create the complete taxonomy table**

```markdown
# Writing Error Taxonomy

| Code | Scope | Count when |
|---|---|---|
| `GRAM-ARTICLE` | Shared | Article selection or omission is incorrect. |
| `GRAM-NEGATION` | Shared | Negation changes or obscures intended meaning. |
| `GRAM-CLAUSE` | Shared | Clause connection, fragment, run-on, or paired `although` + `but` is incorrect. |
| `GRAM-AGREEMENT` | Shared | Subject–verb or noun agreement is incorrect. |
| `LEX-WORDFORM` | Shared | The selected part of speech or derived form is incorrect. |
| `LEX-COLLOCATION` | Shared | Word combination is unnatural or changes clarity. |
| `MECH-SPELLING` | Shared | Spelling error is not a harmless timed typo. |
| `MECH-PUNCTUATION` | Shared | Punctuation damages sentence boundaries or meaning. |
| `EMAIL-PURPOSE` | Email | The communicative purpose is missing or unclear. |
| `EMAIL-MISSING-POINT` | Email | A required prompt point is absent. |
| `EMAIL-REGISTER` | Email | Tone does not fit the relationship or context. |
| `EMAIL-POLITENESS` | Email | Social convention makes the request or response inappropriate. |
| `EMAIL-ORGANIZATION` | Email | Information order obstructs the communicative goal. |
| `EMAIL-ACTION` | Email | A request, proposal, refusal, or criticism is formulated ineffectively. |
| `DISCUSSION-ALIGNMENT` | Discussion | The response answers a materially altered question. |
| `DISCUSSION-POSITION` | Discussion | The writer's position is absent or internally inconsistent. |
| `DISCUSSION-BORROWING` | Discussion | Language or reasoning relies excessively on the stimulus. |
| `DISCUSSION-CONTRIBUTION` | Discussion | The post adds no meaningful original contribution. |
| `DISCUSSION-ELABORATION` | Discussion | An explanation or example is incomplete or unclear. |
| `DISCUSSION-SUPPORT` | Discussion | A claim lacks relevant reasons, details, or causal connection. |

Use `must_fix` for meaning/task-completion failures, `should_fix` for recurring clarity or control problems, and `polish` for optional sophistication. Only the first two levels enter rates.
```

- [ ] **Step 6: Run tests and commit**

Run: `python3 -m pytest tests/test_writing_skill_contract.py -v`

Expected: 2 tests pass.

```bash
git add standards/ets-2026/writing-email.md standards/ets-2026/writing-discussion.md .agents/skills/toefl-writing-coach/references/writing-error-taxonomy.md tests/test_writing_skill_contract.py
git commit -m "docs: define TOEFL writing routes"
```

### Task 3: Author the Initialized Writing Coach Skill

**Files:**
- Create: `.agents/skills/toefl-writing-coach/SKILL.md`
- Create via generator: `.agents/skills/toefl-writing-coach/agents/openai.yaml`
- Create: `.agents/skills/toefl-writing-coach/references/email-feedback.md`
- Create: `.agents/skills/toefl-writing-coach/references/discussion-feedback.md`
- Modify: `tests/test_writing_skill_contract.py`

**Interfaces:**
- Consumes: standards and taxonomy from Task 2; root `AGENTS.md`.
- Produces: discoverable skill `toefl-writing-coach` and two conditional feedback contracts.

- [ ] **Step 1: Extend the contract test before creating the skill**

```python
def test_skill_routes_references_and_enforces_iteration() -> None:
    text = (SKILL / "SKILL.md").read_text()
    assert len(text.splitlines()) < 180
    assert "references/email-feedback.md" in text
    assert "references/discussion-feedback.md" in text
    assert "references/writing-error-taxonomy.md" in text
    assert "第一輪不提供完整範文" in text
    assert "最多三個" in text
    assert "tools/validate_tracker.py" in text


def test_task_contracts_have_distinct_required_fields() -> None:
    email = (SKILL / "references/email-feedback.md").read_text()
    discussion = (SKILL / "references/discussion-feedback.md").read_text()
    assert "Register and politeness" in email
    assert "Original contribution" not in email
    assert "Original contribution" in discussion
    assert "Register and politeness" not in discussion
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m pytest tests/test_writing_skill_contract.py -v`

Expected: FAIL because `SKILL.md` and the task references do not exist.

- [ ] **Step 3: Create `SKILL.md` with the concise workflow**

```markdown
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

## Route

- Email: read `references/email-feedback.md`.
- Academic Discussion: read `references/discussion-feedback.md`.
- For counted errors in either route: read `references/writing-error-taxonomy.md`.
- Do not load the other task route.

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

## Revision output

Compare only against the assigned priorities. Report resolved, partly resolved, unresolved, and newly introduced issues; calculate target-resolution rate. A revision never increases the formal-attempt count. Provide a high-scoring model only after the learner has attempted the revision.

## Persist

Write immutable attempt and event inputs, run `tools/register_attempt.py`, rebuild reports, then run `tools/validate_tracker.py`. Report the attempt ID and any common or task-specific three-practice report that was generated.
```

- [ ] **Step 4: Add the Email output contract**

```markdown
# Email Feedback Contract

Use rubric `ets-writing-email-2025-applicable-2026`.

## Required assessment fields

- Communicative purpose and relationship
- Required prompt points
- Supporting elaboration
- Register and politeness
- Social conventions and organization
- Request, proposal, refusal, or criticism formulation
- Syntax, vocabulary, and counted language evidence

## First-round score explanation

State which rubric features are consistently successful, generally successful, partially successful, mostly unsuccessful, or unsuccessful. Explain the single strongest blocker to the next score. Do not assess original contribution to classmates.

## Revision assignment

Require the learner to repair missing communicative content before stylistic polishing. Give a target audience, action, and tone constraint without supplying a full replacement email.
```

- [ ] **Step 5: Add the Discussion output contract**

```markdown
# Academic Discussion Feedback Contract

Use rubric `ets-writing-discussion-2025-applicable-2026`.

## Required assessment fields

- Exact alignment with the professor's question
- Clear and internally consistent position
- Original contribution to the discussion
- Relationship to classmates' viewpoints
- Relevant explanation, examples, details, and causal links
- Excessive stimulus borrowing
- Syntax, vocabulary, and counted language evidence

## First-round score explanation

State which rubric features are consistently successful, generally successful, partially successful, mostly unsuccessful, or unsuccessful. Explain the single strongest blocker to the next score. Do not score Email register or social conventions.

## Revision assignment

Require the learner to correct any altered thesis first, then independently develop one reason with a concrete explanation or example. Do not supply a full replacement post before revision.
```

- [ ] **Step 6: Generate final UI metadata**

Run:

```bash
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py .agents/skills/toefl-writing-coach --interface display_name="TOEFL Writing Coach" --interface short_description="Score and track TOEFL 2026 writing practice" --interface default_prompt="Evaluate this TOEFL 2026 writing response, track recurring errors, and give me a revision task."
```

Expected: creates `agents/openai.yaml` from the completed skill.

- [ ] **Step 7: Validate, run tests, and commit**

Run:

```bash
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-writing-coach
```

Expected: validation passes.

Run: `python3 -m pytest tests/test_writing_skill_contract.py -v`

Expected: 4 tests pass.

```bash
git add .agents/skills/toefl-writing-coach tests/test_writing_skill_contract.py
git commit -m "feat: add TOEFL writing coach skill"
```

### Task 4: Validate Writing Assessments Before Registration

**Files:**
- Create: `tools/toefl_tracker/writing.py`
- Create: `tests/test_writing.py`

**Interfaces:**
- Consumes: attempt dict, event list, and first-round feedback Markdown.
- Produces: `validate_writing_assessment(attempt: dict, events: list[dict], feedback: str) -> None`.

- [ ] **Step 1: Write failing route and feedback-shape tests**

```python
# tests/test_writing.py
import pytest

from toefl_tracker.models import ValidationError
from toefl_tracker.writing import validate_writing_assessment


def attempt(task_type: str, rubric: str) -> dict:
    return {
        "modality": "writing",
        "task_type": task_type,
        "rubric_version": rubric,
        "task_score": {"scale": "0-5", "value": 3, "confidence": "medium"},
    }


VALID_FEEDBACK = """# Result
Simulated task score: 3/5
# Why this level
Evidence.
# Why not the next level
Evidence.
# Evidence
| Excerpt | Level |
|---|---|
| a object | should_fix |
# Priorities
1. Fix article selection.
# Rewrite task
Rewrite the affected sentence.
"""


def test_discussion_requires_discussion_rubric() -> None:
    row = attempt("academic_discussion", "ets-writing-discussion-2025-applicable-2026")
    validate_writing_assessment(row, [], VALID_FEEDBACK)


def test_email_cannot_use_discussion_rubric() -> None:
    row = attempt("email", "ets-writing-discussion-2025-applicable-2026")
    with pytest.raises(ValidationError, match="rubric"):
        validate_writing_assessment(row, [], VALID_FEEDBACK)


def test_more_than_three_priorities_is_rejected() -> None:
    feedback = VALID_FEEDBACK.replace(
        "1. Fix article selection.",
        "1. One\n2. Two\n3. Three\n4. Four",
    )
    row = attempt("academic_discussion", "ets-writing-discussion-2025-applicable-2026")
    with pytest.raises(ValidationError, match="three priorities"):
        validate_writing_assessment(row, [], feedback)
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m pytest tests/test_writing.py -v`

Expected: FAIL because `toefl_tracker.writing` does not exist.

- [ ] **Step 3: Implement the deterministic writing gate**

```python
# tools/toefl_tracker/writing.py
import re

from toefl_tracker.models import ValidationError


RUBRICS = {
    "email": "ets-writing-email-2025-applicable-2026",
    "academic_discussion": "ets-writing-discussion-2025-applicable-2026",
}
REQUIRED_HEADINGS = (
    "# Result",
    "# Why this level",
    "# Why not the next level",
    "# Evidence",
    "# Priorities",
    "# Rewrite task",
)


def validate_writing_assessment(attempt: dict, events: list[dict], feedback: str) -> None:
    if attempt.get("modality") != "writing":
        raise ValidationError("writing assessment requires writing modality")
    expected = RUBRICS.get(attempt.get("task_type"))
    if expected is None or attempt.get("rubric_version") != expected:
        raise ValidationError("writing task and rubric do not match")
    score = attempt.get("task_score", {})
    if score.get("scale") != "0-5" or not isinstance(score.get("value"), int) or not 0 <= score["value"] <= 5:
        raise ValidationError("writing task score must be an integer from 0 to 5")
    if any(heading not in feedback for heading in REQUIRED_HEADINGS):
        raise ValidationError("first-round feedback is missing required headings")
    priority_block = feedback.split("# Priorities", 1)[1].split("# Rewrite task", 1)[0]
    if len(re.findall(r"(?m)^\d+\.\s", priority_block)) > 3:
        raise ValidationError("first-round feedback exceeds three priorities")
    for event in events:
        excerpt = str(event.get("source_excerpt", "")).strip()
        if event.get("level") in {"must_fix", "should_fix"} and excerpt not in feedback:
            raise ValidationError(f"feedback omits counted evidence: {event.get('event_id')}")
```

- [ ] **Step 4: Run focused and full tests**

Run: `python3 -m pytest tests/test_writing.py -v`

Expected: 3 tests pass.

Run: `python3 -m pytest -v`

Expected: all foundation and writing tests pass.

- [ ] **Step 5: Commit the writing gate**

```bash
git add tools/toefl_tracker/writing.py tests/test_writing.py
git commit -m "feat: validate writing coach assessments"
```

### Task 5: Forward-Test the Skill Against the Baselines

**Files:**
- Create: `tests/skill-evals/writing/skill-results.md`
- Modify: `.agents/skills/toefl-writing-coach/SKILL.md` only when a witnessed failure requires a minimal correction.
- Modify: the directly relevant reference only when a witnessed route-specific failure requires it.

**Interfaces:**
- Consumes: the three scenarios from Task 1 and the completed writing skill.
- Produces: fresh-agent evidence that all evaluation-contract items pass.

- [ ] **Step 1: Run Scenario A with the skill**

Spawn a fresh agent with: `Use $toefl-writing-coach at .agents/skills/toefl-writing-coach to respond to Scenario A and its raw response.`

Do not provide `evaluation.md`. Save the output verbatim and evaluate every Scenario A criterion.

- [ ] **Step 2: Run Scenario B with the skill**

Spawn another fresh agent with: `Use $toefl-writing-coach at .agents/skills/toefl-writing-coach to respond to Scenario B and its raw Email.`

Save the output verbatim and evaluate every Scenario B criterion.

- [ ] **Step 3: Run Scenario C with the skill and tracker fixture**

Spawn another fresh agent with: `Use $toefl-writing-coach at .agents/skills/toefl-writing-coach to assess Scenario C using the supplied tracker fixture.`

Save the output verbatim and evaluate every Scenario C criterion.

- [ ] **Step 4: Apply only evidence-driven skill corrections**

For each failed criterion, record the agent's exact omission or rationalization in `skill-results.md`, add the smallest binding instruction or required output slot, and rerun only the affected fresh-agent scenario. Continue until every criterion passes.

- [ ] **Step 5: Revalidate and commit**

Run:

```bash
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-writing-coach
```

Expected: validation passes.

Run: `python3 -m pytest tests/test_writing_skill_contract.py tests/test_writing.py -v`

Expected: all writing tests pass.

```bash
git add .agents/skills/toefl-writing-coach tests/skill-evals/writing/skill-results.md
git commit -m "test: forward-test TOEFL writing coach"
```

### Task 6: Register the Learner's Historical Academic Discussion Attempt

**Files:**
- Create: `tests/fixtures/writing/history-discussion/prompt.md`
- Create: `tests/fixtures/writing/history-discussion/response.md`
- Create: `tests/fixtures/writing/history-discussion/attempt-input.yaml`
- Create: `tests/fixtures/writing/history-discussion/feedback.md`
- Create: `tests/fixtures/writing/history-discussion/events.jsonl`
- Generate: `tracker/writing/attempts/W-AD-20260731-001/`
- Generate: `tracker/writing/error-events.jsonl`
- Generate: `tracker/writing/dashboard.csv`
- Generate: `tracker/writing/profile.md`

**Interfaces:**
- Consumes: the learner's submitted history prompt/response and the approved provisional 3/5 diagnosis.
- Produces: first real formal writing record, with exact evidence and an explicitly unknown practice date.

- [ ] **Step 1: Create the exact prompt and original response fixtures**

Create `prompt.md` with this exact content:

```text
Your professor is teaching a class on education. Write a post responding to the professor's question. In your response, you should do the following:

- Express and support your opinion.
- Make a contribution to the discussion in your own words.

An effective response will contain at least 100 words.

Doctor Gupta:

Every generation faces a unique set of social problems that it must solve. The question is, how do we best prepare people to solve future problems? Some people believe that to solve any social problem, it is essential to study history and learn from it. Others disagree. In your opinion, do we have to study history in order to solve the problems we will face in the future? Why or why not?

Claire:

I think it is essential that we study history. I forget the exact quotation, but it's been said that if citizens don't understand history, societies will just repeat the same mistakes they made in the past. And I agree with that. I recently watched a historical movie, and I saw many connections with the problems we are facing today.

Paul:

My concern is that history can be presented in a biased way. Events might not be recorded as they actually happened. Historians might exaggerate or downplay the importance of certain things, and they might not show the whole picture or all points of view. Although I like studying history, the lessons learned are usually insufficient for solving today's complex problems.
```

Create `response.md` with this exact original text:

```text
I can not agree that studying history alone can solve social problems , because history can be presented in a biased way.

Historical events might not be recorded in a objected way. In fact, it is almost not practical to perceive a historical event in an even angle. Historians might exaggerate or downplay the view based on their personal perspectives. Thus, although we can learn much from history, I do not think that it is not sufficient for solving today’s complex problems.

Some argue that we can learn from historical events. However, this view does not fully consider the fact that society changes rapidly, a lesson from historical event is unlikely to apply to modern issues like gender equality, A.I. governance …etc. While we can still learn from historical events, many issues are too complicated and require more domain knowledge and experience to solve.

For these reasons, I believe that although history can connect to some of the issues we are facing, but it might be presented in a biased way and might not be able to apply to most complex modern issues.
```

- [ ] **Step 2: Create immutable input metadata**

```yaml
schema_version: 1
attempt_id: W-AD-20260731-001
modality: writing
task_type: academic_discussion
record_type: formal_original
submitted_at: "2026-07-31T00:00:00+08:00"
practiced_at: null
timed: null
duration_seconds: null
assistance:
  spellcheck: null
  translation: null
  other: null
word_count: 183
rubric_version: ets-writing-discussion-2025-applicable-2026
standard_verified_at: "2026-07-31"
task_score:
  scale: "0-5"
  value: 3
  confidence: medium_high
task_metrics:
  prompt_alignment: limited
  position: clear
  original_contribution: limited
  elaboration: partial
opportunities:
  GRAM-ARTICLE: 2
  GRAM-NEGATION: 1
  GRAM-CLAUSE: 3
  LEX-WORDFORM: 2
  LEX-COLLOCATION: 4
  DISCUSSION-ALIGNMENT: 1
  DISCUSSION-BORROWING: 1
  DISCUSSION-ELABORATION: 2
parent_attempt_id: null
revision_outcomes: null
```

- [ ] **Step 3: Create feedback and exact error events**

Create `feedback.md` with:

```markdown
# Result

Simulated Academic Discussion task score: 3/5. Confidence: medium-high.

The response is understandable and organized around two relevant concerns, but the thesis partly changes the professor's question and several noticeable language errors reduce precision.

# Why this level

The post gives a clear negative position, develops two reasons, and reaches the 100-word requirement. The reader can follow the main argument. This matches a partially successful response because elaboration is uneven and noticeable grammar and word-choice errors sometimes obscure the intended claim.

# Why not the next level

A 4-level response would answer the exact question, add a more independent contribution to the existing discussion, develop its examples adequately, and contain only a few language errors. Here, “essential to study history” becomes “studying history alone can solve social problems”; the bias reason closely follows Paul's post; and “A.I. governance” is named without explaining why historical lessons fail there.

# Evidence

| Excerpt | Level | Diagnosis |
|---|---|---|
| studying history alone can solve social problems | must_fix | This changes “Is studying history essential?” into “Can history alone solve everything?” |
| history can be presented in a biased way | should_fix | This repeats Paul's central reason without enough independent development. |
| in a objected way | should_fix | The article is wrong, and `objected` is the wrong word form for `objective`. |
| I do not think that it is not sufficient | must_fix | The double negative reverses the intended meaning. |
| although history can connect to some of the issues we are facing, but | should_fix | Use either `although` or `but`, not both in this clause pattern. |
| modern issues like gender equality, A.I. governance | should_fix | The examples are listed but not causally explained. |

# Priorities

1. Rewrite the thesis so it answers whether studying history is necessary, without introducing the stronger “history alone” claim.
2. Replace the double negative and the paired `although` + `but` construction with unambiguous sentences.
3. Develop one modern issue with two sentences explaining why history is insufficient and what additional expertise is needed.

# Rewrite task

Rewrite the introduction, the AI-governance support, and the conclusion in 90–130 words. Keep your position, but do not copy Paul's wording and do not write a complete new essay beyond those three parts.
```

Create `events.jsonl` with exactly these seven JSON objects, one per line:

```jsonl
{"event_id":"ERR-20260731-0001","attempt_id":"W-AD-20260731-001","taxonomy_version":1,"code":"DISCUSSION-ALIGNMENT","source_excerpt":"studying history alone can solve social problems","audio_timestamp":null,"suggested_revision":"studying history is not always necessary for solving future social problems","reason":"The response changes necessity into the stronger claim that history alone must solve the problem.","level":"must_fix","severity":"meaning_changing","task_specific":true,"opportunity_present":true,"historical_status":"new"}
{"event_id":"ERR-20260731-0002","attempt_id":"W-AD-20260731-001","taxonomy_version":1,"code":"DISCUSSION-BORROWING","source_excerpt":"history can be presented in a biased way","audio_timestamp":null,"suggested_revision":"Historical accounts can reflect the priorities of the people who preserved them, so decision-makers should compare them with current evidence.","reason":"The central reason closely follows Paul's post without enough independent development.","level":"should_fix","severity":"clarity_reducing","task_specific":true,"opportunity_present":true,"historical_status":"new"}
{"event_id":"ERR-20260731-0003","attempt_id":"W-AD-20260731-001","taxonomy_version":1,"code":"GRAM-ARTICLE","source_excerpt":"in a objected way","audio_timestamp":null,"suggested_revision":"in an objective way","reason":"A vowel sound requires `an`.","level":"should_fix","severity":"clarity_reducing","task_specific":false,"opportunity_present":true,"historical_status":"new"}
{"event_id":"ERR-20260731-0004","attempt_id":"W-AD-20260731-001","taxonomy_version":1,"code":"LEX-WORDFORM","source_excerpt":"in a objected way","audio_timestamp":null,"suggested_revision":"in an objective way","reason":"`Objected` is a verb form; the sentence requires the adjective `objective`.","level":"should_fix","severity":"clarity_reducing","task_specific":false,"opportunity_present":true,"historical_status":"new"}
{"event_id":"ERR-20260731-0005","attempt_id":"W-AD-20260731-001","taxonomy_version":1,"code":"GRAM-NEGATION","source_excerpt":"I do not think that it is not sufficient","audio_timestamp":null,"suggested_revision":"I do not think that it is sufficient","reason":"The double negative reverses the intended claim.","level":"must_fix","severity":"meaning_changing","task_specific":false,"opportunity_present":true,"historical_status":"new"}
{"event_id":"ERR-20260731-0006","attempt_id":"W-AD-20260731-001","taxonomy_version":1,"code":"GRAM-CLAUSE","source_excerpt":"although history can connect to some of the issues we are facing, but","audio_timestamp":null,"suggested_revision":"although history is connected to some issues we face, it","reason":"A concessive clause headed by `although` should not also be joined with `but`.","level":"should_fix","severity":"clarity_reducing","task_specific":false,"opportunity_present":true,"historical_status":"new"}
{"event_id":"ERR-20260731-0007","attempt_id":"W-AD-20260731-001","taxonomy_version":1,"code":"DISCUSSION-ELABORATION","source_excerpt":"modern issues like gender equality, A.I. governance","audio_timestamp":null,"suggested_revision":"AI governance involves rapidly changing systems, so policymakers also need current technical and legal expertise that historical cases cannot provide.","reason":"The examples are named without explaining the causal link to the claim.","level":"should_fix","severity":"clarity_reducing","task_specific":true,"opportunity_present":true,"historical_status":"new"}
```

- [ ] **Step 4: Validate the fixture through the writing gate**

Add this regression test to `tests/test_writing.py`:

```python
def test_historical_discussion_fixture_is_valid() -> None:
    import json
    from pathlib import Path

    import yaml

    from toefl_tracker.io import canonical_source_hash

    fixture = Path(__file__).parent / "fixtures/writing/history-discussion"
    attempt_data = yaml.safe_load((fixture / "attempt-input.yaml").read_text())
    prompt = (fixture / "prompt.md").read_text()
    response = (fixture / "response.md").read_text()
    attempt_data["source_hash"] = canonical_source_hash(prompt, response)
    event_data = [
        json.loads(line)
        for line in (fixture / "events.jsonl").read_text().splitlines()
        if line.strip()
    ]
    feedback = (fixture / "feedback.md").read_text()
    validate_writing_assessment(attempt_data, event_data, feedback)
```

Run: `python3 -m pytest tests/test_writing.py::test_historical_discussion_fixture_is_valid -v`

Expected: 1 test passes.

- [ ] **Step 5: Register and rebuild**

Run:

```bash
python3 tools/register_attempt.py --root . --attempt tests/fixtures/writing/history-discussion/attempt-input.yaml --prompt tests/fixtures/writing/history-discussion/prompt.md --response tests/fixtures/writing/history-discussion/response.md --feedback tests/fixtures/writing/history-discussion/feedback.md --events tests/fixtures/writing/history-discussion/events.jsonl
```

Expected: prints `tracker/writing/attempts/W-AD-20260731-001`.

Run: `python3 tools/rebuild_reports.py --root . --modality writing`

Expected: dashboard and profile are generated; no three-practice report is generated because this is formal writing attempt 1.

Run: `python3 tools/validate_tracker.py --root .`

Expected: exit 0.

- [ ] **Step 6: Commit the initial tracked attempt**

```bash
git add tests/fixtures/writing/history-discussion tests/test_writing.py tracker/writing
git commit -m "data: register initial writing practice"
```

## Writing Completion Check

- [ ] Run `python3 -m pytest -v` and record the exact pass count.
- [ ] Run `quick_validate.py` on `.agents/skills/toefl-writing-coach`.
- [ ] Run `python3 tools/rebuild_reports.py --root . --modality writing`.
- [ ] Run `python3 tools/validate_tracker.py --root .` and confirm exit 0.
- [ ] Inspect `tracker/writing/dashboard.csv` and confirm exactly one formal original.
- [ ] Run `git diff --check`.
- [ ] Confirm the writing skill's forward-test checklist is entirely passing.
