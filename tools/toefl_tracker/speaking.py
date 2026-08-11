import json
import re
from hashlib import sha256
from collections.abc import Mapping, Sequence
from math import isclose, isfinite
from pathlib import Path
from re import Match

import yaml

from toefl_tracker.event_validation import SpeakingEvidenceContext
from toefl_tracker.audio import AudioInspectionError, inspect_segment_quality
from toefl_tracker.canonical import write_aggregate_events
from toefl_tracker.models import LEVELS, ValidatedPracticeRegistration, ValidationError
from toefl_tracker.role_mapping import MAPPING_METHOD, MAPPING_VERSION, infer_toefl_role_map
from toefl_tracker.register import (
    _registration_lock,
    publish_registration,
    validate_practice_events,
)
from toefl_tracker.validation import validate_attempt
from toefl_tracker.quality import quality_decision
from toefl_tracker.reports import rebuild_modality
from toefl_tracker.speaking_progress import write_speaking_progress_overview


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
    "quality",
    "provenance",
)
_PERSISTED_INSPECTION_FIELDS = tuple(
    field for field in _INSPECTION_FIELDS if field != "path"
) + ("reliable_dimensions",)
_SEGMENT_QUALITY_FIELD = "segment_quality"
_DIMENSION_OBSERVATIONS_FIELD = "audio_dimension_observations"
_DURATION_TOLERANCE_SECONDS = 1e-6
_PROVENANCE_KEYS = {"executables", "model_identifier", "model_sha256"}
_EXECUTABLE_NAMES = {"ffmpeg", "ffprobe", "whisper-cli"}
_AUDIO_PERFORMANCE_DIMENSIONS = {"intelligibility", "pronunciation", "prosody", "fluency"}
def _text_reliable_dimensions(task_type: str) -> set[str]:
    dimensions = {"content", "grammar", "vocabulary"}
    if task_type == "listen_and_repeat":
        dimensions.add("reconstruction")
    return dimensions


def _all_reliable_dimensions(task_type: str) -> set[str]:
    dimensions = {
        "content", "intelligibility", "pronunciation", "prosody", "fluency",
        "grammar", "vocabulary",
    }
    if task_type == "listen_and_repeat":
        dimensions.add("reconstruction")
    elif task_type == "take_an_interview":
        dimensions.update({"directness", "relevance", "elaboration", "coherence"})
    return dimensions


def _normalized_reliable_dimensions(
    source: object, task_type: str, dimension_set: str
) -> set[str]:
    text_dimensions = _text_reliable_dimensions(task_type)
    if dimension_set == "text_only":
        return text_dimensions
    if dimension_set == "all":
        if source is not None and (
            not isinstance(source, (list, tuple, set))
            or any(not isinstance(dimension, str) for dimension in source)
        ):
            raise ValidationError("speaking reliable_dimensions are invalid")
        # Acoustic quality establishes that the recording can support text
        # analysis.  It does not, by itself, establish pronunciation,
        # prosody, fluency, or intelligibility.  Those dimensions require a
        # separate, persisted human-observed artifact below.
        return text_dimensions
    return set()


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
    quality = inspection["quality"]
    if (
        not isinstance(quality, Mapping)
        or set(quality) != {"policy_version", "standard_basis", "usable", "dimension_set"}
        or quality.get("policy_version") != 1
        or quality.get("standard_basis") != "diagnostic_internal"
        or type(quality.get("usable")) is not bool
        or quality.get("dimension_set") not in {"all", "text_only", "none"}
    ):
        raise ValidationError("speaking inspection quality is invalid")
    try:
        expected_quality = quality_decision({
            "mean_dbfs": inspection["mean_dbfs"],
            "peak_dbfs": inspection["peak_dbfs"],
            "decodable": inspection["decodable"],
        })
    except AudioInspectionError as error:
        raise ValidationError("speaking inspection quality is invalid") from error
    if quality != {
        "policy_version": expected_quality.policy_version,
        "standard_basis": expected_quality.standard_basis,
        "usable": expected_quality.usable,
        "dimension_set": expected_quality.dimension_set,
    }:
        raise ValidationError("speaking inspection quality does not match audio metrics")
    if quality["usable"] is not True:
        raise ValidationError("audio quality is insufficient for formal speaking assessment")
    provenance = inspection["provenance"]
    executables = provenance.get("executables") if isinstance(provenance, Mapping) else None
    if (
        not isinstance(provenance, Mapping)
        or set(provenance) != _PROVENANCE_KEYS
        or not isinstance(executables, Mapping)
        or set(executables) != _EXECUTABLE_NAMES
        or any(
            not isinstance(version, str)
            or not version.strip()
            or any(character in version for character in ("/", "\\", "~"))
            for version in executables.values()
        )
        or provenance.get("model_identifier") != "ggml-small.en.bin"
        or not isinstance(provenance.get("model_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", provenance["model_sha256"]) is None
    ):
        raise ValidationError("speaking inspection provenance is invalid")
    persisted = {
        field: inspection[field]
        for field in _PERSISTED_INSPECTION_FIELDS
        if field != "reliable_dimensions"
    }
    persisted["provenance"] = {
        "executables": dict(executables),
        "model_identifier": provenance["model_identifier"],
        "model_sha256": provenance["model_sha256"],
    }
    if _SEGMENT_QUALITY_FIELD in inspection:
        persisted[_SEGMENT_QUALITY_FIELD] = _validate_segment_quality_artifact(
            inspection[_SEGMENT_QUALITY_FIELD]
        )
    return persisted, source_path


def _validate_segment_quality_artifact(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise ValidationError("learner segment quality is invalid")
    validated: list[dict] = []
    for row in value:
        if not isinstance(row, Mapping):
            raise ValidationError("learner segment quality is invalid")
        required = {"segment_id", "start", "end", "mean_dbfs", "peak_dbfs", "clipping", "decodable", "quality", "reliable_dimensions"}
        if set(row) != required:
            raise ValidationError("learner segment quality fields are invalid")
        if (
            not isinstance(row["segment_id"], str)
            or not row["segment_id"].strip()
            or type(row["start"]) not in {int, float}
            or type(row["end"]) not in {int, float}
            or not isfinite(row["start"])
            or not isfinite(row["end"])
            or row["start"] < 0
            or row["end"] <= row["start"]
            or type(row["mean_dbfs"]) not in {int, float}
            or type(row["peak_dbfs"]) not in {int, float}
            or not isfinite(row["mean_dbfs"])
            or not isfinite(row["peak_dbfs"])
            or type(row["clipping"]) is not bool
            or type(row["decodable"]) is not bool
            or not isinstance(row["reliable_dimensions"], list)
            or any(not isinstance(item, str) for item in row["reliable_dimensions"])
        ):
            raise ValidationError("learner segment quality fields are invalid")
        quality = row["quality"]
        if (
            not isinstance(quality, Mapping)
            or set(quality) != {"policy_version", "standard_basis", "usable", "dimension_set"}
            or quality.get("policy_version") != 1
            or quality.get("standard_basis") != "diagnostic_internal"
            or type(quality.get("usable")) is not bool
            or quality.get("dimension_set") not in {"all", "text_only", "none"}
        ):
            raise ValidationError("learner segment quality is invalid")
        try:
            expected = quality_decision({
                "mean_dbfs": row["mean_dbfs"],
                "peak_dbfs": row["peak_dbfs"],
                "decodable": row["decodable"],
            })
        except AudioInspectionError as error:
            raise ValidationError("learner segment quality is invalid") from error
        expected_quality = {
            "policy_version": expected.policy_version,
            "standard_basis": expected.standard_basis,
            "usable": expected.usable,
            "dimension_set": expected.dimension_set,
        }
        if dict(quality) != expected_quality:
            raise ValidationError("learner segment quality does not match audio metrics")
        validated.append(dict(row))
    return validated


def _validated_audio_dimension_observations(
    value: object,
    learner_segments: Sequence[Mapping],
) -> dict[str, set[str]]:
    """Accept only bounded, path-free human evidence for audio dimensions."""
    if value is None:
        return {}
    if not isinstance(value, list):
        raise ValidationError("audio dimension observations are invalid")
    expected = {
        str(segment.get("segment_id")): (segment.get("start"), segment.get("end"))
        for segment in learner_segments
    }
    observed: dict[str, set[str]] = {}
    for row in value:
        if not isinstance(row, Mapping) or set(row) != {
            "segment_id", "start", "end", "observer_type", "observed_at", "dimensions", "evidence_summary"
        }:
            raise ValidationError("audio dimension observation fields are invalid")
        segment_id = row.get("segment_id")
        dimensions = row.get("dimensions")
        if (
            not isinstance(segment_id, str)
            or segment_id not in expected
            or (row.get("start"), row.get("end")) != expected[segment_id]
            or row.get("observer_type") != "human_observed"
            or not isinstance(row.get("observed_at"), str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)", row["observed_at"])
            or not isinstance(dimensions, list)
            or not dimensions
            or not set(dimensions) <= _AUDIO_PERFORMANCE_DIMENSIONS
            or len(set(dimensions)) != len(dimensions)
            or not isinstance(row.get("evidence_summary"), str)
            or not row["evidence_summary"].strip()
            or segment_id in observed
        ):
            raise ValidationError("audio dimension observations are invalid")
        observed[segment_id] = set(dimensions)
    return observed


def _learner_quality(
    inspection: Mapping,
    task_type: str,
    learner_segments: Sequence[Mapping],
) -> tuple[list[dict], set[str]]:
    """Require quality measured on each learner segment, not whole-file averages."""
    artifact = inspection.get(_SEGMENT_QUALITY_FIELD)
    if artifact is None:
        raise ValidationError("learner segment quality is missing")
    rows = _validate_segment_quality_artifact(artifact)
    by_id = {row["segment_id"]: row for row in rows}
    reliable: set[str] | None = None
    for segment in learner_segments:
        quality = by_id.get(segment.get("segment_id"))
        if quality is None or (
            quality["start"] != segment["start"] or quality["end"] != segment["end"]
        ):
            raise ValidationError("learner segment quality does not match mapping")
        if quality["quality"]["usable"] is not True:
            raise ValidationError("learner segment audio quality is insufficient")
        dimensions = _normalized_reliable_dimensions(
            quality["reliable_dimensions"], task_type, quality["quality"]["dimension_set"]
        )
        provided_dimensions = set(quality["reliable_dimensions"])
        if quality["quality"]["dimension_set"] == "text_only" and provided_dimensions != dimensions:
            raise ValidationError("learner segment reliable dimensions are invalid")
        if quality["quality"]["dimension_set"] == "all" and not dimensions <= provided_dimensions:
            raise ValidationError("learner segment reliable dimensions are invalid")
        reliable = dimensions if reliable is None else reliable & dimensions
    if reliable is None:
        raise ValidationError("learner segments are missing")
    reliable &= _normalized_reliable_dimensions(
        inspection.get("reliable_dimensions"),
        task_type,
        inspection["quality"]["dimension_set"],
    )
    observations = _validated_audio_dimension_observations(
        inspection.get(_DIMENSION_OBSERVATIONS_FIELD), learner_segments
    )
    if observations:
        expected_segment_ids = {str(segment.get("segment_id")) for segment in learner_segments}
        if set(observations) != expected_segment_ids:
            raise ValidationError("audio dimension observations must cover every learner segment")
        # A dimension becomes reliable only when every learner turn has its own
        # human-observed, timestamp-aligned evidence.  This conservative
        # intersection prevents a strong recording segment from masking an
        # unobserved one.
        reliable |= set.intersection(*observations.values())
    # The persisted artifact deliberately contains learner turns only.  Whole
    # file and examiner quality never stand in for a learner performance claim.
    return [by_id[str(segment["segment_id"])] for segment in learner_segments], reliable


def validate_persisted_inspection(inspection: object, task_type: str) -> dict:
    """Validate the persisted, path-free inspection artifact used by audit."""
    required_fields = set(_PERSISTED_INSPECTION_FIELDS) - {"reliable_dimensions"}
    if (
        not isinstance(inspection, Mapping)
        or not required_fields <= set(inspection)
        or set(inspection) - required_fields - {"reliable_dimensions", _SEGMENT_QUALITY_FIELD, _DIMENSION_OBSERVATIONS_FIELD}
    ):
        raise ValidationError("speaking inspection fields are invalid")
    persisted, _ = _validated_inspection({"path": "audit-source", **inspection})
    reliable = _normalized_reliable_dimensions(
        inspection.get("reliable_dimensions"), task_type, persisted["quality"]["dimension_set"]
    )
    if (
        inspection.get("reliable_dimensions")
        and persisted["quality"]["dimension_set"] != "all"
        and set(inspection["reliable_dimensions"]) != reliable
    ):
        raise ValidationError("speaking reliable_dimensions are invalid")
    persisted["reliable_dimensions"] = sorted(reliable)
    if _SEGMENT_QUALITY_FIELD in inspection:
        persisted[_SEGMENT_QUALITY_FIELD] = _validate_segment_quality_artifact(
            inspection[_SEGMENT_QUALITY_FIELD]
        )
    if _DIMENSION_OBSERVATIONS_FIELD in inspection:
        learner_segments = [row for row in persisted[_SEGMENT_QUALITY_FIELD] if isinstance(row, Mapping)] if _SEGMENT_QUALITY_FIELD in persisted else []
        # Persisted validation has no role map, but segment-quality contains
        # exactly the learner segments by construction.
        _validated_audio_dimension_observations(inspection[_DIMENSION_OBSERVATIONS_FIELD], learner_segments)
        persisted[_DIMENSION_OBSERVATIONS_FIELD] = inspection[_DIMENSION_OBSERVATIONS_FIELD]
    if _SEGMENT_QUALITY_FIELD in persisted:
        _, reliable = _learner_quality(persisted, task_type, persisted[_SEGMENT_QUALITY_FIELD])
        persisted["reliable_dimensions"] = sorted(reliable)
    return persisted


def validate_transcript_role_mapping(
    task_type: str,
    transcript_segments: object,
    segments: Sequence[dict],
) -> tuple[list[dict], dict[str, object]]:
    """Confirm formal segment roles against source transcript structure.

    ``transcript_segments`` may be the preparation artifact or an explicit raw
    ASR-row list.  The temporary compatibility path derives raw rows from
    richly annotated segments, but it never trusts their supplied roles.
    """
    if isinstance(segments, (str, bytes)) or not isinstance(segments, Sequence):
        raise ValidationError("speaking segments must be a sequence of mappings")
    given_rows = list(segments)
    if any(not isinstance(row, Mapping) for row in given_rows):
        raise ValidationError("speaking segments must be a sequence of mappings")
    if transcript_segments and (
        isinstance(transcript_segments, (str, bytes))
        or not isinstance(transcript_segments, (Mapping, Sequence))
        or (
            not isinstance(transcript_segments, Mapping)
            and any(not isinstance(row, Mapping) for row in transcript_segments)
        )
    ):
        raise ValidationError("transcript_segments must be a mapping artifact or sequence of mappings")

    prepared: Mapping | None = transcript_segments if isinstance(transcript_segments, Mapping) else None
    if prepared is not None:
        raw_rows = prepared.get("transcript_rows")
    elif transcript_segments:
        raw_rows = transcript_segments
    else:
        raw_rows = [
            {key: row.get(key) for key in ("segment_id", "start", "end", "text")}
            for row in given_rows
        ]
    try:
        result = infer_toefl_role_map(task_type, raw_rows)
    except ValidationError as error:
        raise ValidationError(f"transcript role mapping rejected: {error}") from error
    expected_count = ITEM_COUNTS[task_type]
    expected_pairs = [
        (item, role)
        for item in range(1, expected_count + 1)
        for role in ("examiner", "learner")
    ]
    if result.requires_confirmation:
        # A mapper may identify the complete transcript structure while marking
        # only a few rows uncertain.  Let an explicit user confirmation finish
        # those rows; never let confirmation invent a missing or reordered turn.
        if len(given_rows) != len(expected_pairs) or len(raw_rows) != len(expected_pairs):
            raise ValidationError("incomplete confirmed TOEFL transcript role mapping")
        ambiguous_items = {row.item for row in result.ambiguous_rows}
        confirmed_rows: list[dict] = []
        for given, source, (item, role) in zip(given_rows, raw_rows, expected_pairs):
            _validate_segment(given, expected_count)
            if (
                given.get("segment_id") != source.get("segment_id")
                or given.get("start") != source.get("start")
                or given.get("end") != source.get("end")
                or given.get("text") != source.get("text")
                or given.get("item") != item
                or given.get("role") != role
            ):
                raise ValidationError("speaking segments do not match transcript role mapping")
            if item in ambiguous_items and given.get("confirmed_by_user") is not True:
                raise ValidationError("transcript role mapping requires user confirmation")
            row = dict(given)
            row.setdefault("role_reason", "user_confirmed_transcript_structure")
            confirmed_rows.append(row)
        expected_rows = confirmed_rows
    else:
        if len(result.rows) != len(given_rows):
            raise ValidationError("incomplete confirmed TOEFL transcript role mapping")
        expected_rows = [row.artifact() for row in result.rows]
    expected_keys = ("segment_id", "item", "role", "start", "end", "text", "confidence", "role_reason")
    for given, expected in zip(given_rows, expected_rows):
        if any(given.get(key) != expected[key] for key in expected_keys):
            raise ValidationError("speaking segments do not match transcript role mapping")
    if prepared is not None:
        if any(prepared.get(key) != value for key, value in {
            "task_type": task_type,
            "source_transcript_hash": result.source_transcript_hash,
            "mapping_method": MAPPING_METHOD,
            "mapping_version": MAPPING_VERSION,
        }.items()):
            raise ValidationError("transcript role mapping artifact metadata is invalid")
    artifact = result.artifact()
    artifact["rows"] = expected_rows
    artifact["transcript_rows"] = [
        {key: row[key] for key in ("segment_id", "start", "end", "text")}
        for row in expected_rows
    ]
    return expected_rows, artifact


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
    segment_rows, transcript_artifact = validate_transcript_role_mapping(
        bounded_attempt["task_type"], transcript_segments, segments
    )
    learner_segments = tuple(
        row for row in segment_rows if row.get("role") == "learner"
    )
    segment_quality_rows, reliable_dimensions = _learner_quality(
        inspection,
        bounded_attempt["task_type"],
        learner_segments,
    )
    persisted_inspection["segment_quality"] = segment_quality_rows
    if _DIMENSION_OBSERVATIONS_FIELD in inspection:
        persisted_inspection[_DIMENSION_OBSERVATIONS_FIELD] = inspection[_DIMENSION_OBSERVATIONS_FIELD]
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
    persisted_inspection["reliable_dimensions"] = sorted(reliable_dimensions)
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
        "transcript-segments.yaml": yaml.safe_dump(
            transcript_artifact,
            allow_unicode=True,
            sort_keys=False,
        ),
        # Preserve a stable audit reference without committing a local path or URL.
        "source-reference.txt": "source:" + sha256(source_path.encode("utf-8")).hexdigest() + "\n",
    }
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
        rebuild_modality(root, attempt["modality"])
        write_speaking_progress_overview(root)
    return destination
