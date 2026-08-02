from pathlib import Path

import pytest
import yaml

from test_registration_gates import ROOT, WRITING_FEEDBACK
from test_validation import valid_attempt
from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.register import publish_registration
from toefl_tracker.writing import (
    build_reevaluation_registration,
    build_writing_registration,
)


def _original(tmp_path: Path, manifest: dict) -> dict:
    attempt = valid_attempt()
    prompt = "Prompt"
    response = "A response"
    attempt["source_hash"] = canonical_source_hash(prompt, response)
    published = publish_registration(
        tmp_path, manifest,
        build_writing_registration(
            tmp_path, manifest, attempt, prompt, response, WRITING_FEEDBACK, []
        ),
    )
    return read_yaml(published / "attempt.yaml")


def test_schema_two_reevaluation_links_without_copying_source(tmp_path: Path) -> None:
    manifest = yaml.safe_load((ROOT / "standards/ets-2026/manifest.yaml").read_text())
    original = _original(tmp_path, manifest)
    reevaluation = {
        **original,
        "schema_version": 2,
        "attempt_id": "W-AD-20260731-001-E2",
        "record_type": "re_evaluation",
        "parent_attempt_id": original["attempt_id"],
        "evaluated_at": "2026-08-02T10:00:00+08:00",
        "supersedes_evaluation_id": (
            f"{original['attempt_id']}@{original['rubric_version']}"
        ),
        "rubric_version": original["rubric_version"],
        "task_score": {"scale": "0-5", "value": 4, "confidence": "medium"},
    }

    destination = publish_registration(
        tmp_path, manifest,
        build_reevaluation_registration(tmp_path, manifest, reevaluation, WRITING_FEEDBACK),
    )

    assert not (destination / "prompt.md").exists()
    assert not (destination / "response-original.md").exists()
    assert (destination / "events.jsonl").read_text(encoding="utf-8") == ""
    assert read_yaml(destination / "attempt.yaml")["source_hash"] == original["source_hash"]


@pytest.mark.parametrize("field", ["evaluated_at", "supersedes_evaluation_id"])
def test_reevaluation_requires_schema_two_versioned_fields(tmp_path: Path, field: str) -> None:
    manifest = yaml.safe_load((ROOT / "standards/ets-2026/manifest.yaml").read_text())
    original = _original(tmp_path, manifest)
    reevaluation = {
        **original,
        "schema_version": 2,
        "attempt_id": "W-AD-20260731-001-E2",
        "record_type": "re_evaluation",
        "parent_attempt_id": original["attempt_id"],
        "evaluated_at": "2026-08-02T10:00:00+08:00",
        "supersedes_evaluation_id": f"{original['attempt_id']}@{original['rubric_version']}",
    }
    del reevaluation[field]

    with pytest.raises(ValidationError, match=field):
        build_reevaluation_registration(tmp_path, manifest, reevaluation, WRITING_FEEDBACK)


def test_reevaluation_rejects_a_changed_source_hash(tmp_path: Path) -> None:
    manifest = yaml.safe_load((ROOT / "standards/ets-2026/manifest.yaml").read_text())
    original = _original(tmp_path, manifest)
    reevaluation = {
        **original,
        "schema_version": 2,
        "attempt_id": "W-AD-20260731-001-E2",
        "record_type": "re_evaluation",
        "parent_attempt_id": original["attempt_id"],
        "evaluated_at": "2026-08-02T10:00:00+08:00",
        "supersedes_evaluation_id": f"{original['attempt_id']}@{original['rubric_version']}",
        "source_hash": canonical_source_hash("different", "evidence"),
    }

    with pytest.raises(ValidationError, match="source_hash"):
        build_reevaluation_registration(tmp_path, manifest, reevaluation, WRITING_FEEDBACK)
