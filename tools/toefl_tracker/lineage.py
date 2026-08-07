"""Validated attempt lineage and revision-chain summaries."""

from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime

from toefl_tracker.legacy_migration import synthetic_precedes, synthetic_sort_key
from toefl_tracker.models import ValidationError


def _index(attempts: Iterable[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for attempt in attempts:
        attempt_id = attempt.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise ValidationError("attempt lineage requires a non-empty attempt_id")
        if attempt_id in index:
            raise ValidationError(f"duplicate attempt in lineage: {attempt_id}")
        index[attempt_id] = attempt
    return index


def _submitted_at(attempt: dict) -> datetime:
    try:
        return datetime.fromisoformat(attempt["submitted_at"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError(
            f"invalid submitted_at in lineage: {attempt.get('attempt_id', '<unknown>')}"
        ) from error


def root_formal_attempt(
    attempt_id: str, attempts: Iterable[dict], *, compatibility: dict | None = None
) -> dict:
    """Return the formal original at the root of an attempt's revision chain.

    The function validates the traversed graph so reports cannot silently omit
    a nested revision or accept a cross-route/cyclic parent relationship.
    """

    index = _index(attempts)
    if attempt_id not in index:
        raise ValidationError(f"missing lineage attempt: {attempt_id}")

    current = index[attempt_id]
    visited: set[str] = set()
    while True:
        current_id = current["attempt_id"]
        if current_id in visited:
            raise ValidationError(f"cycle in revision lineage: {current_id}")
        visited.add(current_id)

        record_type = current.get("record_type")
        if record_type == "formal_original":
            if current.get("parent_attempt_id") is not None:
                raise ValidationError(f"formal original has parent: {current_id}")
            return current
        if record_type != "revision":
            raise ValidationError(
                f"unsupported parent record in revision lineage: {current_id}"
            )

        parent_id = current.get("parent_attempt_id")
        if not isinstance(parent_id, str) or not parent_id:
            raise ValidationError(f"missing parent for revision: {current_id}")
        parent = index.get(parent_id)
        if parent is None:
            raise ValidationError(f"missing parent for revision: {current_id}")
        if parent_id in visited:
            raise ValidationError(f"cycle in revision lineage: {parent_id}")
        if (
            parent.get("modality") != current.get("modality")
            or parent.get("task_type") != current.get("task_type")
        ):
            raise ValidationError(f"cross-route parent for revision: {current_id}")
        if (
            _submitted_at(parent) > _submitted_at(current)
            and not synthetic_precedes(compatibility, parent_id, current_id)
        ):
            raise ValidationError(f"parent submitted after revision: {current_id}")
        current = parent


def revision_chain(
    root_id: str, attempts: Iterable[dict], *, compatibility: dict | None = None
) -> list[dict]:
    """Return every revision descending from a formal original in time order."""

    rows = list(attempts)
    root = root_formal_attempt(root_id, rows, compatibility=compatibility)
    if root["attempt_id"] != root_id:
        raise ValidationError(f"lineage root is not a formal original: {root_id}")

    descendants: list[dict] = []
    for attempt in rows:
        if attempt.get("record_type") != "revision":
            continue
        if root_formal_attempt(
            attempt["attempt_id"], rows, compatibility=compatibility
        )["attempt_id"] == root_id:
            descendants.append(attempt)
    descendants.sort(key=lambda row: synthetic_sort_key(compatibility, row))
    return descendants


def _score(attempt: dict) -> object:
    return attempt.get("task_score", {}).get("value")


def _full_resolution(outcomes: dict | None) -> bool:
    if not isinstance(outcomes, dict):
        return False
    return (
        outcomes.get("assigned", 0) > 0
        and outcomes.get("resolved") == outcomes.get("assigned")
        and outcomes.get("partly_resolved") == 0
        and outcomes.get("unresolved") == 0
    )


def lineage_summary(
    root_id: str, attempts: Iterable[dict], *, compatibility: dict | None = None
) -> dict:
    """Build a stable, report-ready summary for one formal original."""

    rows = list(attempts)
    root = root_formal_attempt(root_id, rows, compatibility=compatibility)
    revisions = revision_chain(root_id, rows, compatibility=compatibility)
    full_round = next(
        (number for number, row in enumerate(revisions, start=1) if _full_resolution(row.get("revision_outcomes"))),
        None,
    )
    latest = revisions[-1] if revisions else None
    return {
        "root_attempt_id": root_id,
        "revision_ids": [row["attempt_id"] for row in revisions],
        "latest_revision_id": latest["attempt_id"] if latest else None,
        "round_count": len(revisions),
        "score_trajectory": [_score(root), *[_score(row) for row in revisions]],
        "latest_outcome": deepcopy(latest.get("revision_outcomes")) if latest else None,
        "first_full_resolution_round": full_round,
        "total_new_errors": sum(
            row.get("revision_outcomes", {}).get("new_errors", 0) for row in revisions
        ),
        "switch_recommended_after_round": 2,
    }
