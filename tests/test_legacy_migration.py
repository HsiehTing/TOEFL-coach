from pathlib import Path

import yaml

from toefl_tracker.legacy_migration import (
    apply_approved_legacy_review,
    build_legacy_migration_plan,
    has_approved_excerpt_exception,
    has_approved_status_exception,
    load_legacy_compatibility,
    synthetic_precedes,
    synthetic_sort_key,
    write_legacy_compatibility,
)


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

    path = write_legacy_compatibility(tmp_path, plan)
    metadata = load_legacy_compatibility(tmp_path, "writing")
    assert path.name == "legacy-compat.yaml"
    assert metadata["synthetic_lineage_order"] == ["W-1", "W-1-R1", "W-1-R2"]
    assert metadata["source_records_modified"] is False
    assert synthetic_precedes(metadata, "W-1-R1", "W-1-R2")
    assert synthetic_sort_key(metadata, {"attempt_id": "W-1-R2"}) < synthetic_sort_key(metadata, {"attempt_id": "W-OTHER", "submitted_at": "2020"})


def test_compatibility_exceptions_require_exact_event_evidence(tmp_path: Path) -> None:
    path = tmp_path / "tracker/writing/legacy-compat.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "modality": "writing",
                "source_records_modified": False,
                "synthetic_lineage_order": [],
                "approved_exceptions": {
                    "historical_status": [
                        {
                            "event_id": "E-1",
                            "stored_status": "new",
                            "recomputed_status": "recurring",
                            "reason": "Imported before current status policy.",
                        }
                    ],
                    "source_excerpt": [
                        {
                            "event_id": "E-2",
                            "source_excerpt": "legacy paraphrase",
                            "reason": "Imported feedback used a paraphrase.",
                        }
                    ],
                },
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    metadata = load_legacy_compatibility(tmp_path, "writing")

    assert has_approved_status_exception(
        metadata, {"event_id": "E-1", "historical_status": "new"}, "recurring"
    )
    assert not has_approved_status_exception(
        metadata, {"event_id": "E-1", "historical_status": "new"}, "persistent"
    )
    assert has_approved_excerpt_exception(
        metadata, {"event_id": "E-2", "source_excerpt": "legacy paraphrase"}
    )
    assert not has_approved_excerpt_exception(
        metadata, {"event_id": "E-2", "source_excerpt": "different text"}
    )


def test_apply_review_adds_only_exact_approved_exceptions(tmp_path: Path) -> None:
    review = {
        "version": 1,
        "modality": "writing",
        "source_records_modified": False,
        "historical_status_mismatches": [{
            "event_id": "E-STATUS",
            "stored_status": "new",
            "recomputed_status": "recurring",
        }],
        "excerpt_mismatches": [{
            "event_id": "E-EXCERPT",
            "source_excerpt": "legacy paraphrase",
        }],
    }

    path = apply_approved_legacy_review(
        tmp_path, review, reason="Learner approved the reviewed legacy evidence."
    )
    metadata = load_legacy_compatibility(tmp_path, "writing")

    assert path == tmp_path / "tracker/writing/legacy-compat.yaml"
    assert has_approved_status_exception(
        metadata, {"event_id": "E-STATUS", "historical_status": "new"}, "recurring"
    )
    assert has_approved_excerpt_exception(
        metadata, {"event_id": "E-EXCERPT", "source_excerpt": "legacy paraphrase"}
    )
    assert metadata["source_records_modified"] is False
