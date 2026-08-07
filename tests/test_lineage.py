import pytest

from toefl_tracker.lineage import (
    lineage_summary,
    revision_chain,
    root_formal_attempt,
)
from toefl_tracker.models import ValidationError


def _attempt(
    attempt_id: str,
    record_type: str,
    submitted_at: str,
    parent_attempt_id: str | None = None,
    score: int = 3,
) -> dict:
    return {
        "attempt_id": attempt_id,
        "modality": "writing",
        "task_type": "academic_discussion",
        "record_type": record_type,
        "submitted_at": submitted_at,
        "parent_attempt_id": parent_attempt_id,
        "task_score": {"value": score},
        "revision_outcomes": (
            {
                "assigned": 3,
                "resolved": score - 3,
                "partly_resolved": 3 - (score - 3),
                "unresolved": 0,
                "new_errors": 0,
                "resolution_rate": (score - 3) / 3,
            }
            if record_type == "revision"
            else None
        ),
    }


def test_revision_chain_resolves_nested_revisions_to_root_formal() -> None:
    attempts = [
        _attempt("F-1", "formal_original", "2026-08-01T10:00:00+08:00"),
        _attempt("F-1-R1", "revision", "2026-08-01T10:10:00+08:00", "F-1"),
        _attempt("F-1-R2", "revision", "2026-08-01T10:20:00+08:00", "F-1-R1"),
        _attempt("F-1-R3", "revision", "2026-08-01T10:30:00+08:00", "F-1-R2", 4),
    ]
    attempts[-1]["revision_outcomes"] = {
        "assigned": 3,
        "resolved": 3,
        "partly_resolved": 0,
        "unresolved": 0,
        "new_errors": 0,
        "resolution_rate": 1.0,
    }

    assert root_formal_attempt("F-1-R3", attempts)["attempt_id"] == "F-1"
    assert [row["attempt_id"] for row in revision_chain("F-1", attempts)] == [
        "F-1-R1", "F-1-R2", "F-1-R3"
    ]

    summary = lineage_summary("F-1", attempts)
    assert summary["revision_ids"] == ["F-1-R1", "F-1-R2", "F-1-R3"]
    assert summary["latest_revision_id"] == "F-1-R3"
    assert summary["round_count"] == 3
    assert summary["score_trajectory"] == [3, 3, 3, 4]
    assert summary["first_full_resolution_round"] == 3


@pytest.mark.parametrize(
    "rows, message",
    [
        (
            [
                _attempt("F-1", "formal_original", "2026-08-01T10:00:00+08:00"),
                _attempt("F-1-R1", "revision", "2026-08-01T10:10:00+08:00", "MISSING"),
            ],
            "missing parent",
        ),
        (
            [
                _attempt("F-1", "formal_original", "2026-08-01T10:00:00+08:00"),
                _attempt("F-1-R1", "revision", "2026-08-01T10:10:00+08:00", "F-1-R2"),
                _attempt("F-1-R2", "revision", "2026-08-01T10:20:00+08:00", "F-1-R1"),
            ],
            "cycle",
        ),
    ],
)
def test_lineage_rejects_invalid_parent_graph(rows: list[dict], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        root_formal_attempt(rows[-1]["attempt_id"], rows)


def test_lineage_accepts_explicit_legacy_order_but_not_unapproved_timestamp_reversal() -> None:
    rows = [
        _attempt("F-1", "formal_original", "2026-08-02T10:00:00+08:00"),
        _attempt("F-1-R1", "revision", "2026-08-01T10:00:00+08:00", "F-1"),
    ]

    with pytest.raises(ValidationError, match="parent submitted after revision"):
        root_formal_attempt("F-1-R1", rows)

    compatibility = {"synthetic_lineage_order": ["F-1", "F-1-R1"]}
    assert root_formal_attempt(
        "F-1-R1", rows, compatibility=compatibility
    )["attempt_id"] == "F-1"


def test_report_contract_requires_chain_section(tmp_path) -> None:
    from test_reports import write_attempt
    from toefl_tracker.reports import rebuild_modality

    write_attempt(tmp_path, "W-AD-1", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2-R1", "academic_discussion", "revision")
    write_attempt(tmp_path, "W-AD-2-R2", "academic_discussion", "revision")
    write_attempt(tmp_path, "W-AD-3", "academic_discussion", "formal_original")
    (tmp_path / "tracker/writing/attempts/W-AD-2-R2/attempt.yaml").write_text(
        (tmp_path / "tracker/writing/attempts/W-AD-2-R2/attempt.yaml")
        .read_text(encoding="utf-8")
        .replace("parent_attempt_id: W-AD-2", "parent_attempt_id: W-AD-2-R1"),
        encoding="utf-8",
    )

    rebuild_modality(tmp_path, "writing")

    report = (tmp_path / "tracker/writing/reports/writing-common-0003.md").read_text(
        encoding="utf-8"
    )
    assert "## Revision chains" in report
    assert "W-AD-2-R2" in report
