"""Read-only planner for importing legacy tracker records without rewriting evidence."""

from datetime import datetime
from pathlib import Path

from toefl_tracker.io import read_yaml
from toefl_tracker.models import ValidationError


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValidationError("legacy attempt submitted_at must be an ISO timestamp")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise ValidationError("legacy attempt submitted_at must be an ISO timestamp") from error


def _topological_attempt_ids(attempts: dict[str, dict]) -> list[str]:
    ordered: list[str] = []
    remaining = set(attempts)
    while remaining:
        ready = sorted(
            attempt_id for attempt_id in remaining
            if attempts[attempt_id].get("record_type") != "revision"
            or attempts[attempt_id].get("parent_attempt_id") in ordered
        )
        if not ready:
            raise ValidationError("legacy revision lineage contains a missing parent or cycle")
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


def build_legacy_migration_plan(root: Path, modality: str = "writing") -> dict:
    attempts_root = root / "tracker" / modality / "attempts"
    attempts = {
        path.parent.name: read_yaml(path)
        for path in attempts_root.glob("*/attempt.yaml")
    } if attempts_root.exists() else {}
    for attempt_id, attempt in attempts.items():
        if attempt.get("attempt_id") != attempt_id:
            raise ValidationError("legacy attempt directory does not match attempt_id")
        _timestamp(attempt.get("submitted_at"))
    order = _topological_attempt_ids(attempts)
    timestamp_conflicts = [
        attempt_id for attempt_id in order
        if attempts[attempt_id].get("record_type") == "revision"
        and _timestamp(attempts[attempts[attempt_id]["parent_attempt_id"]]["submitted_at"]) >= _timestamp(attempts[attempt_id]["submitted_at"])
    ]
    return {
        "version": 1,
        "modality": modality,
        "source_records_modified": False,
        "missing_event_sidecars": sorted(
            attempt_id for attempt_id in attempts
            if not (attempts_root / attempt_id / "events.jsonl").exists()
        ),
        "synthetic_lineage_order": order if timestamp_conflicts else [],
        "timestamp_conflict_attempt_ids": timestamp_conflicts,
        "manual_review": {
            "historical_status": "Preserve legacy event values; review before converting them to current status semantics.",
            "evidence_excerpts": "Review any event excerpt that does not occur in its immutable response before registering a compatibility exception.",
        },
    }
