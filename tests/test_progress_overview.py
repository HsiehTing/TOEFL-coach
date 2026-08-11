from pathlib import Path

import yaml

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


def test_overview_renders_actionable_dashboard_details(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-EMAIL-1", "email", "formal_original")
    write_attempt(tmp_path, "W-AD-2", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-EMAIL-3", "email", "formal_original")
    write_events(tmp_path, [
        report_event("W-EMAIL-1", "E-1", "EMAIL-ACTION", task_specific=True),
        report_event("W-AD-2", "E-2", "GRAM-CLAUSE", task_specific=False),
    ])

    path = write_progress_overview(tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "Errors / 100 words" in text
    assert "## Route coverage" in text
    assert "## Atomic-code and skill-family trend signals" in text
    assert "trend signal:" in text
    assert "## Drill, mastery, and transfer evidence" in text
    assert "## Revision chains" in text
    assert "## Data quality" in text


def test_overview_renders_revision_outcomes_and_transfer_evidence(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-AD-1", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2-R1", "academic_discussion", "revision")
    write_attempt(tmp_path, "W-AD-3", "academic_discussion", "formal_original")
    drill = {
        "attempt_id": "W-DRILL-1",
        "modality": "writing",
        "task_type": "academic_discussion",
        "record_type": "targeted_drill",
        "submitted_at": "2026-07-14T10:00:00+08:00",
        "drill": {
            "set_id": "set-1",
            "target_codes": ["GRAM-CLAUSE"],
            "item_count": 4,
            "correct_count": 3,
            "source_attempt_ids": ["W-AD-2"],
        },
    }
    drill_dir = tmp_path / "tracker/writing/attempts/W-DRILL-1"
    drill_dir.mkdir()
    (drill_dir / "attempt.yaml").write_text(yaml.safe_dump(drill), encoding="utf-8")
    (drill_dir / "events.jsonl").write_text("", encoding="utf-8")
    transfer_path = tmp_path / "tracker/writing/attempts/W-AD-3/attempt.yaml"
    transfer = yaml.safe_load(transfer_path.read_text(encoding="utf-8"))
    transfer["opportunities"] = {"GRAM-CLAUSE": 3}
    transfer["transfer"] = {
        "drill_attempt_id": "W-DRILL-1",
        "drill_pack_id": "WD-0000000000000001",
        "source_attempt_id": "W-AD-2",
        "target_codes": ["GRAM-CLAUSE"],
        "opportunity_confirmation": {"GRAM-CLAUSE": 3},
        "source_prompt_hash": "sha256:" + "0" * 64,
        "transfer_prompt_hash": "sha256:" + "1" * 64,
    }
    transfer_path.write_text(yaml.safe_dump(transfer), encoding="utf-8")

    overview = build_progress_overview(tmp_path)
    path = write_progress_overview(tmp_path)
    text = path.read_text(encoding="utf-8")

    assert overview["mastery"]["GRAM-CLAUSE"]["drill_attempt_ids"] == ["W-DRILL-1"]
    assert overview["mastery"]["GRAM-CLAUSE"]["transfer_attempt_ids"] == ["W-AD-3"]
    assert "latest resolution: 50.0%" in text
    assert "latest new errors: 0" in text
    assert "Drill evidence: `W-DRILL-1`" in text
    assert "Transfer evidence: `W-AD-3`" in text


def test_overview_uses_declared_legacy_lineage_order_for_recent_records(tmp_path: Path) -> None:
    for attempt_id, task_type in [
        ("W-EMAIL-1", "email"),
        ("W-EMAIL-2", "email"),
        ("W-AD-3", "academic_discussion"),
    ]:
        write_attempt(tmp_path, attempt_id, task_type, "formal_original")
    for attempt_id in ("W-EMAIL-1", "W-EMAIL-2", "W-AD-3"):
        path = tmp_path / f"tracker/writing/attempts/{attempt_id}/attempt.yaml"
        attempt = yaml.safe_load(path.read_text(encoding="utf-8"))
        attempt["submitted_at"] = "2026-01-01T10:00:00+08:00"
        path.write_text(yaml.safe_dump(attempt), encoding="utf-8")
    metadata = {
        "version": 1,
        "modality": "writing",
        "source_records_modified": False,
        "synthetic_lineage_order": ["W-AD-3", "W-EMAIL-2", "W-EMAIL-1"],
    }
    compat = tmp_path / "tracker/writing/legacy-compat.yaml"
    compat.parent.mkdir(parents=True, exist_ok=True)
    compat.write_text(yaml.safe_dump(metadata), encoding="utf-8")

    overview = build_progress_overview(tmp_path)

    assert [row["attempt_id"] for row in overview["recent_formals"]] == [
        "W-AD-3", "W-EMAIL-2", "W-EMAIL-1"
    ]
