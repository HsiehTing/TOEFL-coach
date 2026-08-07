from pathlib import Path

import pytest

from toefl_tracker.families import aggregate_family_hits, load_skill_families
from toefl_tracker.models import ValidationError


ROOT = Path(__file__).parents[1]


def _attempt(attempt_id: str, task_type: str, record_type: str = "formal_original") -> dict:
    return {
        "attempt_id": attempt_id,
        "modality": "writing",
        "task_type": task_type,
        "record_type": record_type,
    }


def _event(attempt_id: str, code: str, excerpt: str) -> dict:
    return {
        "attempt_id": attempt_id,
        "code": code,
        "level": "should_fix",
        "source_excerpt": excerpt,
    }


def test_skill_family_file_loads_atomic_codes_and_route_scope() -> None:
    families = load_skill_families(ROOT)

    assert families["IDEA-DEVELOPMENT"].members == (
        "DISCUSSION-ELABORATION",
        "DISCUSSION-SUPPORT",
    )
    assert families["IDEA-DEVELOPMENT"].task_types == ("academic_discussion",)
    assert "LEX-COLLOCATION" in families["LEXICAL-NATURALNESS"].members


def test_family_aggregation_preserves_member_code_attempt_and_excerpt() -> None:
    families = load_skill_families(ROOT)
    attempts = [
        _attempt("W-AD-1", "academic_discussion"),
        _attempt("W-AD-2", "academic_discussion"),
        _attempt("W-AD-R1", "academic_discussion", "revision"),
    ]
    events = [
        _event("W-AD-1", "DISCUSSION-ELABORATION", "named an example"),
        _event("W-AD-2", "DISCUSSION-SUPPORT", "missing causal link"),
        _event("W-AD-R1", "DISCUSSION-SUPPORT", "revision evidence"),
    ]

    summary = aggregate_family_hits(families, attempts, events)
    idea = summary["IDEA-DEVELOPMENT"]

    assert idea["formal_record_count"] == 2
    assert idea["event_count"] == 2
    assert [(row["code"], row["attempt_id"], row["source_excerpt"]) for row in idea["evidence"]] == [
        ("DISCUSSION-ELABORATION", "W-AD-1", "named an example"),
        ("DISCUSSION-SUPPORT", "W-AD-2", "missing causal link"),
    ]


def test_family_aggregation_can_filter_to_a_route() -> None:
    families = load_skill_families(ROOT)
    attempts = [
        _attempt("W-AD-1", "academic_discussion"),
        _attempt("W-EM-1", "email"),
    ]
    events = [
        _event("W-AD-1", "DISCUSSION-SUPPORT", "missing causal link"),
        _event("W-EM-1", "EMAIL-ACTION", "unclear next action"),
    ]

    summary = aggregate_family_hits(families, attempts, events, task_type="academic_discussion")

    assert summary["IDEA-DEVELOPMENT"]["formal_record_count"] == 1
    assert summary["EMAIL-ACTION-CLARITY"]["event_count"] == 0


def test_family_loader_rejects_unknown_or_non_writing_member(tmp_path: Path) -> None:
    (tmp_path / "standards/ets-2026").mkdir(parents=True)
    (tmp_path / "standards/ets-2026/taxonomy.yaml").write_text(
        (ROOT / "standards/ets-2026/taxonomy.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "standards/ets-2026/writing-skill-families.yaml").write_text(
        "version: 1\nfamilies:\n  BAD:\n    members: [SPK-FLUENCY]\n    task_types: [email]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="writing taxonomy member"):
        load_skill_families(tmp_path)


def test_writing_report_emits_family_summary(tmp_path: Path) -> None:
    from test_reports import report_event, write_attempt, write_events
    from toefl_tracker.reports import rebuild_modality

    for attempt_id in ("W-AD-1", "W-AD-2", "W-AD-3"):
        write_attempt(tmp_path, attempt_id, "academic_discussion", "formal_original")
    write_events(
        tmp_path,
        [
            {
                **report_event("W-AD-1", "FAM-1", "DISCUSSION-ELABORATION", task_specific=True),
                "source_excerpt": "named an example",
            },
            {
                **report_event("W-AD-2", "FAM-2", "DISCUSSION-SUPPORT", task_specific=True),
                "source_excerpt": "missing causal link",
            },
        ],
    )

    rebuild_modality(tmp_path, "writing")

    report = (tmp_path / "tracker/writing/reports/writing-academic-discussion-0003.md").read_text(
        encoding="utf-8"
    )
    assert "## Skill families" in report
    assert "`IDEA-DEVELOPMENT`: 2 events in 2 formal records" in report
