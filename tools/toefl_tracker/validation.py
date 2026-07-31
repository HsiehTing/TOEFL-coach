import re
from datetime import date, datetime

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
    missing = REQUIRED_ATTEMPT_FIELDS - data.keys()
    if missing:
        raise ValidationError(f"missing attempt fields: {sorted(missing)}")
    if data["schema_version"] != 1:
        raise ValidationError("unsupported attempt schema_version")
    if data["modality"] not in MODALITIES:
        raise ValidationError("invalid modality")
    if data["task_type"] not in TASK_TYPES[data["modality"]]:
        raise ValidationError("task_type does not match modality")
    if data["record_type"] not in RECORD_TYPES:
        raise ValidationError("invalid record_type")
    if data["rubric_version"] not in manifest["rubrics"]:
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
        not isinstance(value, int) or value < 0 for value in opportunities.values()
    ):
        raise ValidationError("opportunities must map codes to non-negative integers")
    if not isinstance(data["task_metrics"], dict):
        raise ValidationError("task_metrics must be a mapping")
    if data["timed"] not in {True, False, None}:
        raise ValidationError("timed must be true, false, or null")
    if data["duration_seconds"] is not None and (
        not isinstance(data["duration_seconds"], int) or data["duration_seconds"] <= 0
    ):
        raise ValidationError("duration_seconds must be a positive integer or null")
    if not isinstance(data["assistance"], dict):
        raise ValidationError("assistance must be a mapping")
    if set(data["assistance"]) != {"spellcheck", "translation", "other"}:
        raise ValidationError("assistance fields are invalid")
    if data["modality"] == "writing":
        score = data.get("task_score", {})
        if data.get("word_count", -1) < 0:
            raise ValidationError("writing word_count must be non-negative")
        if score.get("scale") != "0-5" or not isinstance(score.get("value"), int) or not 0 <= score["value"] <= 5:
            raise ValidationError("writing task_score must be an integer on scale 0-5")
    if data["modality"] == "speaking" and data.get("result_type") != "diagnostic_only":
        raise ValidationError("speaking result_type must be diagnostic_only")
    if data["record_type"] == "revision" and not data["parent_attempt_id"]:
        raise ValidationError("revision requires parent_attempt_id")
    if data["record_type"] != "revision" and data["parent_attempt_id"] is not None:
        raise ValidationError("only revisions may have parent_attempt_id")
    outcomes = data["revision_outcomes"]
    if data["record_type"] != "revision" and outcomes is not None:
        raise ValidationError("only revisions may have revision_outcomes")
    if data["record_type"] == "revision":
        keys = {"assigned", "resolved", "partly_resolved", "unresolved", "new_errors", "resolution_rate"}
        if not isinstance(outcomes, dict) or set(outcomes) != keys:
            raise ValidationError("revision_outcomes fields are invalid")
        if outcomes["assigned"] <= 0:
            raise ValidationError("revision assigned count must be positive")
        completed = outcomes["resolved"] + outcomes["partly_resolved"] + outcomes["unresolved"]
        if completed != outcomes["assigned"]:
            raise ValidationError("revision outcome counts do not reconcile")
        expected_rate = outcomes["resolved"] / outcomes["assigned"]
        if abs(outcomes["resolution_rate"] - expected_rate) > 1e-9:
            raise ValidationError("revision resolution_rate is inconsistent")


def validate_error_event(data: dict) -> None:
    required = {
        "event_id", "attempt_id", "taxonomy_version", "code", "source_excerpt",
        "audio_timestamp", "suggested_revision", "reason", "level", "severity",
        "task_specific", "opportunity_present", "historical_status",
    }
    missing = required - data.keys()
    if missing:
        raise ValidationError(f"missing event fields: {sorted(missing)}")
    if data["level"] not in LEVELS:
        raise ValidationError("invalid event level")
    if data["severity"] not in SEVERITIES:
        raise ValidationError("invalid event severity")
    if data["historical_status"] not in STATUSES:
        raise ValidationError("invalid historical_status")
    if data["opportunity_present"] is not True:
        raise ValidationError("an error event requires opportunity_present=true")
    if data["level"] in {"must_fix", "should_fix"} and not (
        str(data["source_excerpt"]).strip() or data["audio_timestamp"]
    ):
        raise ValidationError("counted event requires traceable evidence")
