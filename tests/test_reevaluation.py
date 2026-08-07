import shutil
import sys
from pathlib import Path

import pytest
import yaml

from test_registration_gates import ROOT, WRITING_FEEDBACK
from test_validation import valid_attempt
from register_attempt import main as register_attempt_main
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


def _reevaluation(
    original: dict,
    attempt_id: str,
    evaluated_at: str,
    supersedes_evaluation_id: str,
) -> dict:
    return {
        **original,
        "schema_version": 2,
        "attempt_id": attempt_id,
        "record_type": "re_evaluation",
        "parent_attempt_id": original["attempt_id"],
        "evaluated_at": evaluated_at,
        "supersedes_evaluation_id": supersedes_evaluation_id,
        "task_score": {"scale": "0-5", "value": 4, "confidence": "medium"},
    }


def _publish_reevaluation(tmp_path: Path, manifest: dict, attempt: dict) -> None:
    publish_registration(
        tmp_path,
        manifest,
        build_reevaluation_registration(tmp_path, manifest, attempt, WRITING_FEEDBACK),
    )


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


def test_reevaluation_lineage_requires_the_immediate_predecessor(tmp_path: Path) -> None:
    manifest = yaml.safe_load((ROOT / "standards/ets-2026/manifest.yaml").read_text())
    original = _original(tmp_path, manifest)
    original_evaluation = f"{original['attempt_id']}@{original['rubric_version']}"
    e1 = _reevaluation(original, "W-AD-20260731-001-E1", "2026-08-02T09:00:00+08:00", original_evaluation)
    _publish_reevaluation(tmp_path, manifest, e1)
    e2 = _reevaluation(
        original,
        "W-AD-20260731-001-E2",
        "2026-08-02T10:00:00+08:00",
        f"{e1['attempt_id']}@{e1['rubric_version']}",
    )
    _publish_reevaluation(tmp_path, manifest, e2)
    e3 = _reevaluation(
        original,
        "W-AD-20260731-001-E3",
        "2026-08-02T11:00:00+08:00",
        f"{e2['attempt_id']}@{e2['rubric_version']}",
    )

    _publish_reevaluation(tmp_path, manifest, e3)


@pytest.mark.parametrize("supersedes", ["original", "nonlatest"])
def test_reevaluation_rejects_lineage_rewind_or_branch(
    tmp_path: Path, supersedes: str
) -> None:
    manifest = yaml.safe_load((ROOT / "standards/ets-2026/manifest.yaml").read_text())
    original = _original(tmp_path, manifest)
    original_evaluation = f"{original['attempt_id']}@{original['rubric_version']}"
    e1 = _reevaluation(original, "W-AD-20260731-001-E1", "2026-08-02T09:00:00+08:00", original_evaluation)
    _publish_reevaluation(tmp_path, manifest, e1)
    e2 = _reevaluation(
        original,
        "W-AD-20260731-001-E2",
        "2026-08-02T10:00:00+08:00",
        f"{e1['attempt_id']}@{e1['rubric_version']}",
    )
    _publish_reevaluation(tmp_path, manifest, e2)
    e3 = _reevaluation(
        original,
        "W-AD-20260731-001-E3",
        "2026-08-02T11:00:00+08:00",
        original_evaluation if supersedes == "original" else f"{e1['attempt_id']}@{e1['rubric_version']}",
    )

    with pytest.raises(ValidationError, match="immediate predecessor"):
        _publish_reevaluation(tmp_path, manifest, e3)


def test_reevaluation_rejects_a_timestamp_before_its_predecessor(
    tmp_path: Path,
) -> None:
    manifest = yaml.safe_load((ROOT / "standards/ets-2026/manifest.yaml").read_text())
    original = _original(tmp_path, manifest)
    e1 = _reevaluation(
        original,
        "W-AD-20260731-001-E1",
        "2026-08-02T10:00:00+08:00",
        f"{original['attempt_id']}@{original['rubric_version']}",
    )
    _publish_reevaluation(tmp_path, manifest, e1)
    backdated_e2 = _reevaluation(
        original,
        "W-AD-20260731-001-E2",
        "2026-08-02T09:00:00+08:00",
        f"{e1['attempt_id']}@{e1['rubric_version']}",
    )

    with pytest.raises(ValidationError, match="ordering key"):
        _publish_reevaluation(tmp_path, manifest, backdated_e2)


def _persist_schema_one_reevaluation(
    tmp_path: Path, original: dict, submitted_at: str
) -> dict:
    legacy = {
        **original,
        "schema_version": 1,
        "attempt_id": "W-AD-20260731-001-LEGACY",
        "record_type": "re_evaluation",
        "parent_attempt_id": original["attempt_id"],
        "submitted_at": submitted_at,
    }
    legacy.pop("evaluated_at", None)
    legacy.pop("supersedes_evaluation_id", None)
    directory = tmp_path / "tracker/writing/attempts" / legacy["attempt_id"]
    directory.mkdir()
    (directory / "attempt.yaml").write_text(yaml.safe_dump(legacy), encoding="utf-8")
    return legacy


def test_schema_one_history_uses_submitted_at_as_the_lineage_predecessor(
    tmp_path: Path,
) -> None:
    manifest = yaml.safe_load((ROOT / "standards/ets-2026/manifest.yaml").read_text())
    original = _original(tmp_path, manifest)
    legacy = _persist_schema_one_reevaluation(
        tmp_path, original, "2026-08-01T10:00:00+08:00"
    )
    successor = _reevaluation(
        original,
        "W-AD-20260731-001-E2",
        "2026-08-02T10:00:00+08:00",
        f"{legacy['attempt_id']}@{legacy['rubric_version']}",
    )

    _publish_reevaluation(tmp_path, manifest, successor)


def test_schema_one_history_with_invalid_submitted_at_is_a_validation_error(
    tmp_path: Path,
) -> None:
    manifest = yaml.safe_load((ROOT / "standards/ets-2026/manifest.yaml").read_text())
    original = _original(tmp_path, manifest)
    legacy = _persist_schema_one_reevaluation(tmp_path, original, "not-a-timestamp")
    successor = _reevaluation(
        original,
        "W-AD-20260731-001-E2",
        "2026-08-02T10:00:00+08:00",
        f"{legacy['attempt_id']}@{legacy['rubric_version']}",
    )

    with pytest.raises(ValidationError, match="legacy re-evaluation submitted_at"):
        _publish_reevaluation(tmp_path, manifest, successor)


def test_generic_cli_publishes_schema_two_reevaluation_without_source_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copytree(ROOT / "standards", tmp_path / "standards")
    manifest = yaml.safe_load((tmp_path / "standards/ets-2026/manifest.yaml").read_text())
    original = _original(tmp_path, manifest)
    reevaluation = _reevaluation(
        original,
        "W-AD-20260731-001-E1",
        "2026-08-02T09:00:00+08:00",
        f"{original['attempt_id']}@{original['rubric_version']}",
    )
    attempt_path = tmp_path / "reevaluation.yaml"
    feedback_path = tmp_path / "feedback.md"
    attempt_path.write_text(yaml.safe_dump(reevaluation), encoding="utf-8")
    feedback_path.write_text(WRITING_FEEDBACK, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "register_attempt.py", "--root", str(tmp_path), "--attempt", str(attempt_path),
        "--feedback", str(feedback_path),
    ])

    assert register_attempt_main() == 0

    destination = tmp_path / "tracker/writing/attempts/W-AD-20260731-001-E1"
    assert {path.name for path in destination.iterdir()} == {
        "attempt.yaml", "feedback-round-1.md", "events.jsonl"
    }
    assert read_yaml(destination / "attempt.yaml")["source_hash"] == original["source_hash"]
    assert (destination / "events.jsonl").read_text(encoding="utf-8") == ""
