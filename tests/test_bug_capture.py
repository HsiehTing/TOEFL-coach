from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from toefl_tracker.bug_capture import (
    append_bug_resolution,
    bug_capture_receipt,
    build_bug_index,
    capture_bug_report,
    recover_bug_reports,
    verify_bug_reports,
)
from toefl_tracker.models import ValidationError


def _roadmap(root: Path) -> Path:
    path = root / "docs/superpowers/plans/roadmap.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "# Roadmap\n\n## Bug capture ledger\n\n"
        "| Bug ID | Status | Summary | Evidence | Artifact |\n"
        "| --- | --- | --- | --- | --- |\n"
        "<!-- BUG-CAPTURE-LEDGER -->\n",
        encoding="utf-8",
    )
    return path


def test_capture_writes_reproduction_snapshot_and_one_roadmap_link(tmp_path: Path) -> None:
    roadmap = _roadmap(tmp_path)
    attachment = tmp_path / "terminal-output.txt"
    attachment.write_text("unexpected result\n", encoding="utf-8")

    report_dir = capture_bug_report(
        tmp_path,
        title="Drill routes the learner to a stale pack",
        purpose="Help the learner start the currently recommended drill.",
        expected="The active plan should offer a compatible drill.",
        observed="The queue points to a legacy pack.",
        steps=["Open the practice queue.", "Select the active writing plan."],
        affected_flow="practice queue → generated drill",
        timing="Immediately after the training plan changed.",
        reproducibility="Every time this active plan is selected.",
        impact="The learner cannot begin the recommended practice.",
        attachments=[attachment],
        reported_at=datetime(2026, 8, 11, 9, 30, tzinfo=timezone.utc),
        roadmap=roadmap,
    )

    assert report_dir.name == "BUG-20260811-001"
    report = (report_dir / "report.yaml").read_text(encoding="utf-8")
    reproduction = (report_dir / "reproduction.md").read_text(encoding="utf-8")
    snapshot = (report_dir / "snapshot.json").read_text(encoding="utf-8")
    assert "affected_flow: practice queue → generated drill" in report
    assert "purpose: Help the learner start the currently recommended drill." in report
    assert "Immediately after the training plan changed." in reproduction
    assert "Every time this active plan is selected." in reproduction
    assert "The queue points to a legacy pack." in reproduction
    assert '"status_porcelain"' in snapshot
    assert (report_dir / "attachments/terminal-output.txt").read_text(encoding="utf-8") == "unexpected result\n"
    assert "`BUG-20260811-001`" in roadmap.read_text(encoding="utf-8")
    assert (report_dir / ".ready").exists()
    assert "sha256:" in roadmap.read_text(encoding="utf-8")
    assert verify_bug_reports(tmp_path, roadmap=roadmap) == []
    assert "original_path" not in report
    assert "original_name: terminal-output.txt" in report
    assert "mime_type: text/plain" in report


def test_capture_requires_steps_and_the_roadmap_marker(tmp_path: Path) -> None:
    roadmap = _roadmap(tmp_path)
    with pytest.raises(ValidationError, match="at least one reproduction step"):
        capture_bug_report(
            tmp_path,
            title="Missing steps",
            purpose="Test validation.",
            expected="Expected",
            observed="Observed",
            steps=[],
            roadmap=roadmap,
        )
    with pytest.raises(ValidationError, match="attachment is not a file"):
        capture_bug_report(
            tmp_path,
            title="Invalid attachment",
            purpose="Test validation.",
            expected="Expected",
            observed="Observed",
            steps=["Reproduce it."],
            attachments=[tmp_path / "missing.log"],
            roadmap=roadmap,
        )
    assert not (tmp_path / "tracker/bug-reports").exists()
    roadmap.write_text("# Roadmap\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="ledger marker"):
        capture_bug_report(
            tmp_path,
            title="Missing ledger",
            purpose="Test validation.",
            expected="Expected",
            observed="Observed",
            steps=["Reproduce it."],
            roadmap=roadmap,
        )


def test_capture_enforces_attachment_privacy_and_double_opt_in_for_diffs(tmp_path: Path) -> None:
    roadmap = _roadmap(tmp_path)
    audio = tmp_path / "learner.m4a"
    audio.write_bytes(b"not captured")
    with pytest.raises(ValidationError, match="type is not allowed"):
        capture_bug_report(
            tmp_path, title="Audio issue", purpose="Test policy.", expected="Expected", observed="Observed",
            steps=["Reproduce it."], attachments=[audio], roadmap=roadmap,
        )
    with pytest.raises(ValidationError, match="explicit confirmation"):
        capture_bug_report(
            tmp_path, title="Diff issue", purpose="Test policy.", expected="Expected", observed="Observed",
            steps=["Reproduce it."], include_git_diff=True, roadmap=roadmap,
        )
    oversized = tmp_path / "oversized.log"
    oversized.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
    with pytest.raises(ValidationError, match="size limit"):
        capture_bug_report(
            tmp_path, title="Large log", purpose="Test policy.", expected="Expected", observed="Observed",
            steps=["Reproduce it."], attachments=[oversized], roadmap=roadmap,
        )
    report = capture_bug_report(
        tmp_path, title="Safe diff", purpose="Test policy.", expected="Expected", observed="Observed",
        steps=["Reproduce it."], include_git_diff=True, confirm_safe_git_diff=True, roadmap=roadmap,
    )
    assert '"working_diff"' in (report / "snapshot.json").read_text(encoding="utf-8")


def test_recovery_links_a_ready_report_once_after_roadmap_write_interrupts(tmp_path: Path) -> None:
    roadmap = _roadmap(tmp_path)

    def interrupt(point: str) -> None:
        if point == "after_publish":
            raise OSError("roadmap temporarily unavailable")

    with pytest.raises(OSError, match="temporarily unavailable"):
        capture_bug_report(
            tmp_path,
            title="Queue does not open the active drill",
            purpose="Start the recommended practice.",
            expected="The active drill opens.",
            observed="The queue returns to its previous screen.",
            steps=["Open the practice queue."],
            reported_at=datetime(2026, 8, 11, 9, 30, tzinfo=timezone.utc),
            roadmap=roadmap,
            failpoint=interrupt,
        )

    report_dir = tmp_path / "tracker/bug-reports/BUG-20260811-001"
    assert (report_dir / ".ready").is_file()
    assert "BUG-20260811-001" not in roadmap.read_text(encoding="utf-8")
    assert verify_bug_reports(tmp_path, roadmap=roadmap) == [
        "ready report is missing a roadmap link: BUG-20260811-001"
    ]
    assert recover_bug_reports(tmp_path, roadmap=roadmap) == [report_dir]
    assert recover_bug_reports(tmp_path, roadmap=roadmap) == []
    assert roadmap.read_text(encoding="utf-8").count("`BUG-20260811-001`") == 1
    assert verify_bug_reports(tmp_path, roadmap=roadmap) == []


def test_concurrent_captures_allocate_unique_ids_and_ledger_rows(tmp_path: Path) -> None:
    roadmap = _roadmap(tmp_path)

    def capture(number: int) -> Path:
        return capture_bug_report(
            tmp_path,
            title=f"Queue issue {number}",
            purpose="Start the recommended practice.",
            expected="The active drill opens.",
            observed="The queue remains on the current screen.",
            steps=["Open the practice queue."],
            reported_at=datetime(2026, 8, 11, 9, 30, tzinfo=timezone.utc),
            roadmap=roadmap,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        reports = list(executor.map(capture, (1, 2)))

    assert {path.name for path in reports} == {"BUG-20260811-001", "BUG-20260811-002"}
    assert verify_bug_reports(tmp_path, roadmap=roadmap) == []


def test_machine_receipt_resolution_and_operational_index(tmp_path: Path) -> None:
    roadmap = _roadmap(tmp_path)
    report = capture_bug_report(
        tmp_path,
        title="Queue does not start the current drill",
        purpose="Start the learner's recommended practice.",
        expected="A compatible pack opens.",
        observed="A stale pack blocks the action.",
        steps=["Open the current plan."],
        affected_flow="practice queue",
        reproducibility="always",
        roadmap=roadmap,
    )
    receipt = bug_capture_receipt(tmp_path, report, roadmap=roadmap)
    assert receipt["bug_id"] == "BUG-20260811-001"
    assert receipt["validation"] == {"passed": True, "problems": []}

    resolution = append_bug_resolution(
        tmp_path,
        bug_id="BUG-20260811-001",
        outcome="fixed_verified",
        diagnosis="The pack identity omitted the renderer version.",
        fix_reference="abc123",
        validation_command="pytest -q tests/test_drill_generation.py",
        validation_result="passed",
        roadmap=roadmap,
    )
    assert resolution.name == "RES-001.yaml"
    assert "| fixed_verified |" in roadmap.read_text(encoding="utf-8")
    assert verify_bug_reports(tmp_path, roadmap=roadmap) == []
    index = build_bug_index(tmp_path, roadmap=roadmap)
    assert index["by_status"] == {"fixed_verified": 1}
    assert index["reports"] == [{
        "bug_id": "BUG-20260811-001",
        "status": "fixed_verified",
        "affected_flow": "practice queue",
        "reproducibility": "always",
        "artifact_complete": True,
    }]


def test_resolution_requires_verified_fix_reference_and_preserves_initial_report(tmp_path: Path) -> None:
    roadmap = _roadmap(tmp_path)
    report = capture_bug_report(
        tmp_path, title="Queue issue", purpose="Start practice.", expected="Open.",
        observed="Blocked.", steps=["Open."], roadmap=roadmap,
    )
    original = (report / "report.yaml").read_bytes()
    with pytest.raises(ValidationError, match="fix reference"):
        append_bug_resolution(
            tmp_path, bug_id=report.name, outcome="fixed_verified", diagnosis="Cause.",
            validation_command="pytest", validation_result="passed", roadmap=roadmap,
        )
    assert (report / "report.yaml").read_bytes() == original
