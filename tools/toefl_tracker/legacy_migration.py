"""Read-only planner for importing legacy tracker records without rewriting evidence."""

from datetime import datetime
from pathlib import Path

import yaml

from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.models import STATUSES, ValidationError


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


def load_legacy_compatibility(root: Path, modality: str = "writing") -> dict | None:
    """Load declared synthetic ordering; absence means current strict semantics."""
    path = root / "tracker" / modality / "legacy-compat.yaml"
    if not path.exists():
        return None
    data = read_yaml(path)
    exceptions = data.get("approved_exceptions", {"historical_status": [], "source_excerpt": []})
    if (
        data.get("version") != 1
        or data.get("modality") != modality
        or data.get("source_records_modified") is not False
        or not isinstance(data.get("synthetic_lineage_order"), list)
        or any(not isinstance(value, str) or not value for value in data["synthetic_lineage_order"])
        or len(set(data["synthetic_lineage_order"])) != len(data["synthetic_lineage_order"])
        or not isinstance(exceptions, dict)
        or set(exceptions) != {"historical_status", "source_excerpt"}
        or not isinstance(exceptions["historical_status"], list)
        or not isinstance(exceptions["source_excerpt"], list)
    ):
        raise ValidationError("legacy compatibility metadata is invalid")
    status_ids: set[str] = set()
    for item in exceptions["historical_status"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"event_id", "stored_status", "recomputed_status", "reason"}
            or not isinstance(item["event_id"], str)
            or not item["event_id"].strip()
            or item["event_id"] in status_ids
            or item["stored_status"] not in STATUSES
            or (item["recomputed_status"] is not None and item["recomputed_status"] not in STATUSES)
            or not isinstance(item["reason"], str)
            or not item["reason"].strip()
        ):
            raise ValidationError("legacy historical-status exception is invalid")
        status_ids.add(item["event_id"])
    excerpt_ids: set[str] = set()
    for item in exceptions["source_excerpt"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"event_id", "source_excerpt", "reason"}
            or not isinstance(item["event_id"], str)
            or not item["event_id"].strip()
            or item["event_id"] in excerpt_ids
            or not isinstance(item["source_excerpt"], str)
            or not item["source_excerpt"].strip()
            or not isinstance(item["reason"], str)
            or not item["reason"].strip()
        ):
            raise ValidationError("legacy excerpt exception is invalid")
        excerpt_ids.add(item["event_id"])
    return {**data, "approved_exceptions": exceptions}


def write_legacy_compatibility(root: Path, plan: dict) -> Path:
    """Write new compatibility metadata only; source evidence remains untouched."""
    modality = plan.get("modality")
    if modality not in {"writing", "speaking"}:
        raise ValidationError("legacy compatibility plan has invalid modality")
    metadata = {
        "version": 1,
        "modality": modality,
        "source_records_modified": False,
        "synthetic_lineage_order": plan.get("synthetic_lineage_order", []),
        "timestamp_conflict_attempt_ids": plan.get("timestamp_conflict_attempt_ids", []),
        "manual_review": plan.get("manual_review", {}),
        "approved_exceptions": {"historical_status": [], "source_excerpt": []},
    }
    path = root / "tracker" / modality / "legacy-compat.yaml"
    if path.exists() and read_yaml(path) != metadata:
        raise ValidationError("refusing to overwrite existing legacy compatibility metadata")
    atomic_write_text(path, yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False))
    return path


def synthetic_precedes(metadata: dict | None, parent_attempt_id: str, child_attempt_id: str) -> bool:
    if metadata is None:
        return False
    order = metadata.get("synthetic_lineage_order", [])
    try:
        return order.index(parent_attempt_id) < order.index(child_attempt_id)
    except ValueError:
        return False


def synthetic_sort_key(metadata: dict | None, attempt: dict) -> tuple[int, str, str]:
    attempt_id = attempt.get("attempt_id", "")
    order = metadata.get("synthetic_lineage_order", []) if metadata else []
    try:
        return (0, f"{order.index(attempt_id):08d}", attempt_id)
    except ValueError:
        return (1, str(attempt.get("submitted_at", "")), str(attempt_id))


def has_approved_status_exception(
    metadata: dict | None, event: dict, recomputed_status: str | None
) -> bool:
    """Allow only an exact, human-approved legacy status exception."""
    if metadata is None or (recomputed_status is not None and recomputed_status not in STATUSES):
        return False
    return any(
        item["event_id"] == event.get("event_id")
        and item["stored_status"] == event.get("historical_status")
        and item["recomputed_status"] == recomputed_status
        for item in metadata["approved_exceptions"]["historical_status"]
    )


def has_approved_excerpt_exception(metadata: dict | None, event: dict) -> bool:
    """Allow only an exact, human-approved legacy excerpt exception."""
    if metadata is None:
        return False
    return any(
        item["event_id"] == event.get("event_id")
        and item["source_excerpt"] == event.get("source_excerpt")
        for item in metadata["approved_exceptions"]["source_excerpt"]
    )
