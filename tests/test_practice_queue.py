from pathlib import Path

from test_reports import report_event, write_attempt, write_events
from toefl_tracker.practice_queue import build_practice_queue, write_practice_queue


def test_queue_groups_latest_supported_focuses_into_drill_then_transfer(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-EMAIL-1", "email", "formal_original")
    write_attempt(tmp_path, "W-AD-2", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-EMAIL-3", "email", "formal_original")
    write_events(tmp_path, [
        report_event("W-EMAIL-1", "E-1", "GRAM-CLAUSE", task_specific=False),
        report_event("W-EMAIL-3", "E-2", "GRAM-CLAUSE", task_specific=False),
        report_event("W-EMAIL-3", "E-3", "LEX-COLLOCATION", task_specific=False),
    ])

    queue = build_practice_queue(tmp_path)

    assert queue["result_label"] == "diagnostic_practice_queue"
    assert len(queue["actions"]) == 2
    drill, transfer = queue["actions"]
    assert drill["kind"] == "targeted_drill"
    assert drill["source_attempt_id"] == "W-EMAIL-3"
    assert drill["target_codes"] == ["GRAM-CLAUSE", "LEX-COLLOCATION"]
    assert transfer["kind"] == "fresh_transfer_check"
    assert transfer["source_action_id"] == drill["action_id"]
    assert drill["status"] == "ready"
    assert transfer["status"] == "blocked_by_drill"
    assert "task_score" not in queue


def test_queue_is_derived_and_does_not_create_actions_without_supported_evidence(
    tmp_path: Path,
) -> None:
    write_attempt(tmp_path, "W-AD-1", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-3", "academic_discussion", "formal_original")
    write_events(tmp_path, [
        report_event("W-AD-1", "E-1", "GRAM-NEGATION", task_specific=False),
    ])

    queue = build_practice_queue(tmp_path)
    path = write_practice_queue(tmp_path)

    assert queue["actions"] == []
    assert queue["deferred_actions"][0]["status"] == "blocked_by_template"
    assert path == tmp_path / "tracker/writing/practice-queue.md"
    assert "diagnostic planning artifact" in path.read_text(encoding="utf-8").lower()
