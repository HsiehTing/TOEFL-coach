import unicodedata
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from toefl_tracker.models import ValidationError
from toefl_tracker.status import classify_code
from toefl_tracker.taxonomy import TaxonomyEntry, load_taxonomy
from toefl_tracker.validation import validate_error_event


@dataclass(frozen=True)
class SpeakingEvidenceContext:
    learner_segments: Sequence[Mapping[str, object]] = ()
    feedback_timestamps: Collection[str] = ()
    duration_seconds: float | int | None = None


def normalized_contains(response: str, excerpt: str) -> bool:
    return unicodedata.normalize("NFC", excerpt.strip()) in unicodedata.normalize("NFC", response)


def expected_historical_status(
    code: str,
    current_attempt: dict,
    current_events: Sequence[dict],
    attempts: Sequence[dict],
    events: Sequence[dict],
) -> str | None:
    return classify_code(code, [*attempts, current_attempt], [*events, *current_events])


def _mapping_rows(rows: Sequence[dict], name: str) -> list[dict]:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValidationError(f"{name} must be a sequence of mappings")
    result = list(rows)
    if any(not isinstance(row, Mapping) for row in result):
        raise ValidationError(f"{name} must be a sequence of mappings")
    return result


def _event_id(row: Mapping[str, Any]) -> str:
    value = row.get("event_id")
    if not isinstance(value, str) or not value:
        raise ValidationError("event_id must be a non-empty string")
    return value


def _validate_speaking_evidence(event: dict, context: SpeakingEvidenceContext) -> None:
    timestamp = event.get("audio_timestamp")
    if not isinstance(timestamp, str):
        return
    if context.feedback_timestamps and timestamp not in context.feedback_timestamps:
        raise ValidationError("speaking feedback omits event timestamp")


def _entry_for_event(
    entries: dict[str, TaxonomyEntry], attempt: dict, event: dict
) -> TaxonomyEntry:
    code = event.get("code")
    if not isinstance(code, str):
        raise ValidationError("event code must be a string")
    entry = entries.get(code)
    if entry is None:
        raise ValidationError(f"unknown taxonomy code: {code}")
    if event.get("taxonomy_version") != entry.taxonomy_version:
        raise ValidationError("event taxonomy_version does not match taxonomy code")
    modality = attempt.get("modality")
    task_type = attempt.get("task_type")
    if not isinstance(modality, str) or not isinstance(task_type, str):
        raise ValidationError("attempt modality and task_type must be strings")
    if entry.modality not in {modality, "all"}:
        raise ValidationError(f"code {code} does not apply to {modality}")
    if task_type not in entry.task_types:
        raise ValidationError(f"code {code} does not apply to {task_type}")
    task_specific = event.get("task_specific")
    if type(task_specific) is not bool:
        raise ValidationError("task_specific must be boolean")
    if task_specific != (entry.scope == "route"):
        raise ValidationError("task_specific does not match taxonomy scope")
    return entry


def validate_event_context(
    root: Path,
    attempt: dict,
    response: str,
    event: dict,
    current_events: Sequence[dict],
    historical_attempts: Sequence[dict],
    historical_events: Sequence[dict],
    speaking_context: SpeakingEvidenceContext | None = None,
) -> None:
    if not isinstance(attempt, dict):
        raise ValidationError("attempt must be a mapping")
    if not isinstance(event, dict):
        raise ValidationError("error event must be a mapping")
    if not isinstance(response, str):
        raise ValidationError("response must be a string")
    validate_error_event(event)
    entry = _entry_for_event(load_taxonomy(root), attempt, event)
    current = _mapping_rows(current_events, "current_events")
    previous_attempts = _mapping_rows(historical_attempts, "historical_attempts")
    previous_events = _mapping_rows(historical_events, "historical_events")
    event_id = _event_id(event)
    other_ids = [
        _event_id(row)
        for row in [*current, *previous_events]
        if row is not event
    ]
    if event_id in other_ids:
        raise ValidationError("event_id already exists")

    if entry.taxonomy_review_required:
        if event.get("taxonomy_review_required") is not True:
            raise ValidationError("UNCLASSIFIED requires taxonomy_review_required=true")
        if event["level"] != "polish" or event["historical_status"] is not None:
            raise ValidationError("UNCLASSIFIED is excluded from status and rates")
        return

    opportunities = attempt.get("opportunities")
    code = event["code"]
    if (
        not isinstance(opportunities, Mapping)
        or type(opportunities.get(code)) is not int
        or opportunities[code] <= 0
    ):
        raise ValidationError("event code requires a positive opportunity")
    if attempt.get("modality") == "writing":
        excerpt = event.get("source_excerpt")
        if (
            not isinstance(excerpt, str)
            or not excerpt.strip()
            or not normalized_contains(response, excerpt)
        ):
            raise ValidationError("writing excerpt is not present in immutable response")
    elif attempt.get("modality") == "speaking" and speaking_context is not None:
        _validate_speaking_evidence(event, speaking_context)

    expected = expected_historical_status(
        code, attempt, current, previous_attempts, previous_events
    )
    if event.get("historical_status") != expected:
        raise ValidationError("historical_status does not match recomputed status")
