from pathlib import Path

import pytest
import yaml

from toefl_tracker.models import ValidatedPracticeRegistration, ValidationError
from toefl_tracker.writing import validate_writing_revision_context
def _feedback(section: str) -> str:
    return """# Result
Simulated task score: 4/5
# Why this level
The request is clear.
# Why not the next level
Some wording can be more idiomatic.
# Evidence
| Evidence | Level |
| --- | --- |
| `The request is clear.` | polish |
# Priorities
1. Use direct, specific requests.
# Rewrite task
Use this control in a new prompt.
""" + section


def test_revision_follow_up_is_bounded_feedback_and_non_scoring(tmp_path: Path) -> None:
    response = "Students urgently need quieter study space. Students urgently need a quiet place before exams."
    feedback = _feedback("""# Naturalness and precision follow-up
1. Excerpt: `Students urgently need quieter study space`
   Reader effect: The repeated urgency can sound insistent rather than specific. Option: Students need a quieter place to study before final exams.
""")
    # The parent is not relevant to this focused artifact contract, so only
    # validate assessment-level feedback here.
    from toefl_tracker.writing import _validate_revision_follow_up
    _validate_revision_follow_up(feedback, response)


def test_revision_follow_up_is_required() -> None:
    from toefl_tracker.writing import _validate_revision_follow_up

    with pytest.raises(ValidationError, match="requires naturalness follow-up"):
        _validate_revision_follow_up(_feedback(""), "Learner text.")


def test_no_issue_follow_up_requires_audited_candidates() -> None:
    from toefl_tracker.writing import _validate_revision_follow_up

    feedback = _feedback("""# Naturalness and precision follow-up
No naturalness or precision issue to flag.
## Transfer suggestion
Use the same control on a new prompt.
""")
    with pytest.raises(ValidationError, match="naturalness audit"):
        _validate_revision_follow_up(feedback, "The request is clear and direct.")


def test_no_issue_follow_up_accepts_documented_audit() -> None:
    from toefl_tracker.writing import _validate_revision_follow_up

    response = "The request is clear and direct. The deadline is specific."
    feedback = _feedback("""# Naturalness and precision follow-up
No naturalness or precision issue to flag.
## Naturalness audit
1. Candidate: `The request is clear and direct.` — The wording is concise and idiomatic.
2. Candidate: `The deadline is specific.` — The reference is precise and needs no change.
## Transfer suggestion
Use the same control on a new prompt.
""")
    _validate_revision_follow_up(feedback, response)


def test_no_issue_follow_up_rejects_mini_practice() -> None:
    from toefl_tracker.writing import _validate_revision_follow_up

    response = "The request is clear and direct. The deadline is specific."
    feedback = _feedback("""# Naturalness and precision follow-up
No naturalness or precision issue to flag.
## Naturalness audit
1. Candidate: `The request is clear and direct.` — The wording is concise and idiomatic.
2. Candidate: `The deadline is specific.` — The reference is precise and needs no change.
## Transfer suggestion
Use the same control on a new prompt.
## Mini-practice
1. Rewrite the request.
""")

    with pytest.raises(ValidationError, match="must not contain mini-practice"):
        _validate_revision_follow_up(feedback, response)


def test_revision_follow_up_cannot_repeat_scored_evidence() -> None:
    from toefl_tracker.writing import _validate_revision_follow_up

    feedback = _feedback("""# Naturalness and precision follow-up
1. Excerpt: `The request is clear.`
   Reader effect: This repeats a scored issue rather than adding new guidance. Option: Use a clearer request.
""")
    with pytest.raises(ValidationError, match="must not repeat scored evidence"):
        _validate_revision_follow_up(feedback, "The request is clear.")


def test_revision_follow_up_cannot_repeat_parent_feedback() -> None:
    from toefl_tracker.writing import _validate_revision_follow_up

    feedback = _feedback("""# Naturalness and precision follow-up
1. Excerpt: `The committee name is unclear.`
   Reader effect: This repeats prior feedback rather than adding new guidance. Option: Use a precise committee name.
""")
    with pytest.raises(ValidationError, match="must not repeat parent feedback"):
        _validate_revision_follow_up(
            feedback,
            "The committee name is unclear.",
            parent_feedback="Prior evidence: The committee name is unclear.",
        )


@pytest.mark.parametrize("section, message", [
    ("# Naturalness and precision follow-up\n1. Excerpt: `missing text`\n", "learner text"),
    ("# Naturalness and precision follow-up\n1. Excerpt: `Students urgently need quieter study space`\n## Mini-practice\n1. One\n2. Two\n", "must not contain mini-practice"),
])
def test_revision_follow_up_rejects_invalid_excerpt_or_practice_prompt(section: str, message: str) -> None:
    from toefl_tracker.writing import _validate_revision_follow_up
    with pytest.raises(ValidationError, match=message):
        _validate_revision_follow_up(_feedback(section), "Students urgently need quieter study space.")


def _attempt(
    attempt_id: str,
    record_type: str,
    submitted_at: str,
    *,
    parent_attempt_id: str | None = None,
    resolved: bool = False,
) -> dict:
    return {
        "attempt_id": attempt_id,
        "modality": "writing",
        "task_type": "academic_discussion",
        "record_type": record_type,
        "submitted_at": submitted_at,
        "parent_attempt_id": parent_attempt_id,
        "revision_outcomes": (
            {
                "assigned": 2,
                "resolved": 2 if resolved else 1,
                "partly_resolved": 0 if resolved else 1,
                "unresolved": 0,
                "new_errors": 0,
                "resolution_rate": 1.0 if resolved else 0.5,
            }
            if record_type == "revision"
            else None
        ),
        "opportunities": {"GRAM-CLAUSE": 2, "GRAM-ARTICLE": 2},
    }


def _persist(root: Path, attempt: dict, feedback: str = "Prior feedback.") -> None:
    path = root / "tracker/writing/attempts" / attempt["attempt_id"]
    path.mkdir(parents=True)
    (path / "attempt.yaml").write_text(yaml.safe_dump(attempt, sort_keys=False))
    (path / "feedback-round-1.md").write_text(feedback)


def _registration(attempt: dict, feedback: str, response: str) -> ValidatedPracticeRegistration:
    return ValidatedPracticeRegistration(
        attempt=attempt,
        prompt="Prompt",
        response=response,
        feedback=feedback,
        events=(),
    )


def _base_feedback(drill: str, follow_up: str = "") -> str:
    return _feedback(f"# Targeted drill\n{drill}\n{follow_up}")


def _actionable_follow_up(excerpt: str) -> str:
    return f"""# Naturalness and precision follow-up
1. Excerpt: `{excerpt}`
   Reader effect: The phrase is understandable but indirect. Option: Workers need direct support.
"""


def test_round_one_completion_skips_drill_and_requires_follow_up(tmp_path: Path) -> None:
    root = _attempt("W-AD-001", "formal_original", "2026-08-01T10:00:00+08:00")
    _persist(tmp_path, root)
    response = "Workers need support after automation replaces their jobs."
    revision = _attempt(
        "W-AD-001-R1",
        "revision",
        "2026-08-02T10:00:00+08:00",
        parent_attempt_id=root["attempt_id"],
        resolved=True,
    )
    feedback = _base_feedback(
        "Drill status: `skipped`.\nReason: All targets were resolved before the third revision.",
        _actionable_follow_up(response),
    )

    validate_writing_revision_context(tmp_path, _registration(revision, feedback, response))


def test_round_two_completion_skips_drill_and_requires_follow_up(tmp_path: Path) -> None:
    root = _attempt("W-AD-001", "formal_original", "2026-08-01T10:00:00+08:00")
    round_one = _attempt(
        "W-AD-001-R1",
        "revision",
        "2026-08-02T10:00:00+08:00",
        parent_attempt_id=root["attempt_id"],
    )
    _persist(tmp_path, root)
    _persist(tmp_path, round_one)
    response = "Workers need support after automation replaces their jobs."
    round_two = _attempt(
        "W-AD-001-R2",
        "revision",
        "2026-08-03T10:00:00+08:00",
        parent_attempt_id=round_one["attempt_id"],
        resolved=True,
    )
    feedback = _base_feedback(
        "Drill status: `skipped`.\nReason: All targets were resolved before the third revision.",
        _actionable_follow_up(response),
    )

    validate_writing_revision_context(tmp_path, _registration(round_two, feedback, response))


def test_unresolved_round_two_requires_bounded_drill_and_blocks_follow_up(tmp_path: Path) -> None:
    root = _attempt("W-AD-001", "formal_original", "2026-08-01T10:00:00+08:00")
    round_one = _attempt(
        "W-AD-001-R1", "revision", "2026-08-02T10:00:00+08:00", parent_attempt_id=root["attempt_id"]
    )
    _persist(tmp_path, root)
    _persist(tmp_path, round_one)
    round_two = _attempt(
        "W-AD-001-R2", "revision", "2026-08-03T10:00:00+08:00", parent_attempt_id=round_one["attempt_id"]
    )
    feedback = _base_feedback("""Drill status: `required`.
Invitation: After reviewing the exact-excerpt feedback and bounded rewrite direction, learner was asked whether to start this targeted drill.
Decision: learner opted in after reviewing the rewrite direction.
Source: `W-AD-001`
Targets: `GRAM-CLAUSE`, `GRAM-ARTICLE`
Items: 6
Completion: Register the assessed drill before another revision.""")

    validate_writing_revision_context(
        tmp_path, _registration(round_two, feedback, "Workers need support.")
    )


def test_required_drill_requires_recorded_learner_opt_in(tmp_path: Path) -> None:
    root = _attempt("W-AD-001", "formal_original", "2026-08-01T10:00:00+08:00")
    round_one = _attempt(
        "W-AD-001-R1", "revision", "2026-08-02T10:00:00+08:00", parent_attempt_id=root["attempt_id"]
    )
    _persist(tmp_path, root)
    _persist(tmp_path, round_one)
    round_two = _attempt(
        "W-AD-001-R2", "revision", "2026-08-03T10:00:00+08:00", parent_attempt_id=round_one["attempt_id"]
    )
    feedback = _base_feedback("""Drill status: `required`.
Invitation: After reviewing the exact-excerpt feedback and bounded rewrite direction, learner was asked whether to start this targeted drill.
Source: `W-AD-001`
Targets: `GRAM-CLAUSE`, `GRAM-ARTICLE`
Items: 6
Completion: Register the assessed drill before another revision.""")

    with pytest.raises(ValidationError, match="record the learner opt-in"):
        validate_writing_revision_context(
            tmp_path, _registration(round_two, feedback, "Workers need support.")
        )


def test_required_drill_requires_recorded_guidance_invitation(tmp_path: Path) -> None:
    root = _attempt("W-AD-001", "formal_original", "2026-08-01T10:00:00+08:00")
    round_one = _attempt(
        "W-AD-001-R1", "revision", "2026-08-02T10:00:00+08:00", parent_attempt_id=root["attempt_id"]
    )
    _persist(tmp_path, root)
    _persist(tmp_path, round_one)
    round_two = _attempt(
        "W-AD-001-R2", "revision", "2026-08-03T10:00:00+08:00", parent_attempt_id=round_one["attempt_id"]
    )
    feedback = _base_feedback("""Drill status: `required`.
Decision: learner opted in after reviewing the rewrite direction.
Source: `W-AD-001`
Targets: `GRAM-CLAUSE`, `GRAM-ARTICLE`
Items: 6
Completion: Register the assessed drill before another revision.""")

    with pytest.raises(ValidationError, match="record the invitation"):
        validate_writing_revision_context(
            tmp_path, _registration(round_two, feedback, "Workers need support.")
        )


def test_unresolved_round_two_can_decline_drill_and_receive_follow_up(tmp_path: Path) -> None:
    root = _attempt("W-AD-001", "formal_original", "2026-08-01T10:00:00+08:00")
    round_one = _attempt(
        "W-AD-001-R1", "revision", "2026-08-02T10:00:00+08:00", parent_attempt_id=root["attempt_id"]
    )
    _persist(tmp_path, root)
    _persist(tmp_path, round_one)
    round_two = _attempt(
        "W-AD-001-R2", "revision", "2026-08-03T10:00:00+08:00", parent_attempt_id=round_one["attempt_id"]
    )
    response = "Workers need support after automation replaces their jobs."
    feedback = _base_feedback(
        "Drill status: `declined`.\nInvitation: After reviewing the exact-excerpt feedback and bounded rewrite direction, learner was asked whether to start this targeted drill.\nDecision: learner declined the targeted drill after receiving the bounded rewrite direction.",
        _actionable_follow_up(response),
    )

    validate_writing_revision_context(tmp_path, _registration(round_two, feedback, response))


def test_declined_drill_requires_recorded_learner_decision(tmp_path: Path) -> None:
    root = _attempt("W-AD-001", "formal_original", "2026-08-01T10:00:00+08:00")
    round_one = _attempt(
        "W-AD-001-R1", "revision", "2026-08-02T10:00:00+08:00", parent_attempt_id=root["attempt_id"]
    )
    _persist(tmp_path, root)
    _persist(tmp_path, round_one)
    round_two = _attempt(
        "W-AD-001-R2", "revision", "2026-08-03T10:00:00+08:00", parent_attempt_id=round_one["attempt_id"]
    )
    response = "Workers need support after automation replaces their jobs."
    feedback = _base_feedback(
        "Drill status: `declined`.\nInvitation: After reviewing the exact-excerpt feedback and bounded rewrite direction, learner was asked whether to start this targeted drill.",
        _actionable_follow_up(response),
    )

    with pytest.raises(ValidationError, match="record the learner decision"):
        validate_writing_revision_context(tmp_path, _registration(round_two, feedback, response))


def test_third_revision_is_rejected_without_completed_drill(tmp_path: Path) -> None:
    root = _attempt("W-AD-001", "formal_original", "2026-08-01T10:00:00+08:00")
    round_one = _attempt("W-AD-001-R1", "revision", "2026-08-02T10:00:00+08:00", parent_attempt_id=root["attempt_id"])
    round_two = _attempt("W-AD-001-R2", "revision", "2026-08-03T10:00:00+08:00", parent_attempt_id=round_one["attempt_id"])
    for row in (root, round_one, round_two):
        _persist(tmp_path, row)
    round_three = _attempt(
        "W-AD-001-R3", "revision", "2026-08-04T10:00:00+08:00", parent_attempt_id=round_two["attempt_id"], resolved=True
    )
    feedback = _base_feedback(
        "Drill status: `completed`.\nDrill attempt: `W-DRILL-001`",
        _actionable_follow_up("Workers need support."),
    )
    with pytest.raises(ValidationError, match="third revision requires"):
        validate_writing_revision_context(
            tmp_path, _registration(round_three, feedback, "Workers need support.")
        )


def test_completed_drill_unlocks_third_revision_follow_up(tmp_path: Path) -> None:
    root = _attempt("W-AD-001", "formal_original", "2026-08-01T10:00:00+08:00")
    round_one = _attempt("W-AD-001-R1", "revision", "2026-08-02T10:00:00+08:00", parent_attempt_id=root["attempt_id"])
    round_two = _attempt("W-AD-001-R2", "revision", "2026-08-03T10:00:00+08:00", parent_attempt_id=round_one["attempt_id"])
    drill = _attempt("W-DRILL-001", "targeted_drill", "2026-08-03T12:00:00+08:00")
    drill["drill"] = {
        "source_attempt_ids": [root["attempt_id"]],
        "item_count": 6,
        "correct_count": 5,
    }
    for row in (root, round_one, round_two, drill):
        _persist(tmp_path, row)
    response = "Workers need support after automation replaces their jobs."
    round_three = _attempt(
        "W-AD-001-R3", "revision", "2026-08-04T10:00:00+08:00", parent_attempt_id=round_two["attempt_id"], resolved=True
    )
    feedback = _base_feedback(
        "Drill status: `completed`.\nDrill attempt: `W-DRILL-001`",
        _actionable_follow_up(response),
    )

    validate_writing_revision_context(tmp_path, _registration(round_three, feedback, response))
