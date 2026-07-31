import json
from pathlib import Path

import yaml

from toefl_tracker.reports import rebuild_modality


def write_attempt(
    root: Path, attempt_id: str, task_type: str, record_type: str
) -> None:
    directory = root / "tracker/writing/attempts" / attempt_id
    directory.mkdir(parents=True)
    data = {
        "attempt_id": attempt_id,
        "modality": "writing",
        "task_type": task_type,
        "record_type": record_type,
        "submitted_at": f"2026-07-{10 + int(attempt_id[-1]):02d}T10:00:00+08:00",
        "timed": True,
        "word_count": 100,
        "duration_seconds": 600,
        "task_score": {"scale": "0-5", "value": 3, "confidence": "medium"},
        "task_metrics": {},
        "opportunities": {},
        "parent_attempt_id": "W-AD-2" if record_type == "revision" else None,
        "revision_outcomes": (
            {
                "assigned": 2,
                "resolved": 1,
                "partly_resolved": 1,
                "unresolved": 0,
                "new_errors": 0,
                "resolution_rate": 0.5,
            }
            if record_type == "revision"
            else None
        ),
    }
    (directory / "attempt.yaml").write_text(
        yaml.safe_dump(data), encoding="utf-8"
    )


def write_events(root: Path, events: list[dict]) -> None:
    ledger = root / "tracker/writing/error-events.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )


def test_third_formal_writing_creates_common_and_task_reports(
    tmp_path: Path,
) -> None:
    write_attempt(tmp_path, "W-AD-1", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2-R1", "academic_discussion", "revision")
    write_attempt(tmp_path, "W-AD-3", "academic_discussion", "formal_original")

    generated = rebuild_modality(tmp_path, "writing")

    names = {path.name for path in generated}
    assert "writing-common-0003.md" in names
    assert "writing-academic-discussion-0003.md" in names
    dashboard = (tmp_path / "tracker/writing/dashboard.csv").read_text()
    assert "W-AD-2-R1" not in dashboard
    report = (
        tmp_path / "tracker/writing/reports/writing-common-0003.md"
    ).read_text()
    assert "Revision resolution rate: 50.0%" in report
    assert "## Next two focuses" in report


def test_rebuild_restores_every_crossed_three_attempt_boundary(
    tmp_path: Path,
) -> None:
    for index in range(1, 8):
        write_attempt(
            tmp_path,
            f"W-AD-{index}",
            "academic_discussion",
            "formal_original",
        )

    generated = {path.name for path in rebuild_modality(tmp_path, "writing")}

    assert "writing-common-0003.md" in generated
    assert "writing-common-0006.md" in generated
    assert "writing-academic-discussion-0003.md" in generated
    assert "writing-academic-discussion-0006.md" in generated


def test_report_only_uses_events_from_its_attempt_window(tmp_path: Path) -> None:
    for index in range(1, 7):
        write_attempt(
            tmp_path,
            f"W-AD-{index}",
            "academic_discussion",
            "formal_original",
        )
    write_events(
        tmp_path,
        [
            {
                "attempt_id": "W-AD-1",
                "code": "GRAM-EARLY",
                "level": "must_fix",
                "severity": "meaning_changing",
            },
            {
                "attempt_id": "W-AD-4",
                "code": "GRAM-LATER",
                "level": "must_fix",
                "severity": "meaning_changing",
            },
        ],
    )

    rebuild_modality(tmp_path, "writing")

    reports = tmp_path / "tracker/writing/reports"
    first_window = (reports / "writing-common-0003.md").read_text()
    second_window = (reports / "writing-common-0006.md").read_text()
    assert "GRAM-EARLY" in first_window
    assert "GRAM-LATER" not in first_window
    assert "GRAM-LATER" in second_window


def test_empty_modality_rebuilds_stable_dashboard_and_profile(
    tmp_path: Path,
) -> None:
    first_generated = rebuild_modality(tmp_path, "writing")
    dashboard = tmp_path / "tracker/writing/dashboard.csv"
    profile = tmp_path / "tracker/writing/profile.md"
    first_dashboard = dashboard.read_text()
    first_profile = profile.read_text()

    second_generated = rebuild_modality(tmp_path, "writing")

    assert first_generated == second_generated == []
    assert first_dashboard == dashboard.read_text()
    assert first_profile == profile.read_text()
    assert first_dashboard.startswith("attempt_id,submitted_at,task_type")
    assert first_profile == "# Current Profile\n"
