import unicodedata
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import re
from typing import Any

from toefl_tracker.models import ValidationError
from toefl_tracker.status import classify_code
from toefl_tracker.taxonomy import TaxonomyEntry, load_taxonomy
from toefl_tracker.validation import validate_error_event


@dataclass(frozen=True)
class SpeakingEvidenceContext:
    learner_segments: Sequence[Mapping[str, object]] = ()
    duration_seconds: float | int | None = None
    reliable_dimensions: Collection[str] = ()
    transcript_only: bool = False


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


def _timestamp_seconds(timestamp: str) -> tuple[int, int]:
    match = re.fullmatch(
        r"([0-5][0-9]):([0-5][0-9])"
        r"(?:–([0-5][0-9]):([0-5][0-9]))?",
        timestamp,
    )
    if match is None:
        raise ValidationError("counted speaking event requires a valid timestamp")
    start = int(match.group(1)) * 60 + int(match.group(2))
    end = (
        int(match.group(3)) * 60 + int(match.group(4))
        if match.group(3) is not None
        else start
    )
    if match.group(3) is not None and end <= start:
        raise ValidationError("counted speaking event has an invalid timestamp range")
    return start, end


def _validate_speaking_evidence(
    event: dict, entry: TaxonomyEntry, context: SpeakingEvidenceContext | None
) -> None:
    if event["level"] not in {"must_fix", "should_fix"}:
        return
    if context is None:
        raise ValidationError("counted speaking event requires evidence context")
    if context.transcript_only:
        excerpt = event.get("source_excerpt")
        if not isinstance(excerpt, str) or not excerpt.strip():
            raise ValidationError("counted speaking event requires a learner transcript excerpt")
        if not any(
            isinstance(segment, Mapping)
            and isinstance(segment.get("text"), str)
            and normalized_contains(segment["text"], excerpt)
            for segment in context.learner_segments
        ):
            raise ValidationError("speaking excerpt is not present in learner transcript")
        dimensions = context.reliable_dimensions
        if entry.dimension not in dimensions:
            raise ValidationError("speaking event requires a reliable dimension")
        return
    timestamp = event.get("audio_timestamp")
    if not isinstance(timestamp, str):
        raise ValidationError("counted speaking event requires a timestamp")
    start, end = _timestamp_seconds(timestamp)
    duration = context.duration_seconds
    if (
        type(duration) not in {int, float}
        or not isfinite(duration)
        or duration <= 0
    ):
        raise ValidationError("speaking evidence context has an invalid duration")
    if end > duration:
        raise ValidationError("speaking timestamp exceeds duration")
    if isinstance(context.learner_segments, (str, bytes)) or not isinstance(
        context.learner_segments, Sequence
    ):
        raise ValidationError("speaking evidence context has invalid learner segments")
    contained = False
    for segment in context.learner_segments:
        if not isinstance(segment, Mapping):
            raise ValidationError("speaking evidence context has invalid learner segments")
        segment_start = segment.get("start")
        segment_end = segment.get("end")
        if (
            type(segment_start) not in {int, float}
            or type(segment_end) not in {int, float}
            or not isfinite(segment_start)
            or not isfinite(segment_end)
            or segment_start < 0
            or segment_end <= segment_start
        ):
            raise ValidationError("speaking evidence context has invalid learner segments")
        contained = contained or (segment_start <= start and segment_end >= end)
    if not contained:
        raise ValidationError("speaking timestamp must be within a learner segment")
    dimensions = context.reliable_dimensions
    if isinstance(dimensions, (str, bytes)) or not isinstance(dimensions, Collection):
        raise ValidationError("speaking evidence context has invalid reliable dimensions")
    if any(not isinstance(dimension, str) for dimension in dimensions):
        raise ValidationError("speaking evidence context has invalid reliable dimensions")
    if entry.dimension not in dimensions:
        raise ValidationError("speaking event requires a reliable dimension")


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
    *,
    allow_legacy_excerpt_exception: bool = False,
    allow_legacy_status_exception: bool = False,
) -> None:
    if not isinstance(attempt, dict):
        raise ValidationError("attempt must be a mapping")
    if not isinstance(event, dict):
        raise ValidationError("error event must be a mapping")
    if not isinstance(response, str):
        raise ValidationError("response must be a string")
    validate_error_event(event)
    entry = _entry_for_event(load_taxonomy(root), attempt, event)
    if event["attempt_id"] != attempt.get("attempt_id"):
        raise ValidationError("event attempt_id does not match current attempt")
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

    opportunities = attempt.get("opportunities")
    code = event["code"]
    if (
        not isinstance(opportunities, Mapping)
        or type(opportunities.get(code)) is not int
        or opportunities[code] <= 0
    ):
        raise ValidationError("event code requires a positive opportunity")
    if entry.taxonomy_review_required:
        if event.get("taxonomy_review_required") is not True:
            raise ValidationError("UNCLASSIFIED requires taxonomy_review_required=true")
        if event["level"] != "polish" or event["historical_status"] is not None:
            raise ValidationError("UNCLASSIFIED is excluded from status and rates")
        return
    if attempt.get("modality") == "writing":
        excerpt = event.get("source_excerpt")
        if (
            not isinstance(excerpt, str)
            or not excerpt.strip()
            or not normalized_contains(response, excerpt)
        ) and not allow_legacy_excerpt_exception:
            raise ValidationError("writing excerpt is not present in immutable response")
    elif attempt.get("modality") == "speaking":
        _validate_speaking_evidence(event, entry, speaking_context)

    expected = expected_historical_status(
        code, attempt, current, previous_attempts, previous_events
    )
    if event.get("historical_status") != expected and not allow_legacy_status_exception:
        raise ValidationError("historical_status does not match recomputed status")
