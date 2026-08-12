from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_writing_drill_skill_owns_the_drill_cli_lifecycle() -> None:
    text = (ROOT / ".agents/skills/writing-drill-lifecycle/SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "tools/generate_writing_drill.py" in text
    assert "tools/read_writing_drill.py" in text
    assert "tools/review_writing_drill.py" in text
    assert "tools/register_writing_drill.py" in text
    assert "tools/register_writing_transfer.py" in text
    assert "answer-key.md" in text


def test_tracker_maintenance_only_rebuilds_derived_views() -> None:
    text = (ROOT / ".agents/skills/tracker-maintenance/SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "tools/validate_tracker.py" in text
    assert "tools/rebuild_reports.py" in text
    assert "tools/rebuild_training_plan.py" in text
    assert "tools/rebuild_practice_queue.py" in text
    assert "must not create, overwrite, or hand-edit learner attempts" in text


def test_legacy_migration_requires_review_and_explicit_apply_approval() -> None:
    text = (ROOT / ".agents/skills/legacy-tracker-migration/SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "tools/plan_legacy_tracker_migration.py" in text
    assert "tools/review_legacy_tracker.py" in text
    assert "tools/migrate_event_sidecars.py --dry-run" in text
    assert "explicit approval" in text
    assert "tools/approve_legacy_tracker_review.py --apply" in text
    assert "tools/apply_legacy_tracker_compatibility.py --apply" in text
