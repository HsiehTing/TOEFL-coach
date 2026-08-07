from pathlib import Path

import yaml

from test_reports import write_attempt
from toefl_tracker.canonical import canonical_jsonl
from toefl_tracker.io import canonical_source_hash
from toefl_tracker.training_plan import build_training_plan, write_training_plan


def _event(attempt_id: str, code: str) -> dict:
    return {
        "event_id": f"E-{attempt_id}-{code}",
        "attempt_id": attempt_id,
        "taxonomy_version": 1,
        "code": code,
        "source_excerpt": "bad sentence",
        "audio_timestamp": None,
        "suggested_revision": "correct sentence",
        "reason": "recurring issue",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "recurring",
    }


def test_plan_waits_for_two_unresolved_rounds_and_preserves_route(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-AD-1", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-1-R1", "academic_discussion", "revision")
    write_attempt(tmp_path, "W-AD-1-R2", "academic_discussion", "revision")
    root = tmp_path / "tracker/writing/attempts"
    for attempt_id, parent_id in [("W-AD-1-R1", "W-AD-1"), ("W-AD-1-R2", "W-AD-1-R1")]:
        path = root / attempt_id / "attempt.yaml"
        attempt = yaml.safe_load(path.read_text(encoding="utf-8"))
        attempt["parent_attempt_id"] = parent_id
        path.write_text(yaml.safe_dump(attempt), encoding="utf-8")
    for attempt_id, codes in [("W-AD-1", ["GRAM-CLAUSE", "DISCUSSION-ELABORATION"]), ("W-AD-1-R1", ["GRAM-CLAUSE"]), ("W-AD-1-R2", ["DISCUSSION-ELABORATION"])]:
        (root / attempt_id / "events.jsonl").write_text(
            canonical_jsonl([_event(attempt_id, code) for code in codes]), encoding="utf-8"
        )
    plan = build_training_plan(tmp_path)
    assert len(plan["recommendations"]) == 1
    recommendation = plan["recommendations"][0]
    assert recommendation["task_type"] == "academic_discussion"
    assert recommendation["target_codes"] == ["DISCUSSION-ELABORATION", "GRAM-CLAUSE"]
    assert recommendation["drill"]["item_count"] == 8
    assert recommendation["transfer_check"]["new_prompt"] is True
    assert "causal" in recommendation["drill"]["instruction"].lower()


def test_plan_does_not_generate_for_fully_resolved_latest_round(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-EM-1", "email", "formal_original")
    write_attempt(tmp_path, "W-EM-1-R1", "email", "revision")
    write_attempt(tmp_path, "W-EM-1-R2", "email", "revision")
    for attempt_id, parent_id in [("W-EM-1-R1", "W-EM-1"), ("W-EM-1-R2", "W-EM-1-R1")]:
        path = tmp_path / "tracker/writing/attempts" / attempt_id / "attempt.yaml"
        attempt = yaml.safe_load(path.read_text(encoding="utf-8"))
        attempt["parent_attempt_id"] = parent_id
        path.write_text(yaml.safe_dump(attempt), encoding="utf-8")
    revisions = ["W-EM-1-R1", "W-EM-1-R2"]
    for number, attempt_id in enumerate(revisions, start=1):
        path = tmp_path / "tracker/writing/attempts" / attempt_id / "attempt.yaml"
        attempt = yaml.safe_load(path.read_text(encoding="utf-8"))
        attempt["revision_outcomes"] = {
            "assigned": 1,
            "resolved": 1,
            "partly_resolved": 0,
            "unresolved": 0,
            "new_errors": 0,
            "resolution_rate": 1.0,
        }
        attempt["submitted_at"] = f"2026-08-0{number + 2}T10:00:00+08:00"
        path.write_text(yaml.safe_dump(attempt), encoding="utf-8")
    assert build_training_plan(tmp_path)["recommendations"] == []


def test_write_training_plan_is_a_derived_artifact(tmp_path: Path) -> None:
    path = write_training_plan(tmp_path)
    assert path == tmp_path / "tracker/writing/training-plan.md"
    assert "Derived" in path.read_text(encoding="utf-8")
