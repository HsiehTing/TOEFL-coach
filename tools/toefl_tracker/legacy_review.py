"""Read-only review of legacy tracker records before compatibility approval."""

import json
from pathlib import Path
from typing import Any

import yaml

from toefl_tracker.event_validation import (
    expected_historical_status,
    normalized_contains,
)
from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.legacy_migration import load_legacy_compatibility, synthetic_sort_key
from toefl_tracker.models import ValidationError


_COUNTED_LEVELS = {"must_fix", "should_fix"}


def _response_name(attempt: dict[str, Any]) -> str:
    if attempt["modality"] == "writing":
        return "response-revision.md" if attempt["record_type"] == "revision" else "response-original.md"
    return "transcript-revision.md" if attempt["record_type"] == "revision" else "transcript-original.md"


def _read_events(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValidationError("legacy event must be a JSON mapping")
            rows.append(row)
    return rows


def _empty_review(modality: str) -> dict[str, Any]:
    return {
        "version": 1,
        "modality": modality,
        "source_records_modified": False,
        "missing_event_sidecars": [],
        "historical_status_mismatches": [],
        "excerpt_mismatches": [],
        "unreadable_records": [],
    }


def _summary(review: dict[str, Any]) -> dict[str, int]:
    return {
        "historical_status_mismatches": len(review["historical_status_mismatches"]),
        "excerpt_mismatches": len(review["excerpt_mismatches"]),
        "missing_event_sidecars": len(review["missing_event_sidecars"]),
        "unreadable_records": len(review["unreadable_records"]),
    }


def build_legacy_review(root: Path, modality: str = "writing") -> dict[str, Any]:
    """List compatibility decisions needed without changing source records."""
    if modality not in {"writing", "speaking"}:
        raise ValidationError("legacy review modality must be writing or speaking")

    review = _empty_review(modality)
    attempts_root = root / "tracker" / modality / "attempts"
    attempts: list[dict[str, Any]] = []
    sidecars: dict[str, list[dict[str, Any]]] = {}
    responses: dict[str, str] = {}

    for directory in sorted(attempts_root.glob("*")) if attempts_root.exists() else []:
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        attempt_path = directory / "attempt.yaml"
        try:
            attempt = read_yaml(attempt_path)
            attempt_id = attempt.get("attempt_id")
            if not isinstance(attempt_id, str) or attempt_id != directory.name:
                raise ValidationError("attempt_id does not match directory")
            if attempt.get("modality") != modality:
                raise ValidationError("attempt modality does not match review route")
        except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError, ValidationError) as error:
            review["unreadable_records"].append({"path": str(attempt_path), "reason": str(error)})
            continue
        attempts.append(attempt)

        sidecar = directory / "events.jsonl"
        if not sidecar.exists():
            review["missing_event_sidecars"].append(attempt_id)
            sidecars[attempt_id] = []
        else:
            try:
                sidecars[attempt_id] = _read_events(sidecar)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
                review["unreadable_records"].append({"path": str(sidecar), "reason": str(error)})
                sidecars[attempt_id] = []

        response_path = directory / _response_name(attempt)
        if modality == "writing" and attempt.get("record_type") != "re_evaluation":
            try:
                responses[attempt_id] = response_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                review["unreadable_records"].append({"path": str(response_path), "reason": str(error)})

    compatibility = load_legacy_compatibility(root, modality)
    ordered = sorted(attempts, key=lambda row: synthetic_sort_key(compatibility, row))
    history_attempts: list[dict[str, Any]] = []
    history_events: list[dict[str, Any]] = []
    for attempt in ordered:
        attempt_id = attempt["attempt_id"]
        current_events = sidecars[attempt_id]
        response = responses.get(attempt_id)
        for event in current_events:
            event_id = event.get("event_id")
            code = event.get("code")
            if not isinstance(event_id, str) or not isinstance(code, str):
                review["unreadable_records"].append({
                    "path": str(attempts_root / attempt_id / "events.jsonl"),
                    "reason": "legacy event requires string event_id and code",
                })
                continue
            if attempt["modality"] == "writing" and event.get("level") in _COUNTED_LEVELS:
                excerpt = event.get("source_excerpt")
                if (
                    not isinstance(excerpt, str)
                    or response is None
                    or not normalized_contains(response, excerpt)
                ):
                    review["excerpt_mismatches"].append({
                        "attempt_id": attempt_id,
                        "event_id": event_id,
                        "code": code,
                        "source_excerpt": excerpt if isinstance(excerpt, str) else "",
                    })
            expected = expected_historical_status(
                code, attempt, current_events, history_attempts, history_events
            )
            if event.get("historical_status") != expected:
                review["historical_status_mismatches"].append({
                    "attempt_id": attempt_id,
                    "event_id": event_id,
                    "code": code,
                    "stored_status": event.get("historical_status"),
                    "recomputed_status": expected,
                })
        history_attempts.append(attempt)
        history_events.extend(current_events)

    for key in ("missing_event_sidecars", "historical_status_mismatches", "excerpt_mismatches", "unreadable_records"):
        review[key] = sorted(review[key], key=lambda row: str(row))
    review["summary"] = _summary(review)
    return review


def write_legacy_review(destination: Path, review: dict[str, Any]) -> Path:
    """Write a review only to the caller-selected destination."""
    if review.get("source_records_modified") is not False:
        raise ValidationError("legacy review must declare source_records_modified=false")
    atomic_write_text(destination, yaml.safe_dump(review, allow_unicode=True, sort_keys=False))
    return destination
