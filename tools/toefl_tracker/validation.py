import re
from datetime import date, datetime
from math import isclose

from toefl_tracker.models import (
    LEVELS, MODALITIES, RECORD_TYPES, SEVERITIES, STATUSES, TASK_TYPES, ValidationError
)


REQUIRED_ATTEMPT_FIELDS = {
    "schema_version", "attempt_id", "modality", "task_type", "record_type",
    "submitted_at", "practiced_at", "timed", "duration_seconds", "assistance",
    "rubric_version", "standard_verified_at", "task_metrics", "source_hash",
    "opportunities", "parent_attempt_id", "revision_outcomes",
}


def validate_attempt(data: dict, manifest: dict) -> None:
    if not isinstance(data, dict):
        raise ValidationError("attempt must be a mapping")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("rubrics"), dict):
        raise ValidationError("manifest rubrics must be a mapping")
    missing = REQUIRED_ATTEMPT_FIELDS - data.keys()
    if missing:
        raise ValidationError(f"missing attempt fields: {sorted(missing)}")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValidationError("unsupported attempt schema_version")
    if not isinstance(data["modality"], str) or data["modality"] not in MODALITIES:
        raise ValidationError("invalid modality")
    if not isinstance(data["task_type"], str) or data["task_type"] not in TASK_TYPES[data["modality"]]:
        raise ValidationError("task_type does not match modality")
    if not isinstance(data["record_type"], str) or data["record_type"] not in RECORD_TYPES:
        raise ValidationError("invalid record_type")
    if not isinstance(data["rubric_version"], str) or data["rubric_version"] not in manifest["rubrics"]:
        raise ValidationError("unknown rubric_version")
    rubric_task = manifest["rubrics"][data["rubric_version"]]["task_type"]
    if rubric_task not in {data["task_type"], data["modality"]}:
        raise ValidationError("rubric_version does not match task_type")
    try:
        datetime.fromisoformat(data["submitted_at"])
    except (TypeError, ValueError) as error:
        raise ValidationError("submitted_at must be ISO 8601") from error
    for field in ("practiced_at", "standard_verified_at"):
        if data[field] is not None:
            try:
                date.fromisoformat(data[field])
            except (TypeError, ValueError) as error:
                raise ValidationError(f"{field} must be an ISO date or null") from error
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", data["source_hash"]):
        raise ValidationError("source_hash must be a SHA-256 digest")
    opportunities = data["opportunities"]
    if not isinstance(opportunities, dict) or any(
        type(value) is not int or value < 0 for value in opportunities.values()
    ):
        raise ValidationError("opportunities must map codes to non-negative integers")
    if not isinstance(data["task_metrics"], dict):
        raise ValidationError("task_metrics must be a mapping")
    if data["timed"] not in {True, False, None}:
        raise ValidationError("timed must be true, false, or null")
    if data["duration_seconds"] is not None and (
        type(data["duration_seconds"]) is not int or data["duration_seconds"] <= 0
    ):
        raise ValidationError("duration_seconds must be a positive integer or null")
    if not isinstance(data["assistance"], dict):
        raise ValidationError("assistance must be a mapping")
    if set(data["assistance"]) != {"spellcheck", "translation", "other"}:
        raise ValidationError("assistance fields are invalid")
    if data["modality"] == "writing":
        score = data.get("task_score", {})
        if type(data.get("word_count")) is not int or data["word_count"] < 0:
            raise ValidationError("writing word_count must be non-negative")
        if score.get("scale") != "0-5" or type(score.get("value")) is not int or not 0 <= score["value"] <= 5:
            raise ValidationError("writing task_score must be an integer on scale 0-5")
    if data["modality"] == "speaking" and data.get("result_type") != "diagnostic_only":
        raise ValidationError("speaking result_type must be diagnostic_only")
    if data["record_type"] in {"revision", "re_evaluation"} and not isinstance(data["parent_attempt_id"], str):
        raise ValidationError("revision or re_evaluation requires parent_attempt_id")
    if data["record_type"] not in {"revision", "re_evaluation"} and data["parent_attempt_id"] is not None:
        raise ValidationError("only revisions or re_evaluations may have parent_attempt_id")
    outcomes = data["revision_outcomes"]
    if data["record_type"] != "revision" and outcomes is not None:
        raise ValidationError("only revisions may have revision_outcomes")
    if data["record_type"] == "revision":
        keys = {"assigned", "resolved", "partly_resolved", "unresolved", "new_errors", "resolution_rate"}
        if not isinstance(outcomes, dict) or set(outcomes) != keys:
            raise ValidationError("revision_outcomes fields are invalid")
        if type(outcomes["assigned"]) is not int or outcomes["assigned"] <= 0:
            raise ValidationError("revision assigned count must be positive")
        for field in {"resolved", "partly_resolved", "unresolved", "new_errors"}:
            if type(outcomes[field]) is not int or outcomes[field] < 0:
                raise ValidationError(f"revision {field} count must be non-negative")
        completed = outcomes["resolved"] + outcomes["partly_resolved"] + outcomes["unresolved"]
        if completed != outcomes["assigned"]:
            raise ValidationError("revision outcome counts do not reconcile")
        expected_rate = outcomes["resolved"] / outcomes["assigned"]
        if type(outcomes["resolution_rate"]) not in {int, float} or not isclose(
            outcomes["resolution_rate"], expected_rate, rel_tol=0.0, abs_tol=1e-9
        ):
            raise ValidationError("revision resolution_rate is inconsistent")


def validate_error_event(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValidationError("error event must be a mapping")
    required = {
        "event_id", "attempt_id", "taxonomy_version", "code", "source_excerpt",
        "audio_timestamp", "suggested_revision", "reason", "level", "severity",
        "task_specific", "opportunity_present", "historical_status",
    }
    missing = required - data.keys()
    if missing:
        raise ValidationError(f"missing event fields: {sorted(missing)}")
    if type(data["taxonomy_version"]) is not int or data["taxonomy_version"] != 1:
        raise ValidationError("unsupported taxonomy_version")
    if data["level"] not in LEVELS:
        raise ValidationError("invalid event level")
    if data["severity"] not in SEVERITIES:
        raise ValidationError("invalid event severity")
    if data["historical_status"] not in STATUSES:
        raise ValidationError("invalid historical_status")
    if data["opportunity_present"] is not True:
        raise ValidationError("an error event requires opportunity_present=true")
    source_excerpt = data["source_excerpt"]
    audio_timestamp = data["audio_timestamp"]
    has_source_excerpt = isinstance(source_excerpt, str) and bool(source_excerpt.strip())
    has_audio_timestamp = isinstance(audio_timestamp, str) and bool(re.fullmatch(
        r"[0-5][0-9]:[0-5][0-9](?:–[0-5][0-9]:[0-5][0-9])?", audio_timestamp
    ))
    if data["level"] in {"must_fix", "should_fix"} and not (
        has_source_excerpt or has_audio_timestamp
    ):
        raise ValidationError("counted event requires traceable evidence")
