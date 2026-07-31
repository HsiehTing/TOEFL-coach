import json
import re
from collections.abc import Mapping
from math import isfinite
from pathlib import Path
from re import Match

import yaml

from toefl_tracker.models import LEVELS, ValidationError
from toefl_tracker.register import register_attempt


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

    duration = attempt.get("duration_seconds")
    if duration is not None and (
        type(duration) not in {int, float}
        or not isfinite(duration)
        or duration <= 0
    ):
        raise ValidationError("speaking duration must be a positive number")
    if not isinstance(segments, list):
        raise ValidationError("speaking segments must be a list of mappings")
    mapped: set[tuple[int, str]] = set()
    for row in segments:
        if not isinstance(row, Mapping):
            raise ValidationError("each speaking segment must be a mapping")
        pair = _validate_segment(row, expected)
        if duration is not None and row["end"] > duration:
            raise ValidationError("speaking segment exceeds session duration")
        if pair in mapped:
            raise ValidationError("incomplete examiner/learner mapping")
        mapped.add(pair)
    expected_pairs = {
        (item, role)
        for item in range(1, expected + 1)
        for role in ("examiner", "learner")
    }
    if mapped != expected_pairs:
        raise ValidationError("incomplete examiner/learner mapping")

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
        _, timestamp_end = _seconds_from_timestamp(timestamp)
        if duration is not None and timestamp_end > duration:
            raise ValidationError("speaking timestamp exceeds session duration")
        if timestamp not in evidence_timestamps:
            raise ValidationError(
                f"feedback omits timestamp: {event.get('event_id')}"
            )


def _validated_inspection(inspection: object) -> tuple[dict, str]:
    if not isinstance(inspection, Mapping):
        raise ValidationError("speaking inspection must be a mapping")
    required = {
        "path",
        "duration_seconds",
        "codec",
        "sample_rate_hz",
        "channels",
        "mean_dbfs",
        "peak_dbfs",
        "clipping",
        "decodable",
    }
    if required - inspection.keys():
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
    persisted = dict(inspection)
    del persisted["path"]
    return persisted, source_path


def register_speaking_session(
    root: Path,
    manifest: dict,
    attempt: dict,
    prompt: str,
    transcript: str,
    feedback: str,
    events: list[dict],
    segments: list[dict],
    inspection: dict,
) -> Path:
    validate_speaking_assessment(attempt, segments, events, feedback)
    persisted_inspection, source_path = _validated_inspection(inspection)
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
            segments,
            allow_unicode=True,
            sort_keys=False,
        ),
        "source-reference.txt": source_path + "\n",
    }
    return register_attempt(
        root,
        manifest,
        attempt,
        prompt,
        transcript,
        feedback,
        events,
        extra_files=extra_files,
    )
