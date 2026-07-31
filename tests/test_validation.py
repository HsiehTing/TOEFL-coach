from pathlib import Path

import pytest
import yaml

from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.validation import validate_attempt, validate_error_event


MANIFEST = yaml.safe_load(
    (Path(__file__).parents[1] / "standards/ets-2026/manifest.yaml").read_text()
)


def valid_attempt() -> dict:
    return {
        "schema_version": 1,
        "attempt_id": "W-AD-20260731-001",
        "modality": "writing",
        "task_type": "academic_discussion",
        "record_type": "formal_original",
        "submitted_at": "2026-07-31T10:00:00+08:00",
        "practiced_at": None,
        "timed": True,
        "duration_seconds": 600,
        "assistance": {"spellcheck": False, "translation": False, "other": None},
        "word_count": 120,
        "rubric_version": "ets-writing-discussion-2025-applicable-2026",
        "standard_verified_at": "2026-07-31",
        "task_score": {"scale": "0-5", "value": 3, "confidence": "medium"},
        "task_metrics": {"prompt_alignment": "partial", "elaboration": "partial"},
        "source_hash": canonical_source_hash("prompt", "response"),
        "opportunities": {"GRAM-NEGATION": 1},
        "parent_attempt_id": None,
        "revision_outcomes": None,
    }


def test_valid_attempt_is_accepted() -> None:
    validate_attempt(valid_attempt(), MANIFEST)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("record_type", "draft"),
        ("task_type", "listen_and_repeat"),
        ("rubric_version", "invented-rubric"),
        ("opportunities", {"GRAM-NEGATION": -1}),
    ],
)
def test_invalid_attempt_fields_are_rejected(field: str, value: object) -> None:
    attempt = valid_attempt()
    attempt[field] = value
    with pytest.raises(ValidationError):
        validate_attempt(attempt, MANIFEST)


def test_counted_event_requires_traceable_evidence() -> None:
    event = {
        "event_id": "ERR-20260731-0001",
        "attempt_id": "W-AD-20260731-001",
        "taxonomy_version": 1,
        "code": "GRAM-NEGATION",
        "source_excerpt": "",
        "audio_timestamp": None,
        "suggested_revision": "I do not think it is sufficient.",
        "reason": "Double negative changes the claim.",
        "level": "must_fix",
        "severity": "meaning_changing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }
    with pytest.raises(ValidationError, match="evidence"):
        validate_error_event(event)


def test_revision_outcomes_must_reconcile() -> None:
    attempt = valid_attempt()
    attempt["record_type"] = "revision"
    attempt["parent_attempt_id"] = "W-AD-20260730-001"
    attempt["revision_outcomes"] = {
        "assigned": 3,
        "resolved": 2,
        "partly_resolved": 1,
        "unresolved": 0,
        "new_errors": 1,
        "resolution_rate": 0.5,
    }
    with pytest.raises(ValidationError, match="resolution_rate"):
        validate_attempt(attempt, MANIFEST)


def valid_error_event() -> dict:
    return {
        "event_id": "ERR-20260731-0001",
        "attempt_id": "W-AD-20260731-001",
        "taxonomy_version": 1,
        "code": "GRAM-NEGATION",
        "source_excerpt": "I do not think it is sufficient.",
        "audio_timestamp": None,
        "suggested_revision": "I think it is insufficient.",
        "reason": "Double negative changes the claim.",
        "level": "must_fix",
        "severity": "meaning_changing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }


@pytest.mark.parametrize("value", [True, 2])
def test_schema_version_must_be_exact_integer_one(value: object) -> None:
    attempt = valid_attempt()
    attempt["schema_version"] = value
    with pytest.raises(ValidationError, match="schema_version"):
        validate_attempt(attempt, MANIFEST)


@pytest.mark.parametrize("value", [True, 2])
def test_taxonomy_version_must_be_exact_integer_one(value: object) -> None:
    event = valid_error_event()
    event["taxonomy_version"] = value
    with pytest.raises(ValidationError, match="taxonomy_version"):
        validate_error_event(event)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("word_count", True),
        ("duration_seconds", True),
        ("opportunities", {"GRAM-NEGATION": True}),
    ],
)
def test_attempt_counts_reject_boolean_values(field: str, value: object) -> None:
    attempt = valid_attempt()
    attempt[field] = value
    with pytest.raises(ValidationError):
        validate_attempt(attempt, MANIFEST)


def test_writing_score_rejects_boolean_value() -> None:
    attempt = valid_attempt()
    attempt["task_score"]["value"] = True
    with pytest.raises(ValidationError, match="task_score"):
        validate_attempt(attempt, MANIFEST)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("assigned", True),
        ("assigned", -1),
        ("resolved", -1),
        ("resolved", True),
        ("partly_resolved", True),
        ("partly_resolved", -1),
        ("unresolved", -1),
        ("unresolved", True),
        ("new_errors", -1),
        ("new_errors", True),
        ("resolution_rate", True),
    ],
)
def test_revision_outcomes_require_valid_numeric_types(field: str, value: object) -> None:
    attempt = valid_attempt()
    attempt["record_type"] = "revision"
    attempt["parent_attempt_id"] = "W-AD-20260730-001"
    attempt["revision_outcomes"] = {
        "assigned": 3,
        "resolved": 2,
        "partly_resolved": 1,
        "unresolved": 0,
        "new_errors": 1,
        "resolution_rate": 2 / 3,
    }
    attempt["revision_outcomes"][field] = value
    with pytest.raises(ValidationError):
        validate_attempt(attempt, MANIFEST)


@pytest.mark.parametrize(
    ("source_excerpt", "audio_timestamp"),
    [
        ({"excerpt": "not text"}, None),
        ("", True),
        ("", "12 seconds"),
    ],
)
def test_counted_event_evidence_requires_text_or_project_timestamp(
    source_excerpt: object, audio_timestamp: object
) -> None:
    event = valid_error_event()
    event["source_excerpt"] = source_excerpt
    event["audio_timestamp"] = audio_timestamp
    with pytest.raises(ValidationError, match="evidence"):
        validate_error_event(event)


@pytest.mark.parametrize("audio_timestamp", ["00:12", "00:12–00:15"])
def test_counted_event_accepts_project_audio_timestamp(audio_timestamp: str) -> None:
    event = valid_error_event()
    event["source_excerpt"] = ""
    event["audio_timestamp"] = audio_timestamp
    validate_error_event(event)
