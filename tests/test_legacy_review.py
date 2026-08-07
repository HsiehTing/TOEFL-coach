import json
from pathlib import Path

import yaml

from toefl_tracker.legacy_review import build_legacy_review, write_legacy_review


def _event(attempt_id: str, event_id: str, *, status: str, excerpt: str) -> dict:
    return {
        "event_id": event_id,
        "attempt_id": attempt_id,
        "taxonomy_version": 1,
        "code": "GRAM-ARTICLE",
        "source_excerpt": excerpt,
        "audio_timestamp": None,
        "suggested_revision": "Use an article that matches the noun phrase.",
        "reason": "Fixture legacy evidence.",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": status,
    }


def test_review_lists_exact_legacy_status_and_excerpt_findings(
    populated_workspace: Path,
) -> None:
    attempts = populated_workspace / "tracker/writing/attempts"
    first = "W-AD-20260101-001"
    second = "W-AD-20260102-002"
    (attempts / first / "events.jsonl").write_text(
        json.dumps(_event(first, "E-ONE", status="recurring", excerpt=f"Fixture response {first}")) + "\n",
        encoding="utf-8",
    )
    (attempts / second / "events.jsonl").write_text(
        json.dumps(_event(second, "E-TWO", status="new", excerpt="not in the immutable response")) + "\n",
        encoding="utf-8",
    )

    review = build_legacy_review(populated_workspace, "writing")

    assert review["source_records_modified"] is False
    assert review["summary"] == {
        "historical_status_mismatches": 2,
        "excerpt_mismatches": 1,
        "missing_event_sidecars": 0,
        "unreadable_records": 0,
    }
    assert review["historical_status_mismatches"] == [
        {
            "attempt_id": first,
            "event_id": "E-ONE",
            "code": "GRAM-ARTICLE",
            "stored_status": "recurring",
            "recomputed_status": "new",
        },
        {
            "attempt_id": second,
            "event_id": "E-TWO",
            "code": "GRAM-ARTICLE",
            "stored_status": "new",
            "recomputed_status": "recurring",
        },
    ]
    assert review["excerpt_mismatches"] == [
        {
            "attempt_id": second,
            "event_id": "E-TWO",
            "code": "GRAM-ARTICLE",
            "source_excerpt": "not in the immutable response",
        }
    ]


def test_review_reports_missing_sidecar_and_only_writes_explicit_destination(
    populated_workspace: Path, tmp_path: Path
) -> None:
    sidecar = populated_workspace / "tracker/writing/attempts/W-AD-20260101-001/events.jsonl"
    sidecar.unlink()

    review = build_legacy_review(populated_workspace, "writing")
    destination = tmp_path / "review.yaml"
    written = write_legacy_review(destination, review)

    assert review["missing_event_sidecars"] == ["W-AD-20260101-001"]
    assert written == destination
    assert yaml.safe_load(destination.read_text(encoding="utf-8")) == review
    assert not (populated_workspace / "tracker/writing/legacy-review.yaml").exists()
