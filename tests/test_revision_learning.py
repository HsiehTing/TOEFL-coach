from pathlib import Path

from test_reports import report_event, write_attempt, write_events
from toefl_tracker.revision_learning import build_revision_learning, write_revision_learning


def test_revision_learning_separates_retained_removed_and_new_codes(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-AD-1", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-1-R1", "academic_discussion", "revision")
    revision = tmp_path / "tracker/writing/attempts/W-AD-1-R1/attempt.yaml"
    revision.write_text(
        revision.read_text(encoding="utf-8").replace("parent_attempt_id: W-AD-2", "parent_attempt_id: W-AD-1"),
        encoding="utf-8",
    )
    write_events(tmp_path, [
        report_event("W-AD-1", "E-1", "GRAM-CLAUSE", task_specific=False),
        report_event("W-AD-1", "E-2", "LEX-WORDFORM", task_specific=False),
        report_event("W-AD-1-R1", "E-3", "GRAM-CLAUSE", task_specific=False),
        report_event("W-AD-1-R1", "E-4", "LEX-COLLOCATION", task_specific=False),
    ])

    learning = build_revision_learning(tmp_path)
    path = write_revision_learning(tmp_path)

    assert learning["comparisons"][0]["retained_codes"] == ["GRAM-CLAUSE"]
    assert learning["comparisons"][0]["no_longer_observed_codes"] == ["LEX-WORDFORM"]
    assert learning["comparisons"][0]["new_codes"] == ["LEX-COLLOCATION"]
    assert "not proof of mastery" in path.read_text(encoding="utf-8").lower()
