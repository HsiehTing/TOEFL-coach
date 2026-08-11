import json
from pathlib import Path

import yaml

from toefl_tracker.speaking_progress import build_speaking_progress_overview, write_speaking_progress_overview


def _attempt(root: Path, attempt_id: str, task_type: str, submitted_at: str) -> None:
    directory = root / "tracker/speaking/attempts" / attempt_id
    directory.mkdir(parents=True)
    (directory / "attempt.yaml").write_text(yaml.safe_dump({
        "attempt_id": attempt_id, "modality": "speaking", "task_type": task_type,
        "record_type": "formal_original", "submitted_at": submitted_at,
        "duration_seconds": 42.0,
    }), encoding="utf-8")
    (directory / "audio-inspection.json").write_text(json.dumps({"reliable_dimensions": ["content", "grammar", "vocabulary"]}), encoding="utf-8")
    (directory / "segments.yaml").write_text(yaml.safe_dump([
        {"confidence": "high"}, {"confidence": "medium", "confirmed_by_user": True},
    ]), encoding="utf-8")
    (directory / "events.jsonl").write_text("", encoding="utf-8")


def _event(attempt_id: str, event_id: str, code: str) -> dict:
    return {
        "event_id": event_id, "attempt_id": attempt_id, "taxonomy_version": 1,
        "code": code, "source_excerpt": None, "audio_timestamp": "00:10",
        "suggested_revision": "Use a complete response.", "reason": "Fixture diagnostic.",
        "level": "should_fix", "severity": "clarity_reducing", "task_specific": code.startswith("INTERVIEW-"),
        "opportunity_present": True, "historical_status": "new",
    }


def test_speaking_overview_is_diagnostic_and_keeps_route_signals_separate(tmp_path: Path) -> None:
    standards = Path(__file__).parents[1] / "standards"
    import shutil
    shutil.copytree(standards, tmp_path / "standards")
    _attempt(tmp_path, "S-LR-1", "listen_and_repeat", "2026-08-01T10:00:00+08:00")
    _attempt(tmp_path, "S-INT-2", "take_an_interview", "2026-08-02T10:00:00+08:00")
    _attempt(tmp_path, "S-INT-3", "take_an_interview", "2026-08-03T10:00:00+08:00")
    drill_dir = tmp_path / "tracker/speaking/attempts/S-DRILL-1"
    drill_dir.mkdir(parents=True)
    (drill_dir / "attempt.yaml").write_text(yaml.safe_dump({
        "attempt_id": "S-DRILL-1", "modality": "speaking", "task_type": "take_an_interview",
        "record_type": "targeted_drill", "submitted_at": "2026-08-04T10:00:00+08:00",
        "drill": {
            "minimum_accuracy": 0.8,
            "code_results": [{
                "code": "INTERVIEW-ELABORATION", "item_count": 2,
                "correct_count": 2, "partial_count": 0,
            }],
        },
    }), encoding="utf-8")
    (drill_dir / "events.jsonl").write_text("", encoding="utf-8")
    transfer_dir = tmp_path / "tracker/speaking/attempts/S-INT-TRANSFER-4"
    transfer_dir.mkdir(parents=True)
    (transfer_dir / "attempt.yaml").write_text(yaml.safe_dump({
        "attempt_id": "S-INT-TRANSFER-4", "modality": "speaking", "task_type": "take_an_interview",
        "record_type": "formal_original", "submitted_at": "2026-08-05T10:00:00+08:00",
        "duration_seconds": 42.0,
        "transfer": {
            "target_codes": ["INTERVIEW-ELABORATION"],
            "outcomes": [{"code": "INTERVIEW-ELABORATION", "status": "meets_target"}],
        },
    }), encoding="utf-8")
    (transfer_dir / "events.jsonl").write_text("", encoding="utf-8")
    revision_dir = tmp_path / "tracker/speaking/attempts/S-INT-R1"
    revision_dir.mkdir(parents=True)
    (revision_dir / "attempt.yaml").write_text(yaml.safe_dump({
        "attempt_id": "S-INT-R1", "modality": "speaking", "task_type": "take_an_interview",
        "record_type": "revision", "submitted_at": "2026-08-06T10:00:00+08:00",
        "speaking_revision": {
            "parent_attempt_id": "S-INT-3", "scope": "partial",
            "outcomes": [{"code": "INTERVIEW-DIRECTNESS", "status": "partially_meets_target", "item_ids": [2]}],
        },
    }), encoding="utf-8")
    (revision_dir / "events.jsonl").write_text("", encoding="utf-8")
    events = [
        _event("S-LR-1", "E-1", "GRAM-CLAUSE"),
        _event("S-INT-2", "E-2", "INTERVIEW-DIRECTNESS"),
        _event("S-INT-3", "E-3", "INTERVIEW-DIRECTNESS"),
    ]
    ledger = tmp_path / "tracker/speaking/error-events.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("".join(json.dumps(row) + "\n" for row in events), encoding="utf-8")
    for row in events:
        path = tmp_path / "tracker/speaking/attempts" / row["attempt_id"] / "events.jsonl"
        path.write_text(path.read_text(encoding="utf-8") + json.dumps(row) + "\n", encoding="utf-8")

    overview = build_speaking_progress_overview(tmp_path)
    path = write_speaking_progress_overview(tmp_path)
    text = path.read_text(encoding="utf-8")

    assert overview["result_label"] == "diagnostic_only_speaking_progress"
    assert overview["version"] == 2
    assert "GRAM-CLAUSE" in overview["routes"]["listen_and_repeat"]["atomic_codes"]
    assert "INTERVIEW-DIRECTNESS" not in overview["routes"]["listen_and_repeat"]["atomic_codes"]
    assert overview["next_focuses"][0]["code"] == "INTERVIEW-DIRECTNESS"
    lifecycle = overview["routes"]["take_an_interview"]["practice_lifecycle"]
    assert lifecycle == [{
        "code": "INTERVIEW-ELABORATION",
        "drill_attempt_ids": ["S-DRILL-1"],
        "transfer_attempt_ids": ["S-INT-TRANSFER-4"],
        "latest_drill_accuracy": 1.0,
        "latest_minimum_accuracy": 0.8,
        "latest_transfer_outcome": "meets_target",
        "state": "transfer_outcome_meets_target",
    }]
    assert "not a TOEFL Speaking section band" in text
    assert "Practice lifecycle" in text
    assert "Re-recordings (excluded from formal-session count)" in text
    assert "confirmed" in text
