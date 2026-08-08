"""Opportunity-aware Writing weakness ranking from formal originals only."""

from collections import defaultdict
from pathlib import Path

from toefl_tracker.canonical import load_canonical_events
from toefl_tracker.legacy_migration import load_legacy_compatibility, synthetic_sort_key
from toefl_tracker.io import read_yaml
from toefl_tracker.status import SEVERITY, classify_code


_COUNTED = {"must_fix", "should_fix"}


def _formal_attempts(root: Path) -> list[dict]:
    base = root / "tracker/writing/attempts"
    attempts = [read_yaml(path) for path in base.glob("*/attempt.yaml")] if base.exists() else []
    compatibility = load_legacy_compatibility(root, "writing")
    return [
        attempt
        for attempt in sorted(attempts, key=lambda row: synthetic_sort_key(compatibility, row))
        if attempt.get("record_type") == "formal_original"
    ]


def rank_writing_weaknesses(root: Path, *, limit: int | None = None) -> list[dict]:
    """Rank formal-original weakness signals without counting revisions as recurrence."""
    formals = _formal_attempts(root)
    if not formals:
        return []
    formal_ids = {attempt["attempt_id"] for attempt in formals}
    events = [
        event for event in load_canonical_events(root, "writing")
        if event.get("attempt_id") in formal_ids
        and event.get("level") in _COUNTED
        and event.get("code") != "UNCLASSIFIED"
    ]
    by_code: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_code[event["code"]].append(event)
    recent_ids = {attempt["attempt_id"] for attempt in formals[-3:]}
    ranks: list[dict] = []
    for code, code_events in by_code.items():
        opportunities = sum(
            attempt.get("opportunities", {}).get(code, 0)
            for attempt in formals
            if type(attempt.get("opportunities", {}).get(code, 0)) is int
        )
        recent_opportunities = sum(
            attempt.get("opportunities", {}).get(code, 0)
            for attempt in formals[-3:]
            if type(attempt.get("opportunities", {}).get(code, 0)) is int
        )
        affected_ids = {event["attempt_id"] for event in code_events}
        recent_events = [event for event in code_events if event["attempt_id"] in recent_ids]
        weighted_recent_events = sum(
            index + 1
            for index, attempt in enumerate(formals[-3:])
            for event in recent_events
            if event["attempt_id"] == attempt["attempt_id"]
        )
        max_severity = max(SEVERITY.get(event.get("severity"), 0) for event in code_events)
        status = classify_code(code, formals, code_events) or "not_established"
        score = (
            weighted_recent_events * 10
            + len(affected_ids) * 6
            + max_severity * 3
            + (recent_events.__len__() * 100 / recent_opportunities if recent_opportunities else 0)
        )
        ranks.append({
            "code": code,
            "priority_score": round(score, 2),
            "historical_status": status,
            "formal_records_affected": len(affected_ids),
            "counted_events": len(code_events),
            "opportunities": opportunities,
            "recent_counted_events": len(recent_events),
            "recent_opportunities": recent_opportunities,
            "max_severity": max_severity,
            "evidence": [
                {
                    "attempt_id": event["attempt_id"],
                    "event_id": event["event_id"],
                    "source_excerpt": event.get("source_excerpt", ""),
                }
                for event in sorted(code_events, key=lambda row: (row["attempt_id"], row["event_id"]))
            ],
        })
    ranks.sort(
        key=lambda row: (-row["priority_score"], -row["formal_records_affected"], row["code"])
    )
    return ranks[:limit] if limit is not None else ranks
