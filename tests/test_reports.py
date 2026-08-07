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
        "submitted_at": (
            f"2026-07-{20 + int(attempt_id[-1]):02d}T10:00:00+08:00"
            if record_type == "revision"
            else f"2026-07-{10 + int(attempt_id[-1]):02d}T10:00:00+08:00"
        ),
        "timed": True,
        "rubric_version": (
            "ets-writing-email-2025-applicable-2026"
            if task_type == "email"
            else "ets-writing-discussion-2025-applicable-2026"
        ),
        "standard_verified_at": "2026-07-31",
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
    (directory / "events.jsonl").write_text("", encoding="utf-8")


def write_events(root: Path, events: list[dict]) -> None:
    standards = root / "standards"
    if not standards.exists():
        import shutil

        shutil.copytree(Path(__file__).parents[1] / "standards", standards)
    ledger = root / "tracker/writing/error-events.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    by_attempt: dict[str, list[dict]] = {}
    for event in events:
        by_attempt.setdefault(event["attempt_id"], []).append(event)
    for attempt_id, rows in by_attempt.items():
        (root / "tracker/writing/attempts" / attempt_id / "events.jsonl").write_text(
            "".join(json.dumps(event) + "\n" for event in rows), encoding="utf-8"
        )


def report_event(attempt_id: str, event_id: str, code: str, *, task_specific: bool) -> dict:
    return {
        "event_id": event_id,
        "attempt_id": attempt_id,
        "taxonomy_version": 1,
        "code": code,
        "source_excerpt": "Fixture response",
        "audio_timestamp": None,
        "suggested_revision": "Use a clearer form.",
        "reason": "Fixture diagnostic.",
        "level": "must_fix",
        "severity": "meaning_changing",
        "task_specific": task_specific,
        "opportunity_present": True,
        "historical_status": "new",
    }


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
    assert "## Revision chains" in report
    assert "W-AD-2-R1" in report
    assert "## Revision resolution\nLatest-round full resolution:" in report
    assert "## Next two focuses" in report


def test_early_milestone_report_can_resolve_a_revision_whose_root_is_outside_window(
    tmp_path: Path,
) -> None:
    for attempt_id in ("W-AD-1", "W-AD-2", "W-AD-3", "W-AD-4"):
        write_attempt(tmp_path, attempt_id, "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-4-R1", "academic_discussion", "revision")
    revision = tmp_path / "tracker/writing/attempts/W-AD-4-R1/attempt.yaml"
    revision.write_text(
        revision.read_text(encoding="utf-8").replace(
            "parent_attempt_id: W-AD-2", "parent_attempt_id: W-AD-4"
        ),
        encoding="utf-8",
    )

    rebuild_modality(tmp_path, "writing")

    report = (tmp_path / "tracker/writing/reports/writing-common-0003.md").read_text(
        encoding="utf-8"
    )
    assert "W-AD-4-R1" not in report


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
            report_event("W-AD-1", "W-EARLY", "GRAM-ARTICLE", task_specific=False),
            report_event("W-AD-4", "W-LATER", "GRAM-NEGATION", task_specific=False),
        ],
    )

    rebuild_modality(tmp_path, "writing")

    reports = tmp_path / "tracker/writing/reports"
    first_window = (reports / "writing-common-0003.md").read_text()
    second_window = (reports / "writing-common-0006.md").read_text()
    assert "GRAM-ARTICLE" in first_window
    assert "GRAM-NEGATION" not in first_window
    assert "GRAM-NEGATION" in second_window


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
    assert first_profile == "# Current Profile\n\nFormal records: 0\n"


def test_rebuilt_dashboard_uses_stable_lf_line_endings(tmp_path: Path) -> None:
    write_attempt(
        tmp_path,
        "W-AD-1",
        "academic_discussion",
        "formal_original",
    )

    rebuild_modality(tmp_path, "writing")
    dashboard = tmp_path / "tracker/writing/dashboard.csv"
    first_bytes = dashboard.read_bytes()

    assert b"\r\n" not in first_bytes
    assert first_bytes.endswith(b"\n")
    rebuild_modality(tmp_path, "writing")
    assert dashboard.read_bytes() == first_bytes


def test_common_report_has_contract_fields_and_excludes_route_codes(
    tmp_path: Path,
) -> None:
    for index in range(1, 4):
        write_attempt(tmp_path, f"W-EMAIL-{index}", "email", "formal_original")
    write_events(
        tmp_path,
        [
            report_event("W-EMAIL-1", "W-E-1", "GRAM-ARTICLE", task_specific=False),
            report_event("W-EMAIL-1", "W-E-2", "LEX-WORDFORM", task_specific=False),
            report_event("W-EMAIL-1", "W-E-3", "EMAIL-REGISTER", task_specific=True),
            report_event(
                "W-EMAIL-2", "W-E-4", "MECH-SPELLING", task_specific=False
            ),
            report_event(
                "W-EMAIL-2", "W-E-5", "DISCUSSION-ELABORATION", task_specific=True
            ),
        ],
    )

    rebuild_modality(tmp_path, "writing")

    report = (tmp_path / "tracker/writing/reports/writing-common-0003.md").read_text()
    assert "Formal records: 3" in report
    assert "`W-EMAIL-1` | timed | simulated_task_score" in report
    assert "rubric: `ets-writing-email-2025-applicable-2026`" in report
    assert "## Severe-event trend\n2 → 1 → 0" in report
    assert "EMAIL-REGISTER" not in report


def test_route_report_contains_common_and_only_matching_route_codes(
    tmp_path: Path,
) -> None:
    for index in range(1, 4):
        write_attempt(tmp_path, f"W-EMAIL-{index}", "email", "formal_original")
    write_events(
        tmp_path,
        [
            report_event("W-EMAIL-1", "W-E-1", "GRAM-ARTICLE", task_specific=False),
            report_event("W-EMAIL-1", "W-E-2", "EMAIL-REGISTER", task_specific=True),
            report_event(
                "W-EMAIL-2", "W-E-3", "DISCUSSION-ELABORATION", task_specific=True
            ),
        ],
    )

    rebuild_modality(tmp_path, "writing")

    report = (tmp_path / "tracker/writing/reports/writing-email-0003.md").read_text()
    assert "GRAM-ARTICLE" in report
    assert "EMAIL-REGISTER" in report
    assert "DISCUSSION-ELABORATION" not in report


def test_rebuild_removes_only_stale_generated_reports(tmp_path: Path) -> None:
    reports = tmp_path / "tracker/writing/reports"
    reports.mkdir(parents=True)
    stale = reports / "writing-common-9999.md"
    personal = reports / "my-notes.md"
    stale.write_text("generated\n", encoding="utf-8")
    personal.write_text("personal\n", encoding="utf-8")

    rebuild_modality(tmp_path, "writing")

    assert not stale.exists()
    assert personal.exists()


def test_reevaluation_is_shown_beside_original_without_advancing_cadence(
    tmp_path: Path,
) -> None:
    for index in range(1, 4):
        write_attempt(tmp_path, f"W-AD-{index}", "academic_discussion", "formal_original")
    original = tmp_path / "tracker/writing/attempts/W-AD-3/attempt.yaml"
    reevaluation = yaml.safe_load(original.read_text(encoding="utf-8"))
    reevaluation.update(
        {
            "schema_version": 2,
            "attempt_id": "W-AD-3-E1",
            "record_type": "re_evaluation",
            "parent_attempt_id": "W-AD-3",
            "evaluated_at": "2026-08-02T10:00:00+08:00",
            "supersedes_evaluation_id": "W-AD-3@ets-writing-discussion-2025-applicable-2026",
            "rubric_version": "ets-writing-discussion-2026-revised",
            "task_score": {"scale": "0-5", "value": 4, "confidence": "medium"},
        }
    )
    directory = tmp_path / "tracker/writing/attempts/W-AD-3-E1"
    directory.mkdir()
    (directory / "attempt.yaml").write_text(yaml.safe_dump(reevaluation), encoding="utf-8")
    (directory / "events.jsonl").write_text("", encoding="utf-8")

    generated = rebuild_modality(tmp_path, "writing")
    report = (tmp_path / "tracker/writing/reports/writing-common-0003.md").read_text()

    assert "Original evaluation:" in report
    assert "Re-evaluation: `W-AD-3-E1` | simulated_task_score | result: 4" in report
    assert "Warning: compared records span multiple rubric versions." in report
    assert not any(path.name.endswith("0004.md") for path in generated)


def test_zero_speaking_records_still_have_derived_artifacts(tmp_path: Path) -> None:
    rebuild_modality(tmp_path, "speaking")

    assert (tmp_path / "tracker/speaking/dashboard.csv").read_text().startswith("attempt_id,")
    assert "Formal records: 0" in (tmp_path / "tracker/speaking/profile.md").read_text()
