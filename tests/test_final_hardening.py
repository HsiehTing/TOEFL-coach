from pathlib import Path

import pytest

from test_validation import MANIFEST, valid_attempt, valid_error_event
from toefl_tracker.models import ValidationError
from toefl_tracker.status import classify_code
from toefl_tracker.validation import validate_attempt, validate_error_event


def test_three_comparable_errors_are_persistent() -> None:
    attempts = [
        {"attempt_id": str(index), "record_type": "formal_original", "opportunities": {"GRAM-ARTICLE": 1}}
        for index in range(3)
    ]
    events = [
        {"attempt_id": str(index), "code": "GRAM-ARTICLE", "level": "must_fix", "severity": "minor"}
        for index in range(3)
    ]
    assert classify_code("GRAM-ARTICLE", attempts, events) == "persistent"


@pytest.mark.parametrize("invalid", [None, [], "attempt"])
def test_attempt_validator_rejects_non_mappings(invalid: object) -> None:
    with pytest.raises(ValidationError, match="mapping"):
        validate_attempt(invalid, MANIFEST)


@pytest.mark.parametrize("invalid", [None, [], "event"])
def test_event_validator_rejects_non_mappings(invalid: object) -> None:
    with pytest.raises(ValidationError, match="mapping"):
        validate_error_event(invalid)


def test_re_evaluation_is_a_non_cadence_record_type() -> None:
    attempt = valid_attempt()
    attempt["record_type"] = "re_evaluation"
    attempt["parent_attempt_id"] = "W-AD-20260730-001"
    validate_attempt(attempt, MANIFEST)

