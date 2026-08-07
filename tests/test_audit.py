import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from test_validation import valid_attempt
from toefl_tracker.audit import audit_workspace
from toefl_tracker.canonical import canonical_jsonl
from toefl_tracker.io import canonical_source_hash, read_yaml
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


def test_audit_text_only_inspection_rejects_audio_dimension_event(
    populated_workspace: Path,
) -> None:
    artifact = populated_workspace / "tracker/speaking/attempts/S-LR-20260105-001/audio-inspection.json"
    inspection = json.loads(artifact.read_text(encoding="utf-8"))
    inspection["mean_dbfs"] = -36.0
    inspection["quality"] = {
        "policy_version": 1,
        "standard_basis": "diagnostic_internal",
        "usable": True,
        "dimension_set": "text_only",
    }
    inspection["reliable_dimensions"] = ["content", "grammar", "vocabulary", "reconstruction"]
    artifact.write_text(json.dumps(inspection), encoding="utf-8")

    assert any("reliable dimension" in row for row in audit_workspace(populated_workspace))


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


def _persist_reevaluation(
    workspace: Path, attempt_id: str, evaluated_at: str, supersedes: str
) -> Path:
    original = read_yaml(
        workspace / "tracker/writing/attempts/W-AD-20260101-001/attempt.yaml"
    )
    reevaluation = {
        **original,
        "schema_version": 2,
        "attempt_id": attempt_id,
        "record_type": "re_evaluation",
        "parent_attempt_id": original["attempt_id"],
        "evaluated_at": evaluated_at,
        "supersedes_evaluation_id": supersedes,
        "task_score": {"scale": "0-5", "value": 4, "confidence": "medium"},
    }
    directory = workspace / "tracker/writing/attempts" / attempt_id
    directory.mkdir()
    (directory / "attempt.yaml").write_text(
        yaml.safe_dump(reevaluation), encoding="utf-8"
    )
    (directory / "feedback-round-1.md").write_text("feedback\n", encoding="utf-8")
    (directory / "events.jsonl").write_text("", encoding="utf-8")
    return directory


def test_audit_reuses_reevaluation_lineage_rules_and_rejects_event_sidecars(
    populated_workspace: Path,
) -> None:
    original = read_yaml(
        populated_workspace / "tracker/writing/attempts/W-AD-20260101-001/attempt.yaml"
    )
    original_evaluation = f"{original['attempt_id']}@{original['rubric_version']}"
    e1 = _persist_reevaluation(
        populated_workspace, "W-AD-20260101-001-E1", "2026-08-02T09:00:00+08:00", original_evaluation
    )
    e2 = _persist_reevaluation(
        populated_workspace, "W-AD-20260101-001-E2", "2026-08-02T08:00:00+08:00", original_evaluation
    )
    event = {
        "event_id": "E-ILLEGAL-REEVALUATION",
        "attempt_id": "W-AD-20260101-001-E2",
        "taxonomy_version": 1,
        "code": "GRAM-ARTICLE",
        "source_excerpt": "Fixture response W-AD-20260101-001",
        "audio_timestamp": None,
        "suggested_revision": "Use an article.",
        "reason": "Fixture evidence.",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }
    (e2 / "events.jsonl").write_text(canonical_jsonl([event]), encoding="utf-8")

    problems = audit_workspace(populated_workspace)

    assert any("immediate predecessor" in problem or "ordering key" in problem for problem in problems)
    assert any(str(e2 / "events.jsonl") in problem and "must be empty" in problem for problem in problems)
    assert e1.exists()


def test_audit_finds_duplicate_hash_and_attempt_directory_without_manifest(
    populated_workspace: Path,
) -> None:
    original = populated_workspace / "tracker/writing/attempts/W-AD-20260101-001"
    duplicate = populated_workspace / "tracker/writing/attempts/W-AD-DUPLICATE"
    shutil.copytree(original, duplicate)
    attempt = read_yaml(duplicate / "attempt.yaml")
    attempt["attempt_id"] = "W-AD-DUPLICATE"
    attempt["submitted_at"] = "2026-02-01T10:00:00+08:00"
    (duplicate / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
    hidden = populated_workspace / "tracker/writing/attempts/W-ORPHAN-DIRECTORY"
    hidden.mkdir()
    (hidden / "events.jsonl").write_text("", encoding="utf-8")

    problems = audit_workspace(populated_workspace)

    assert any("duplicate source_hash" in problem for problem in problems)
    assert any(str(hidden) in problem and "missing attempt.yaml" in problem for problem in problems)


def test_audit_reports_writing_and_reevaluation_feedback_utf8(
    populated_workspace: Path,
) -> None:
    original = read_yaml(
        populated_workspace / "tracker/writing/attempts/W-AD-20260101-001/attempt.yaml"
    )
    reevaluation = _persist_reevaluation(
        populated_workspace,
        "W-AD-20260101-001-E1",
        "2026-08-02T09:00:00+08:00",
        f"{original['attempt_id']}@{original['rubric_version']}",
    )
    writing_feedback = populated_workspace / "tracker/writing/attempts/W-AD-20260101-001/feedback-round-1.md"
    reevaluation_feedback = reevaluation / "feedback-round-1.md"
    writing_feedback.write_bytes(b"\xff")
    reevaluation_feedback.write_bytes(b"\xff")

    problems = audit_workspace(populated_workspace)

    assert any(str(writing_feedback) in problem and "UTF-8" in problem for problem in problems)
    assert any(str(reevaluation_feedback) in problem and "UTF-8" in problem for problem in problems)


def test_audit_preserves_schema_one_reevaluation_history(
    populated_workspace: Path,
) -> None:
    original = read_yaml(
        populated_workspace / "tracker/writing/attempts/W-AD-20260101-001/attempt.yaml"
    )
    legacy = _persist_reevaluation(
        populated_workspace,
        "W-AD-20260101-001-LEGACY",
        "2026-08-02T09:00:00+08:00",
        f"{original['attempt_id']}@{original['rubric_version']}",
    )
    attempt = read_yaml(legacy / "attempt.yaml")
    attempt["schema_version"] = 1
    attempt.pop("evaluated_at")
    attempt.pop("supersedes_evaluation_id")
    (legacy / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")

    problems = audit_workspace(populated_workspace)

    assert not any("supersedes_evaluation_id" in problem for problem in problems)


def test_audit_ignores_personal_report_notes_when_comparing_derived_files(
    populated_workspace: Path,
) -> None:
    rebuild_modality(populated_workspace, "writing")
    rebuild_modality(populated_workspace, "speaking")
    reports = populated_workspace / "tracker/writing/reports"
    reports.mkdir(exist_ok=True)
    note = reports / "my-notes.md"
    note.write_text("keep this private note\n", encoding="utf-8")

    problems = audit_workspace(populated_workspace)

    assert not any("derived report set is stale" in problem for problem in problems)
    assert not any(str(note) in problem for problem in problems)


def test_audit_accumulates_each_invalid_revision_relationship(
    populated_workspace: Path,
) -> None:
    original = read_yaml(
        populated_workspace / "tracker/writing/attempts/W-AD-20260101-001/attempt.yaml"
    )
    for attempt_id, parent_id, task_type, rubric in [
        ("W-REV-MISSING", "W-NOT-THERE", "academic_discussion", "ets-writing-discussion-2025-applicable-2026"),
        ("W-REV-MISMATCH", original["attempt_id"], "email", "ets-writing-email-2025-applicable-2026"),
    ]:
        prompt = f"Prompt {attempt_id}"
        response = f"Response {attempt_id}"
        attempt = {
            **original,
            "attempt_id": attempt_id,
            "record_type": "revision",
            "parent_attempt_id": parent_id,
            "task_type": task_type,
            "rubric_version": rubric,
            "submitted_at": "2026-02-01T10:00:00+08:00",
            "source_hash": canonical_source_hash(prompt, response),
            "revision_outcomes": {
                "assigned": 1,
                "resolved": 1,
                "partly_resolved": 0,
                "unresolved": 0,
                "new_errors": 0,
                "resolution_rate": 1.0,
            },
        }
        directory = populated_workspace / "tracker/writing/attempts" / attempt_id
        directory.mkdir()
        (directory / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
        (directory / "prompt.md").write_text(prompt, encoding="utf-8")
        (directory / "response-revision.md").write_text(response, encoding="utf-8")
        (directory / "feedback-round-1.md").write_text("feedback\n", encoding="utf-8")
        (directory / "events.jsonl").write_text("", encoding="utf-8")

    problems = audit_workspace(populated_workspace)

    assert any("writing: W-REV-MISSING: revision parent does not exist" in row for row in problems)
    assert any("writing: W-REV-MISMATCH: revision parent must be matching formal original or revision" in row for row in problems)


def test_audit_keeps_actual_lineage_predecessor_after_bad_supersedes_link(
    populated_workspace: Path,
) -> None:
    original = read_yaml(
        populated_workspace / "tracker/writing/attempts/W-AD-20260101-001/attempt.yaml"
    )
    original_evaluation = f"{original['attempt_id']}@{original['rubric_version']}"
    e1 = _persist_reevaluation(
        populated_workspace,
        "W-AD-20260101-001-E1",
        "2026-08-02T09:00:00+08:00",
        "NOT-THE-ORIGINAL",
    )
    e2 = _persist_reevaluation(
        populated_workspace,
        "W-AD-20260101-001-E2",
        "2026-08-02T10:00:00+08:00",
        f"W-AD-20260101-001-E1@{original['rubric_version']}",
    )
    _persist_reevaluation(
        populated_workspace,
        "W-AD-20260101-001-E3",
        "2026-08-02T11:00:00+08:00",
        original_evaluation,
    )

    problems = audit_workspace(populated_workspace)

    assert any("W-AD-20260101-001-E1: supersedes_evaluation_id" in row for row in problems)
    assert not any("W-AD-20260101-001-E2: supersedes_evaluation_id" in row for row in problems)
    assert any("W-AD-20260101-001-E3: supersedes_evaluation_id" in row for row in problems)
    assert e1.exists() and e2.exists()
