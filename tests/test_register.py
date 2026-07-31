import json
from pathlib import Path

import pytest

from test_validation import MANIFEST, valid_attempt
from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.register import register_attempt


def test_register_writes_immutable_attempt_and_events(tmp_path: Path) -> None:
    attempt = valid_attempt()
    attempt["source_hash"] = canonical_source_hash("prompt", "response")
    event = {
        "event_id": "ERR-20260731-0001",
        "attempt_id": attempt["attempt_id"],
        "taxonomy_version": 1,
        "code": "GRAM-NEGATION",
        "source_excerpt": "do not think it is not",
        "audio_timestamp": None,
        "suggested_revision": "do not think it is",
        "reason": "Double negative.",
        "level": "must_fix",
        "severity": "meaning_changing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }

    path = register_attempt(
        tmp_path, MANIFEST, attempt, "prompt", "response", "feedback", [event]
    )

    assert (path / "attempt.yaml").exists()
    assert (path / "prompt.md").read_text() == "prompt\n"
    assert (path / "response-original.md").read_text() == "response\n"
    rows = (tmp_path / "tracker/writing/error-events.jsonl").read_text().splitlines()
    assert json.loads(rows[0])["event_id"] == event["event_id"]


def test_duplicate_source_hash_is_rejected(tmp_path: Path) -> None:
    attempt = valid_attempt()
    attempt["source_hash"] = canonical_source_hash("prompt", "response")
    register_attempt(tmp_path, MANIFEST, attempt, "prompt", "response", "feedback", [])
    duplicate = {**attempt, "attempt_id": "W-AD-20260731-002"}

    with pytest.raises(ValidationError, match="duplicate"):
        register_attempt(
            tmp_path, MANIFEST, duplicate, "prompt", "response", "feedback", []
        )


def test_revision_uses_revision_filename_and_parent_link(tmp_path: Path) -> None:
    original = valid_attempt()
    register_attempt(tmp_path, MANIFEST, original, "prompt", "response", "feedback", [])
    revision = {
        **valid_attempt(),
        "attempt_id": "W-AD-20260731-001-R1",
        "record_type": "revision",
        "parent_attempt_id": original["attempt_id"],
        "revision_outcomes": {
            "assigned": 2,
            "resolved": 1,
            "partly_resolved": 1,
            "unresolved": 0,
            "new_errors": 0,
            "resolution_rate": 0.5,
        },
        "source_hash": canonical_source_hash("prompt", "revised response"),
    }

    path = register_attempt(
        tmp_path, MANIFEST, revision, "prompt", "revised response", "feedback", []
    )

    assert (path / "response-revision.md").read_text() == "revised response\n"
    assert not (path / "response-original.md").exists()
