from pathlib import Path

import yaml

from toefl_tracker.legacy_migration import build_legacy_migration_plan


def _attempt(attempt_id: str, record_type: str, submitted_at: str, parent: str | None = None) -> dict:
    return {"attempt_id": attempt_id, "record_type": record_type, "submitted_at": submitted_at, "parent_attempt_id": parent}


def test_plan_preserves_source_records_and_proposes_only_metadata(tmp_path: Path) -> None:
    base = tmp_path / "tracker/writing/attempts"
    for row in [
        _attempt("W-1", "formal_original", "2026-08-01T00:00:00+08:00"),
        _attempt("W-1-R1", "revision", "2026-08-01T00:00:00+08:00", "W-1"),
        _attempt("W-1-R2", "revision", "2026-08-01T00:00:00+08:00", "W-1-R1"),
    ]:
        directory = base / row["attempt_id"]
        directory.mkdir(parents=True)
        (directory / "attempt.yaml").write_text(yaml.safe_dump(row), encoding="utf-8")

    plan = build_legacy_migration_plan(tmp_path, "writing")

    assert plan["version"] == 1
    assert plan["missing_event_sidecars"] == ["W-1", "W-1-R1", "W-1-R2"]
    assert plan["synthetic_lineage_order"] == ["W-1", "W-1-R1", "W-1-R2"]
    assert plan["source_records_modified"] is False
