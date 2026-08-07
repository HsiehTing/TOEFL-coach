from pathlib import Path

from test_reports import report_event, write_attempt, write_events
from toefl_tracker.progress import build_progress_overview, write_progress_overview


def test_overview_marks_fewer_than_three_formals_as_diagnostic_early_view(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-EMAIL-1", "email", "formal_original")
    overview = build_progress_overview(tmp_path)

    assert overview["result_label"] == "diagnostic_only_early_view"
    assert overview["formal_record_count"] == 1
    assert overview["next_focuses"] == []


def test_overview_keeps_route_specific_codes_in_their_own_route(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-EMAIL-1", "email", "formal_original")
    write_attempt(tmp_path, "W-EMAIL-2", "email", "formal_original")
    write_attempt(tmp_path, "W-AD-3", "academic_discussion", "formal_original")
    write_events(tmp_path, [
        report_event("W-EMAIL-1", "E-1", "EMAIL-ACTION", task_specific=True),
        report_event("W-EMAIL-2", "E-2", "GRAM-CLAUSE", task_specific=False),
        report_event("W-AD-3", "E-3", "DISCUSSION-ELABORATION", task_specific=True),
    ])

    overview = build_progress_overview(tmp_path)

    assert overview["result_label"] == "diagnostic_only_progress_view"
    assert "EMAIL-ACTION" in overview["routes"]["email"]["atomic_codes"]
    assert "EMAIL-ACTION" not in overview["routes"]["academic_discussion"]["atomic_codes"]
    assert "DISCUSSION-ELABORATION" in overview["routes"]["academic_discussion"]["atomic_codes"]
    assert len(overview["next_focuses"]) <= 2
    assert all("section band" not in focus["reason"].lower() for focus in overview["next_focuses"])


def test_overview_is_rebuildable_without_mutating_events(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-EMAIL-1", "email", "formal_original")
    write_events(tmp_path, [report_event("W-EMAIL-1", "E-1", "GRAM-CLAUSE", task_specific=False)])
    before = (tmp_path / "tracker/writing/attempts/W-EMAIL-1/events.jsonl").read_text(encoding="utf-8")

    path = write_progress_overview(tmp_path)

    assert path == tmp_path / "tracker/writing/progress-overview.md"
    assert "not a toefl writing section band" in path.read_text(encoding="utf-8").lower()
    assert (tmp_path / "tracker/writing/attempts/W-EMAIL-1/events.jsonl").read_text(encoding="utf-8") == before
    assert (tmp_path / "tracker/writing/progress-overview.yaml").exists()
