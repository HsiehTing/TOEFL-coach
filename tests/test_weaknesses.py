import json
from pathlib import Path

from test_reports import report_event, write_attempt, write_events
from toefl_tracker.weaknesses import rank_writing_weaknesses


def test_weakness_ranking_uses_opportunities_severity_recency_and_formals_only(
    tmp_path: Path,
) -> None:
    for attempt_id in ("W-AD-1", "W-AD-2", "W-AD-3"):
        write_attempt(tmp_path, attempt_id, "academic_discussion", "formal_original")
        path = tmp_path / f"tracker/writing/attempts/{attempt_id}/attempt.yaml"
        text = path.read_text(encoding="utf-8").replace("opportunities: {}", "opportunities:\n  GRAM-CLAUSE: 2\n  LEX-COLLOCATION: 8")
        path.write_text(text, encoding="utf-8")
    write_attempt(tmp_path, "W-AD-3-R1", "academic_discussion", "revision")
    revision = tmp_path / "tracker/writing/attempts/W-AD-3-R1/attempt.yaml"
    revision.write_text(
        revision.read_text(encoding="utf-8").replace("parent_attempt_id: W-AD-2", "parent_attempt_id: W-AD-3"),
        encoding="utf-8",
    )
    clause = report_event("W-AD-1", "E-1", "GRAM-CLAUSE", task_specific=False)
    clause["severity"] = "meaning_changing"
    events = [
        clause,
        report_event("W-AD-2", "E-2", "GRAM-CLAUSE", task_specific=False),
        report_event("W-AD-3", "E-3", "GRAM-CLAUSE", task_specific=False),
        report_event("W-AD-3-R1", "E-4", "LEX-COLLOCATION", task_specific=False),
    ]
    write_events(tmp_path, events)

    ranked = rank_writing_weaknesses(tmp_path)

    assert [row["code"] for row in ranked] == ["GRAM-CLAUSE"]
    signal = ranked[0]
    assert signal["formal_records_affected"] == 3
    assert signal["recent_opportunities"] == 6
    assert signal["max_severity"] == 3
    assert {row["event_id"] for row in signal["evidence"]} == {"E-1", "E-2", "E-3"}
