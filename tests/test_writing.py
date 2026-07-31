import pytest

from toefl_tracker.models import ValidationError
from toefl_tracker.writing import validate_writing_assessment


def attempt(task_type: str, rubric: str) -> dict:
    return {
        "modality": "writing",
        "task_type": task_type,
        "rubric_version": rubric,
        "task_score": {
            "scale": "0-5",
            "value": 3,
            "confidence": "medium",
        },
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
    row = attempt(
        "academic_discussion",
        "ets-writing-discussion-2025-applicable-2026",
    )
    validate_writing_assessment(row, [], VALID_FEEDBACK)


def test_email_requires_email_rubric() -> None:
    row = attempt("email", "ets-writing-email-2025-applicable-2026")
    validate_writing_assessment(row, [], VALID_FEEDBACK)


def test_email_cannot_use_discussion_rubric() -> None:
    row = attempt(
        "email",
        "ets-writing-discussion-2025-applicable-2026",
    )
    with pytest.raises(ValidationError, match="rubric"):
        validate_writing_assessment(row, [], VALID_FEEDBACK)


def test_unknown_writing_route_is_rejected() -> None:
    row = attempt(
        "discussion",
        "ets-writing-discussion-2025-applicable-2026",
    )
    with pytest.raises(ValidationError, match="rubric"):
        validate_writing_assessment(row, [], VALID_FEEDBACK)


def test_more_than_three_priorities_is_rejected() -> None:
    feedback = VALID_FEEDBACK.replace(
        "1. Fix article selection.",
        "1. One\n2. Two\n3. Three\n4. Four",
    )
    row = attempt(
        "academic_discussion",
        "ets-writing-discussion-2025-applicable-2026",
    )
    with pytest.raises(ValidationError, match="three priorities"):
        validate_writing_assessment(row, [], feedback)


def test_boolean_task_score_is_rejected() -> None:
    row = attempt(
        "academic_discussion",
        "ets-writing-discussion-2025-applicable-2026",
    )
    row["task_score"]["value"] = True
    with pytest.raises(ValidationError, match="task score"):
        validate_writing_assessment(row, [], VALID_FEEDBACK)


@pytest.mark.parametrize("excerpt", ["", "   ", {"text": "a object"}])
def test_counted_event_requires_nonempty_string_excerpt(
    excerpt: object,
) -> None:
    row = attempt(
        "academic_discussion",
        "ets-writing-discussion-2025-applicable-2026",
    )
    event = {
        "event_id": "ERR-1",
        "level": "should_fix",
        "source_excerpt": excerpt,
    }
    with pytest.raises(ValidationError, match="evidence"):
        validate_writing_assessment(row, [event], VALID_FEEDBACK)


def test_feedback_must_include_each_counted_excerpt() -> None:
    row = attempt(
        "academic_discussion",
        "ets-writing-discussion-2025-applicable-2026",
    )
    event = {
        "event_id": "ERR-1",
        "level": "must_fix",
        "source_excerpt": "missing sentence",
    }
    with pytest.raises(ValidationError, match="evidence"):
        validate_writing_assessment(row, [event], VALID_FEEDBACK)
