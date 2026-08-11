from pathlib import Path

import pytest

from test_validation import MANIFEST, valid_attempt
from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.mastery import derive_mastery, write_mastery
from toefl_tracker.models import ValidationError
from toefl_tracker.validation import validate_attempt
from toefl_tracker.writing import register_writing_attempt


def drill_attempt(attempt_id: str = "W-DRILL-20260807-001") -> dict:
    attempt = valid_attempt()
    attempt.update(
        {
            "attempt_id": attempt_id,
            "record_type": "targeted_drill",
            "submitted_at": "2026-08-07T10:00:00+08:00",
            "timed": False,
            "duration_seconds": 180,
            "word_count": 42,
            "task_score": None,
            "task_metrics": {},
            "source_hash": canonical_source_hash("drill prompt", "drill response"),
            "opportunities": {"GRAM-CLAUSE": 8},
            "parent_attempt_id": None,
            "revision_outcomes": None,
            "drill": {
                "set_id": "clause-set-01",
                "target_codes": ["GRAM-CLAUSE"],
                "item_count": 8,
                "correct_count": 7,
                "source_attempt_ids": ["W-AD-20260805-001"],
            },
        }
    )
    return attempt


def test_targeted_drill_is_not_a_scored_formal_attempt() -> None:
    validate_attempt(drill_attempt(), MANIFEST)


def test_targeted_drill_requires_bounded_performance_metadata() -> None:
    attempt = drill_attempt()
    attempt["drill"]["correct_count"] = 9
    with pytest.raises(ValidationError, match="correct_count"):
        validate_attempt(attempt, MANIFEST)


def test_targeted_drill_requires_complete_inline_transfer_lineage() -> None:
    attempt = drill_attempt()
    attempt["drill"].update(
        {
            "drill_pack_id": "WD-0000000000000001",
            "recommendation_id": "PLAN-W-SOURCE-001",
            "minimum_accuracy": 0.8,
        }
    )

    with pytest.raises(ValidationError, match="inline transfer lineage is incomplete"):
        validate_attempt(attempt, MANIFEST)

    attempt["drill"].update(
        {
            "source_prompt_hash": "sha256:" + "0" * 64,
            "pack_version": 9,
            "artifact_retention": "result_only",
            "code_results": [
                {
                    "code": "GRAM-CLAUSE",
                    "item_count": 8,
                    "correct_count": 7,
                    "partial_count": 0,
                }
            ],
        }
    )
    validate_attempt(attempt, MANIFEST)


def test_targeted_drill_preserves_per_item_partial_results() -> None:
    attempt = drill_attempt()
    attempt["drill"]["item_results"] = [
        {
            "item_id": f"I{index:02d}",
            "status": "meets_target" if index <= 6 else "partially_meets_target" if index == 7 else "needs_revision",
            "reason": "Fixture assessment evidence.",
        }
        for index in range(1, 9)
    ]
    attempt["drill"]["correct_count"] = 6

    validate_attempt(attempt, MANIFEST)

    attempt["drill"]["correct_count"] = 7
    with pytest.raises(ValidationError, match="match meets_target"):
        validate_attempt(attempt, MANIFEST)


def test_targeted_drill_registration_persists_without_formal_score(tmp_path: Path) -> None:
    attempt = drill_attempt()
    destination = register_writing_attempt(
        tmp_path,
        MANIFEST,
        attempt,
        "drill prompt",
        "drill response",
        "Targeted practice.",
        [],
    )
    persisted = read_yaml(destination / "attempt.yaml")
    assert persisted["record_type"] == "targeted_drill"
    assert persisted["task_score"] is None
    assert not list((tmp_path / "tracker/writing/reports").glob("*.md"))


def test_mastery_uses_per_code_drill_accuracy_when_available(tmp_path: Path) -> None:
    import yaml

    attempt = drill_attempt("W-DRILL-PER-CODE")
    attempt["drill"] = {
        "set_id": "mixed-set",
        "target_codes": ["GRAM-CLAUSE", "GRAM-AGREEMENT"],
        "item_count": 10,
        "correct_count": 8,
        "source_attempt_ids": ["W-AD-20260805-001"],
        "code_results": [
            {"code": "GRAM-CLAUSE", "item_count": 8, "correct_count": 8, "partial_count": 0},
            {"code": "GRAM-AGREEMENT", "item_count": 2, "correct_count": 0, "partial_count": 0},
        ],
    }
    directory = tmp_path / "tracker/writing/attempts/W-DRILL-PER-CODE"
    directory.mkdir(parents=True)
    (directory / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
    (directory / "events.jsonl").write_text("", encoding="utf-8")

    mastery = derive_mastery(tmp_path)

    assert mastery["GRAM-CLAUSE"]["drill_accuracy"] == 1.0
    assert mastery["GRAM-AGREEMENT"]["drill_accuracy"] == 0.0


def _persist_formal(root: Path, attempt_id: str, submitted_at: str, events: list[dict]) -> None:
    original = valid_attempt()
    original.update(
        {
            "attempt_id": attempt_id,
            "submitted_at": submitted_at,
            "source_hash": canonical_source_hash(attempt_id, attempt_id + " response"),
        }
    )
    directory = root / "tracker/writing/attempts" / attempt_id
    directory.mkdir(parents=True, exist_ok=True)
    import yaml

    (directory / "attempt.yaml").write_text(yaml.safe_dump(original), encoding="utf-8")
    (directory / "prompt.md").write_text(attempt_id, encoding="utf-8")
    (directory / "response-original.md").write_text(attempt_id + " response", encoding="utf-8")
    (directory / "feedback-round-1.md").write_text("feedback", encoding="utf-8")
    from toefl_tracker.canonical import canonical_jsonl

    (directory / "events.jsonl").write_text(canonical_jsonl(events), encoding="utf-8")


def _event(attempt_id: str, code: str = "GRAM-CLAUSE") -> dict:
    return {
        "event_id": f"E-{attempt_id}",
        "attempt_id": attempt_id,
        "taxonomy_version": 1,
        "code": code,
        "source_excerpt": "bad clause",
        "audio_timestamp": None,
        "suggested_revision": "correct clause",
        "reason": "clause boundary",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }


def test_mastery_progresses_from_drills_to_transfer_and_can_relapse(tmp_path: Path) -> None:
    import yaml

    standards = Path(__file__).parents[1] / "standards"
    import shutil

    shutil.copytree(standards, tmp_path / "standards")
    for index in range(1, 4):
        attempt = drill_attempt(f"W-DRILL-20260807-00{index}")
        attempt["submitted_at"] = f"2026-08-07T10:0{index}:00+08:00"
        attempt["drill"] = {
            "set_id": f"clause-set-0{index}",
            "target_codes": ["GRAM-CLAUSE"],
            "item_count": 8,
            "correct_count": 7,
            "source_attempt_ids": ["W-AD-20260805-001"],
        }
        directory = tmp_path / "tracker/writing/attempts" / attempt["attempt_id"]
        directory.mkdir(parents=True)
        (directory / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
        (directory / "events.jsonl").write_text("", encoding="utf-8")
        (directory / "feedback-round-1.md").write_text("drill", encoding="utf-8")
        (directory / "prompt.md").write_text("drill", encoding="utf-8")
        (directory / "response-original.md").write_text("drill", encoding="utf-8")
    for index in range(1, 4):
        _persist_formal(
            tmp_path,
            f"W-FORMAL-{index}",
            f"2026-08-0{index}T10:00:00+08:00",
            [],
        )
        attempt = read_yaml(tmp_path / "tracker/writing/attempts" / f"W-FORMAL-{index}" / "attempt.yaml")
        attempt["opportunities"] = {"GRAM-CLAUSE": 1}
        (tmp_path / "tracker/writing/attempts" / f"W-FORMAL-{index}" / "attempt.yaml").write_text(
            yaml.safe_dump(attempt), encoding="utf-8"
        )
    mastery = derive_mastery(tmp_path)
    # Pre-drill formal records are not transfer evidence; a future new-prompt
    # formal attempt must carry explicit transfer metadata.
    assert mastery["GRAM-CLAUSE"]["status"] == "provisional"
    for index in range(4, 6):
        _persist_formal(tmp_path, f"W-FORMAL-{index}", f"2026-08-0{index}T10:00:00+08:00", [])
        attempt = read_yaml(tmp_path / "tracker/writing/attempts" / f"W-FORMAL-{index}" / "attempt.yaml")
        attempt["opportunities"] = {"GRAM-CLAUSE": 1}
        (tmp_path / "tracker/writing/attempts" / f"W-FORMAL-{index}" / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
    _persist_formal(tmp_path, "W-FORMAL-6", "2026-08-06T10:00:00+08:00", [_event("W-FORMAL-6")])
    attempt = read_yaml(tmp_path / "tracker/writing/attempts/W-FORMAL-6/attempt.yaml")
    attempt["opportunities"] = {"GRAM-CLAUSE": 1}
    (tmp_path / "tracker/writing/attempts/W-FORMAL-6/attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
    assert derive_mastery(tmp_path)["GRAM-CLAUSE"]["status"] == "provisional"
    path = write_mastery(tmp_path)
    assert path.exists()
    assert "GRAM-CLAUSE" in path.read_text(encoding="utf-8")


def test_mastery_reports_partial_drill_items(tmp_path: Path) -> None:
    attempt = drill_attempt()
    attempt["drill"]["item_results"] = [
        {
            "item_id": f"I{index:02d}",
            "status": "partially_meets_target" if index <= 2 else "needs_revision",
            "reason": "Fixture assessment evidence.",
        }
        for index in range(1, 9)
    ]
    attempt["drill"]["correct_count"] = 0
    directory = tmp_path / "tracker/writing/attempts" / attempt["attempt_id"]
    directory.mkdir(parents=True)
    import yaml

    (directory / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
    (directory / "events.jsonl").write_text("", encoding="utf-8")
    mastery = derive_mastery(tmp_path)

    assert mastery["GRAM-CLAUSE"]["drill_partial_items"] == 2
