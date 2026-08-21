import pytest

from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.writing import register_writing_attempt, validate_writing_assessment


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


def test_completed_revision_requires_naturalness_follow_up() -> None:
    row = attempt("email", "ets-writing-email-2025-applicable-2026")
    row["record_type"] = "revision"
    row["revision_outcomes"] = {
        "assigned": 1,
        "resolved": 1,
        "partly_resolved": 0,
        "unresolved": 0,
        "new_errors": 0,
        "resolution_rate": 1.0,
    }
    feedback = VALID_FEEDBACK + """# Targeted drill
Drill status: `skipped`.
Reason: All targets were resolved before the third revision.
"""
    with pytest.raises(ValidationError, match="requires naturalness follow-up"):
        validate_writing_assessment(row, [], feedback)


def test_incomplete_revision_must_not_enter_follow_up() -> None:
    row = attempt("email", "ets-writing-email-2025-applicable-2026")
    row["record_type"] = "revision"
    row["revision_outcomes"] = {
        "assigned": 2,
        "resolved": 1,
        "partly_resolved": 1,
        "unresolved": 0,
        "new_errors": 0,
        "resolution_rate": 0.5,
    }
    feedback = VALID_FEEDBACK + """# Targeted drill
Drill status: `not_required_yet`.
Reason: The third revision gate has not been reached.
# Naturalness and precision follow-up
No naturalness or precision issue to flag.
"""
    with pytest.raises(ValidationError, match="must not enter"):
        validate_writing_assessment(row, [], feedback)


def test_revision_with_new_errors_must_separate_them_from_assigned_targets() -> None:
    row = attempt("email", "ets-writing-email-2025-applicable-2026")
    row["record_type"] = "revision"
    row["revision_outcomes"] = {
        "assigned": 2,
        "resolved": 1,
        "partly_resolved": 1,
        "unresolved": 0,
        "new_errors": 1,
        "resolution_rate": 0.5,
    }
    feedback = VALID_FEEDBACK + """# Targeted drill
Drill status: `not_required_yet`.
Reason: The third revision gate has not been reached.
"""

    with pytest.raises(ValidationError, match="separate new issues"):
        validate_writing_assessment(row, [], feedback)

    separated = feedback.replace(
        "# Priorities",
        "## New issues (not assigned targets)\n- `a new issue` is recorded separately.\n# Priorities",
    )
    validate_writing_assessment(row, [], separated)


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


def test_counted_excerpt_must_be_in_the_evidence_section_not_only_elsewhere() -> None:
    row = attempt(
        "academic_discussion", "ets-writing-discussion-2025-applicable-2026"
    )
    event = {"event_id": "ERR-1", "level": "must_fix", "source_excerpt": "a object"}
    feedback = VALID_FEEDBACK.replace(
        "Evidence.\n# Why not", "Evidence includes a object.\n# Why not"
    ).replace("| a object | should_fix |", "| omitted | should_fix |")

    with pytest.raises(ValidationError, match="evidence section"):
        validate_writing_assessment(row, [event], feedback)


@pytest.mark.parametrize(
    "feedback",
    [
        VALID_FEEDBACK.replace("# Evidence\n", ""),
        VALID_FEEDBACK.replace(
            "# Evidence\n",
            "# Evidence\n# Evidence\n",
            1,
        ),
        VALID_FEEDBACK.replace(
            "# Why this level",
            "# TEMPORARY",
        )
        .replace(
            "# Why not the next level",
            "# Why this level",
        )
        .replace(
            "# TEMPORARY",
            "# Why not the next level",
        ),
        VALID_FEEDBACK.replace("# Result", "Embedded prose: # Result"),
    ],
    ids=["missing", "duplicate", "wrong-order", "embedded-prose"],
)
def test_required_headings_must_be_unique_ordered_markdown_headings(
    feedback: str,
) -> None:
    row = attempt(
        "academic_discussion",
        "ets-writing-discussion-2025-applicable-2026",
    )
    with pytest.raises(ValidationError, match="headings"):
        validate_writing_assessment(row, [], feedback)


@pytest.mark.parametrize("row", [None, [], "attempt"])
def test_attempt_must_be_a_mapping(row: object) -> None:
    with pytest.raises(ValidationError, match="attempt"):
        validate_writing_assessment(row, [], VALID_FEEDBACK)


@pytest.mark.parametrize("event", [None, [], "event"])
def test_each_event_must_be_a_mapping(event: object) -> None:
    row = attempt(
        "academic_discussion",
        "ets-writing-discussion-2025-applicable-2026",
    )
    with pytest.raises(ValidationError, match="event"):
        validate_writing_assessment(row, [event], VALID_FEEDBACK)


def test_polish_event_does_not_require_counted_evidence() -> None:
    row = attempt(
        "academic_discussion",
        "ets-writing-discussion-2025-applicable-2026",
    )
    event = {
        "event_id": "ERR-OPTIONAL",
        "level": "polish",
        "source_excerpt": "",
    }
    validate_writing_assessment(row, [event], VALID_FEEDBACK)


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


def test_feedback_result_must_match_the_persisted_simulated_task_score() -> None:
    row = attempt(
        "academic_discussion", "ets-writing-discussion-2025-applicable-2026"
    )
    with pytest.raises(ValidationError, match="matching simulated task score"):
        validate_writing_assessment(
            row, [], VALID_FEEDBACK.replace("3/5", "4/5")
        )


def test_writing_registration_refreshes_all_derived_coaching_views(tmp_path) -> None:
    from test_validation import MANIFEST, valid_attempt

    attempt_data = valid_attempt()
    attempt_data["source_hash"] = canonical_source_hash("prompt", "response")

    register_writing_attempt(
        tmp_path, MANIFEST, attempt_data, "prompt", "response", VALID_FEEDBACK, []
    )

    assert (tmp_path / "tracker/writing/dashboard.csv").exists()
    assert (tmp_path / "tracker/writing/training-plan.md").exists()
    assert (tmp_path / "tracker/writing/progress-overview.md").exists()
    assert (tmp_path / "tracker/writing/practice-queue.md").exists()
    assert (tmp_path / "tracker/writing/revision-learning.md").exists()
