import json
import re
from hashlib import sha256
from collections.abc import Mapping, Sequence
from math import isclose, isfinite
from pathlib import Path
from re import Match

import yaml

from toefl_tracker.event_validation import SpeakingEvidenceContext
from toefl_tracker.canonical import write_aggregate_events
from toefl_tracker.models import LEVELS, ValidatedPracticeRegistration, ValidationError
from toefl_tracker.register import (
    _registration_lock,
    publish_registration,
    validate_practice_events,
)
from toefl_tracker.validation import validate_attempt


ITEM_COUNTS = {"listen_and_repeat": 7, "take_an_interview": 4}
REQUIRED_HEADINGS = (
    "# Result",
    "# Why this level",
    "# Why not the next level",
    "# Timestamp evidence",
    "# Priorities",
    "# Re-record task",
)
_TIMESTAMP_TOKEN = (
    r"[0-5][0-9]:[0-5][0-9]"
    r"(?:–[0-5][0-9]:[0-5][0-9])?"
)
_INSPECTION_FIELDS = (
    "path",
    "duration_seconds",
    "codec",
    "sample_rate_hz",
    "channels",
    "mean_dbfs",
    "peak_dbfs",
    "clipping",
    "decodable",
)
_PERSISTED_INSPECTION_FIELDS = tuple(
    field for field in _INSPECTION_FIELDS if field != "path"
)
_DURATION_TOLERANCE_SECONDS = 1e-6


def _ordered_heading_matches(feedback: str) -> list[Match[str]]:
    if not isinstance(feedback, str):
        raise ValidationError("speaking feedback is missing required headings")
    matches = list(
        re.finditer(r"(?m)^(# [^\r\n]+?)[ \t]*\r?$", feedback)
    )
    headings = tuple(match.group(1) for match in matches)
    if headings != REQUIRED_HEADINGS:
        raise ValidationError(
            "speaking feedback headings are missing, duplicated, or out of order"
        )
    return matches


def _seconds_from_timestamp(timestamp: str) -> tuple[int, int]:
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


def _validate_segment(row: Mapping, expected_items: int) -> tuple[int, str]:
    item = row.get("item")
    if type(item) is not int or not 1 <= item <= expected_items:
        raise ValidationError("speaking segment item is invalid")
    role = row.get("role")
    if not isinstance(role, str) or role not in {"examiner", "learner"}:
        raise ValidationError("speaking segment role is invalid")
    start = row.get("start")
    end = row.get("end")
    if (
        type(start) not in {int, float}
        or type(end) not in {int, float}
        or not isfinite(start)
        or not isfinite(end)
        or start < 0
        or end <= start
    ):
        raise ValidationError("speaking segment time range is invalid")
    confidence = row.get("confidence")
    if (
        not isinstance(confidence, str)
        or confidence not in {"high", "medium", "low"}
    ):
        raise ValidationError("speaking segment confidence is invalid")
    if "confirmed_by_user" in row and type(row["confirmed_by_user"]) is not bool:
        raise ValidationError("mapping confirmation must be boolean")
    if confidence != "high" and row.get("confirmed_by_user") is not True:
        raise ValidationError("ambiguous mapping requires user confirmation")
    return item, role


def validate_speaking_assessment(
    attempt: dict,
    segments: list[dict],
    events: list[dict],
    feedback: str,
) -> None:
    if not isinstance(attempt, Mapping):
        raise ValidationError("speaking attempt must be a mapping")
    if attempt.get("modality") != "speaking":
        raise ValidationError("speaking assessment requires speaking modality")
    task_type = attempt.get("task_type")
    expected = ITEM_COUNTS.get(task_type) if isinstance(task_type, str) else None
    if expected is None:
        raise ValidationError("unknown speaking task")
    if (
        attempt.get("rubric_version")
        != "ets-speaking-blueprint-2026-diagnostic"
    ):
        raise ValidationError("speaking rubric mismatch")
    if attempt.get("result_type") != "diagnostic_only":
        raise ValidationError("speaking session must be diagnostic_only")

    audio_quality = attempt.get("audio_quality")
    if not isinstance(audio_quality, Mapping) or any(
        type(audio_quality.get(field)) is not bool
        for field in ("decodable", "clipping")
    ):
        raise ValidationError("speaking audio_quality must contain booleans")
    if audio_quality["decodable"] is not True:
        raise ValidationError("speaking audio must be decodable")
    if audio_quality["clipping"] is True:
        raise ValidationError("clipped audio cannot be used for a formal speaking assessment")

    duration = attempt.get("duration_seconds")
    if duration is not None and (
        type(duration) not in {int, float}
        or not isfinite(duration)
        or duration <= 0
    ):
        raise ValidationError("speaking duration must be a positive number")
    if not isinstance(segments, list):
        raise ValidationError("speaking segments must be a list of mappings")
    mapped: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()
    previous_end: float | int | None = None
    for row in segments:
        if not isinstance(row, Mapping):
            raise ValidationError("each speaking segment must be a mapping")
        pair = _validate_segment(row, expected)
        if previous_end is not None and row["start"] < previous_end:
            raise ValidationError(
                "speaking segments overlap or are not chronological"
            )
        if duration is not None and row["end"] > duration:
            raise ValidationError("speaking segment exceeds session duration")
        if pair in seen:
            raise ValidationError("incomplete examiner/learner mapping")
        mapped.append(pair)
        seen.add(pair)
        previous_end = row["end"]
    expected_pairs = [
        (item, role)
        for item in range(1, expected + 1)
        for role in ("examiner", "learner")
    ]
    if seen != set(expected_pairs):
        raise ValidationError("incomplete examiner/learner mapping")
    if mapped != expected_pairs:
        raise ValidationError(
            "speaking segments must follow item and role order"
        )

    heading_matches = _ordered_heading_matches(feedback)
    timestamp_block = feedback[
        heading_matches[-3].end():heading_matches[-2].start()
    ]
    priority_block = feedback[
        heading_matches[-2].end():heading_matches[-1].start()
    ]
    if len(re.findall(r"(?m)^\d+\.\s", priority_block)) > 3:
        raise ValidationError("first-round feedback exceeds three priorities")
    evidence_timestamps = set(re.findall(_TIMESTAMP_TOKEN, timestamp_block))

    if not isinstance(events, list):
        raise ValidationError("speaking events must be a list of mappings")
    for event in events:
        if not isinstance(event, Mapping):
            raise ValidationError("each speaking event must be a mapping")
        level = event.get("level")
        if not isinstance(level, str) or level not in LEVELS:
            raise ValidationError("speaking event level is invalid")
        if level not in {"must_fix", "should_fix"}:
            continue
        timestamp = event.get("audio_timestamp")
        if not isinstance(timestamp, str):
            raise ValidationError("counted speaking event requires a timestamp")
        timestamp_start, timestamp_end = _seconds_from_timestamp(timestamp)
        if duration is not None and timestamp_end > duration:
            raise ValidationError("speaking timestamp exceeds session duration")
        if not any(
            row["role"] == "learner"
            and row["start"] <= timestamp_start
            and row["end"] >= timestamp_end
            for row in segments
        ):
            raise ValidationError("speaking timestamp must be within a learner segment")
        if timestamp not in evidence_timestamps:
            raise ValidationError(
                f"feedback omits timestamp: {event.get('event_id')}"
            )


def _validated_inspection(inspection: object) -> tuple[dict, str]:
    if not isinstance(inspection, Mapping):
        raise ValidationError("speaking inspection must be a mapping")
    if set(_INSPECTION_FIELDS) - inspection.keys():
        raise ValidationError("speaking inspection is missing required fields")
    source_path = inspection["path"]
    if (
        not isinstance(source_path, str)
        or not source_path.strip()
        or "\n" in source_path
        or "\r" in source_path
    ):
        raise ValidationError("speaking inspection path is invalid")
    if (
        type(inspection["duration_seconds"]) not in {int, float}
        or not isfinite(inspection["duration_seconds"])
        or inspection["duration_seconds"] <= 0
        or type(inspection["sample_rate_hz"]) is not int
        or inspection["sample_rate_hz"] <= 0
        or type(inspection["channels"]) is not int
        or inspection["channels"] <= 0
        or type(inspection["mean_dbfs"]) not in {int, float}
        or not isfinite(inspection["mean_dbfs"])
        or type(inspection["peak_dbfs"]) not in {int, float}
        or not isfinite(inspection["peak_dbfs"])
        or not isinstance(inspection["codec"], str)
        or not inspection["codec"]
        or type(inspection["clipping"]) is not bool
        or type(inspection["decodable"]) is not bool
    ):
        raise ValidationError("speaking inspection field types are invalid")
    persisted = {
        field: inspection[field]
        for field in _PERSISTED_INSPECTION_FIELDS
    }
    return persisted, source_path


def build_speaking_registration(
    root: Path,
    manifest: dict,
    attempt: dict,
    prompt: str,
    transcript: str,
    feedback: str,
    events: Sequence[dict],
    segments: Sequence[dict],
    inspection: dict,
    transcript_segments: Sequence[dict] = (),
) -> ValidatedPracticeRegistration:
    validate_attempt(attempt, manifest)
    if isinstance(transcript_segments, (str, bytes)) or not isinstance(
        transcript_segments, Sequence
    ) or any(not isinstance(row, Mapping) for row in transcript_segments):
        raise ValidationError("transcript_segments must be a sequence of mappings")
    persisted_inspection, source_path = _validated_inspection(inspection)
    if not isinstance(attempt, Mapping):
        raise ValidationError("speaking attempt must be a mapping")
    inspection_duration = persisted_inspection["duration_seconds"]
    attempt_duration = attempt.get("duration_seconds")
    if attempt_duration is not None and (
        type(attempt_duration) not in {int, float}
        or not isfinite(attempt_duration)
        or attempt_duration <= 0
    ):
        raise ValidationError("speaking duration must be a positive number")
    if attempt_duration is not None and not isclose(
        attempt_duration,
        inspection_duration,
        rel_tol=0.0,
        abs_tol=_DURATION_TOLERANCE_SECONDS,
    ):
        raise ValidationError(
            "attempt duration does not match audio inspection duration"
        )
    bounded_attempt = dict(attempt)
    bounded_attempt["duration_seconds"] = inspection_duration
    event_rows = tuple(events)
    segment_rows = list(segments)
    validate_speaking_assessment(
        bounded_attempt,
        segment_rows,
        list(event_rows),
        feedback,
    )
    if attempt.get("audio_quality") != {
        "decodable": persisted_inspection["decodable"],
        "clipping": persisted_inspection["clipping"],
    }:
        raise ValidationError(
            "attempt audio_quality does not match inspection"
        )
    extra_files = {
        "audio-inspection.json": (
            json.dumps(
                persisted_inspection,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ),
        "segments.yaml": yaml.safe_dump(
            segment_rows,
            allow_unicode=True,
            sort_keys=False,
        ),
        # Preserve a stable audit reference without committing a local path or URL.
        "source-reference.txt": "source:" + sha256(source_path.encode("utf-8")).hexdigest() + "\n",
    }
    reliable_dimensions = inspection.get("reliable_dimensions")
    if reliable_dimensions is None:
        # Reliability policy arrives with the transcript-preparation task. Until
        # then, the confirmed technical/mapping gate supports all dimensions.
        reliable_dimensions = {
            "intelligibility", "pronunciation", "prosody", "fluency", "grammar",
            "vocabulary", "reconstruction", "directness", "relevance",
            "elaboration", "coherence",
        }
    learner_segments = tuple(
        row for row in segment_rows if row.get("role") == "learner"
    )
    speaking_context = SpeakingEvidenceContext(
        learner_segments=learner_segments,
        duration_seconds=persisted_inspection["duration_seconds"],
        reliable_dimensions=reliable_dimensions,
    )
    with _registration_lock(root):
        validate_practice_events(
            root, attempt, transcript, event_rows, speaking_context
        )
    return ValidatedPracticeRegistration(
        attempt=attempt,
        prompt=prompt,
        response=transcript,
        feedback=feedback,
        events=event_rows,
        extra_files=extra_files,
        require_contextual_validation=True,
        speaking_context=speaking_context,
    )


def register_speaking_session(
    root: Path,
    manifest: dict,
    attempt: dict,
    prompt: str,
    transcript: str,
    feedback: str,
    events: Sequence[dict],
    segments: Sequence[dict],
    inspection: dict,
    transcript_segments: Sequence[dict] = (),
) -> Path:
    registration = build_speaking_registration(
        root,
        manifest,
        attempt,
        prompt,
        transcript,
        feedback,
        events,
        segments,
        inspection,
        transcript_segments,
    )
    destination = publish_registration(
        root,
        manifest,
        registration,
    )
    with _registration_lock(root):
        write_aggregate_events(root, attempt["modality"])
    return destination
