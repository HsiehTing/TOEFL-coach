import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from test_validation import valid_attempt
from toefl_tracker.audit import audit_workspace
from toefl_tracker.reports import rebuild_modality
from validate_tracker import main as validate_tracker_main


def test_orphan_event_is_reported(tmp_path: Path) -> None:
    ledger = tmp_path / "tracker/writing/error-events.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({
        "event_id": "E-1",
        "attempt_id": "MISSING",
        "taxonomy_version": 1,
        "code": "GRAM-ARTICLE",
        "source_excerpt": "a object",
        "audio_timestamp": None,
        "suggested_revision": "an object",
        "reason": "Article selection.",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }) + "\n")
    problems = audit_workspace(tmp_path)
    assert any("orphan event E-1" in problem for problem in problems)


def test_stale_derived_dashboard_is_reported(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    shutil.copytree(root / "standards", tmp_path / "standards")
    destination = tmp_path / "tracker/writing/attempts/W-AD-20260731-001"
    destination.mkdir(parents=True)
    (destination / "attempt.yaml").write_text(
        yaml.safe_dump(valid_attempt(), allow_unicode=True),
        encoding="utf-8",
    )
    (destination / "events.jsonl").write_text("", encoding="utf-8")
    rebuild_modality(tmp_path, "writing")
    dashboard = tmp_path / "tracker/writing/dashboard.csv"
    dashboard.write_text(dashboard.read_text() + "stale,row\n", encoding="utf-8")
    assert any("stale derived file" in problem for problem in audit_workspace(tmp_path))


def test_non_mapping_ledger_row_is_reported_without_crashing(tmp_path: Path) -> None:
    ledger = tmp_path / "tracker/writing/error-events.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("null\n[]\n42\n", encoding="utf-8")
    problems = audit_workspace(tmp_path)
    assert len([problem for problem in problems if "must be a JSON mapping" in problem]) == 3


def test_missing_score_policy_is_reported(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    shutil.copytree(root / "standards", tmp_path / "standards")
    (tmp_path / "standards/ets-2026/score-policy.md").unlink()
    assert any("score-policy.md: missing" in problem for problem in audit_workspace(tmp_path))


def test_unreadable_derived_file_is_reported(tmp_path: Path, monkeypatch) -> None:
    root = Path(__file__).parents[1]
    shutil.copytree(root / "standards", tmp_path / "standards")
    destination = tmp_path / "tracker/writing/attempts/W-AD-20260731-001"
    destination.mkdir(parents=True)
    (destination / "attempt.yaml").write_text(
        yaml.safe_dump(valid_attempt(), allow_unicode=True), encoding="utf-8"
    )
    (destination / "events.jsonl").write_text("", encoding="utf-8")
    rebuild_modality(tmp_path, "writing")
    dashboard = tmp_path / "tracker/writing/dashboard.csv"
    original_read_text = Path.read_text

    def unreadable_dashboard(path: Path, *args, **kwargs):
        if path == dashboard:
            raise OSError("permission denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable_dashboard)
    assert any("stale derived file dashboard.csv" in problem for problem in audit_workspace(tmp_path))


def test_invalid_utf8_becomes_an_audit_finding(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    shutil.copytree(root / "standards", tmp_path / "standards")
    destination = tmp_path / "tracker/writing/attempts/W-AD-20260731-001"
    destination.mkdir(parents=True)
    (destination / "attempt.yaml").write_text(
        yaml.safe_dump(valid_attempt(), allow_unicode=True), encoding="utf-8"
    )
    target = destination / "response-original.md"
    target.write_bytes(b"\xff\xfe")
    (destination / "prompt.md").write_text("prompt\n", encoding="utf-8")
    (destination / "feedback-round-1.md").write_text("feedback\n", encoding="utf-8")
    (destination / "events.jsonl").write_text("", encoding="utf-8")

    problems = audit_workspace(tmp_path)

    assert any(str(target) in row and "UTF-8" in row for row in problems)


def test_malformed_speaking_artifacts_are_semantic_audit_findings(
    populated_workspace: Path,
) -> None:
    segments = populated_workspace / "tracker/speaking/attempts/S-LR-20260105-001/segments.yaml"
    segments.write_text("- role: learner\n  item: 99\n", encoding="utf-8")

    assert any("speaking segment item" in row for row in audit_workspace(populated_workspace))


def test_audit_continues_after_bad_utf8_and_cli_returns_nonzero(
    populated_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = populated_workspace / "tracker/writing/attempts/W-AD-20260101-001/response-original.md"
    response.write_bytes(b"\xff")
    ledger = populated_workspace / "tracker/writing/error-events.jsonl"
    orphan = {
        "event_id": "W-ORPHAN",
        "attempt_id": "MISSING",
        "taxonomy_version": 1,
        "code": "GRAM-ARTICLE",
        "source_excerpt": "a object",
        "audio_timestamp": None,
        "suggested_revision": "an object",
        "reason": "Fixture orphan.",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }
    ledger.write_text(ledger.read_text(encoding="utf-8") + json.dumps(orphan) + "\n", encoding="utf-8")

    problems = audit_workspace(populated_workspace)
    monkeypatch.setattr(sys, "argv", ["validate_tracker.py", "--root", str(populated_workspace)])

    assert any(str(response) in row and "UTF-8" in row for row in problems)
    assert any("orphan event W-ORPHAN" in row for row in problems)
    assert validate_tracker_main() == 1
