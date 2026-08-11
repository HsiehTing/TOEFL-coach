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


def validate_reevaluation_metadata(data: dict) -> None:
    """Validate fields unique to a newly registered schema-v2 re-evaluation."""
    if data.get("record_type") != "re_evaluation":
        raise ValidationError("schema_version 2 requires record_type re_evaluation")
    if data.get("schema_version") != 2:
        raise ValidationError("re-evaluation requires schema_version 2")
    try:
        datetime.fromisoformat(data["evaluated_at"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError("evaluated_at must be ISO 8601") from error
    supersedes = data.get("supersedes_evaluation_id")
    if not isinstance(supersedes, str) or not supersedes.strip():
        raise ValidationError("supersedes_evaluation_id must be a non-empty string")


def validate_attempt(data: dict, manifest: dict) -> None:
    if not isinstance(data, dict):
        raise ValidationError("attempt must be a mapping")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("rubrics"), dict):
        raise ValidationError("manifest rubrics must be a mapping")
    missing = REQUIRED_ATTEMPT_FIELDS - data.keys()
    if missing:
        raise ValidationError(f"missing attempt fields: {sorted(missing)}")
    if type(data["schema_version"]) is not int or data["schema_version"] not in {1, 2}:
        raise ValidationError("unsupported attempt schema_version")
    if not isinstance(data["modality"], str) or data["modality"] not in MODALITIES:
        raise ValidationError("invalid modality")
    if not isinstance(data["task_type"], str) or data["task_type"] not in TASK_TYPES[data["modality"]]:
        raise ValidationError("task_type does not match modality")
    if not isinstance(data["record_type"], str) or data["record_type"] not in RECORD_TYPES:
        raise ValidationError("invalid record_type")
    if data["schema_version"] == 2:
        validate_reevaluation_metadata(data)
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
        if type(data.get("word_count")) is not int or data["word_count"] < 0:
            raise ValidationError("writing word_count must be non-negative")
        if data["record_type"] == "targeted_drill":
            drill = data.get("drill")
            if not isinstance(drill, dict):
                raise ValidationError("targeted_drill requires drill metadata")
            required_drill = {"set_id", "target_codes", "item_count", "correct_count", "source_attempt_ids"}
            optional_drill = {
                "drill_pack_id", "recommendation_id", "item_results",
                "minimum_accuracy", "source_prompt_hash", "pack_version", "artifact_retention",
                "code_results",
            }
            if not required_drill <= set(drill) <= required_drill | optional_drill:
                raise ValidationError("targeted_drill metadata fields are invalid")
            if ("drill_pack_id" in drill) != ("recommendation_id" in drill):
                raise ValidationError("targeted_drill drill_pack_id and recommendation_id must appear together")
            if "drill_pack_id" in drill and (
                not isinstance(drill["drill_pack_id"], str) or not drill["drill_pack_id"].startswith("WD-")
                or not isinstance(drill["recommendation_id"], str) or not drill["recommendation_id"].strip()
            ):
                raise ValidationError("targeted_drill generated-pack metadata is invalid")
            inline_lineage = {
                "minimum_accuracy", "source_prompt_hash", "pack_version", "artifact_retention",
            }
            if set(drill) & inline_lineage and not inline_lineage <= set(drill):
                raise ValidationError("targeted_drill inline transfer lineage is incomplete")
            if inline_lineage <= set(drill) and "drill_pack_id" not in drill:
                raise ValidationError("targeted_drill inline transfer lineage requires a generated pack ID")
            if inline_lineage <= set(drill) and "code_results" not in drill:
                raise ValidationError("targeted_drill result-only drill requires per-code results")
            if inline_lineage <= set(drill) and (
                type(drill["minimum_accuracy"]) not in {int, float}
                or not 0 < drill["minimum_accuracy"] <= 1
                or not isinstance(drill["source_prompt_hash"], str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", drill["source_prompt_hash"])
                or type(drill["pack_version"]) is not int
                or drill["pack_version"] < 5
                or drill["artifact_retention"] != "result_only"
            ):
                raise ValidationError("targeted_drill inline transfer lineage is invalid")
            if not isinstance(drill["set_id"], str) or not drill["set_id"].strip():
                raise ValidationError("targeted_drill set_id must be non-empty")
            codes = drill["target_codes"]
            if not isinstance(codes, list) or not codes or any(
                not isinstance(code, str) or not code.strip() for code in codes
            ) or len(set(codes)) != len(codes):
                raise ValidationError("targeted_drill target_codes must be unique strings")
            if type(drill["item_count"]) is not int or drill["item_count"] <= 0:
                raise ValidationError("targeted_drill item_count must be positive")
            if type(drill["correct_count"]) is not int or not 0 <= drill["correct_count"] <= drill["item_count"]:
                raise ValidationError("targeted_drill correct_count must be within item_count")
            item_results = drill.get("item_results")
            if item_results is not None:
                if not isinstance(item_results, list) or len(item_results) != drill["item_count"]:
                    raise ValidationError("targeted_drill item_results must cover every item")
                seen_item_ids = set()
                meets_target = 0
                for item in item_results:
                    if not isinstance(item, dict) or set(item) != {"item_id", "status", "reason"}:
                        raise ValidationError("targeted_drill item result fields are invalid")
                    item_id = item["item_id"]
                    status = item["status"]
                    reason = item["reason"]
                    if not isinstance(item_id, str) or not item_id.strip() or item_id in seen_item_ids:
                        raise ValidationError("targeted_drill item result IDs must be unique strings")
                    if status not in {"meets_target", "partially_meets_target", "needs_revision"}:
                        raise ValidationError("targeted_drill item result status is invalid")
                    if not isinstance(reason, str) or not reason.strip():
                        raise ValidationError("targeted_drill item result reason must be a non-empty string")
                    seen_item_ids.add(item_id)
                    meets_target += status == "meets_target"
                if drill["correct_count"] != meets_target:
                    raise ValidationError("targeted_drill correct_count must match meets_target item results")
            code_results = drill.get("code_results")
            if code_results is not None:
                if not isinstance(code_results, list) or len(code_results) != len(codes):
                    raise ValidationError("targeted_drill code_results must cover every target code")
                seen_codes = set()
                total_items = total_correct = total_partial = 0
                for result in code_results:
                    if not isinstance(result, dict) or set(result) != {
                        "code", "item_count", "correct_count", "partial_count"
                    }:
                        raise ValidationError("targeted_drill code result fields are invalid")
                    code = result["code"]
                    item_count = result["item_count"]
                    correct_count = result["correct_count"]
                    partial_count = result["partial_count"]
                    if (
                        not isinstance(code, str)
                        or code not in codes
                        or code in seen_codes
                        or type(item_count) is not int
                        or item_count <= 0
                        or type(correct_count) is not int
                        or type(partial_count) is not int
                        or correct_count < 0
                        or partial_count < 0
                        or correct_count + partial_count > item_count
                    ):
                        raise ValidationError("targeted_drill code result is invalid")
                    seen_codes.add(code)
                    total_items += item_count
                    total_correct += correct_count
                    total_partial += partial_count
                if total_items != drill["item_count"] or total_correct != drill["correct_count"]:
                    raise ValidationError("targeted_drill code results do not reconcile")
                if item_results is not None and total_partial != sum(
                    item["status"] == "partially_meets_target" for item in item_results
                ):
                    raise ValidationError("targeted_drill code partial results do not reconcile")
            source_attempt_ids = drill["source_attempt_ids"]
            if not isinstance(source_attempt_ids, list) or any(
                not isinstance(value, str) or not value.strip() for value in source_attempt_ids
            ):
                raise ValidationError("targeted_drill source_attempt_ids must be strings")
        else:
            score = data.get("task_score", {})
            if score.get("scale") != "0-5" or type(score.get("value")) is not int or not 0 <= score["value"] <= 5:
                raise ValidationError("writing task_score must be an integer on scale 0-5")
            if data.get("drill") is not None:
                raise ValidationError("drill metadata is only valid for targeted_drill")
        transfer = data.get("transfer")
        if transfer is not None:
            required_transfer = {"drill_attempt_id", "drill_pack_id", "source_attempt_id", "target_codes", "opportunity_confirmation", "source_prompt_hash", "transfer_prompt_hash"}
            if data["record_type"] != "formal_original" or not isinstance(transfer, dict) or set(transfer) != required_transfer:
                raise ValidationError("transfer metadata is invalid")
            if not all(isinstance(transfer[field], str) and transfer[field].strip() for field in {"drill_attempt_id", "drill_pack_id", "source_attempt_id", "source_prompt_hash", "transfer_prompt_hash"}):
                raise ValidationError("transfer metadata IDs are invalid")
            if not transfer["drill_pack_id"].startswith("WD-") or not all(value.startswith("sha256:") for value in (transfer["source_prompt_hash"], transfer["transfer_prompt_hash"])):
                raise ValidationError("transfer metadata hashes are invalid")
            if not isinstance(transfer["target_codes"], list) or not transfer["target_codes"] or len(set(transfer["target_codes"])) != len(transfer["target_codes"]):
                raise ValidationError("transfer target_codes are invalid")
            if transfer["opportunity_confirmation"] != opportunities:
                raise ValidationError("transfer opportunity confirmation must match opportunities")
    if data["modality"] == "speaking":
        if data.get("result_type") != "diagnostic_only":
            raise ValidationError("speaking result_type must be diagnostic_only")
        if data["record_type"] == "targeted_drill":
            drill = data.get("drill")
            if not isinstance(drill, dict) or drill.get("artifact_retention") != "result_only":
                raise ValidationError("speaking targeted_drill requires result-only metadata")
        elif data.get("drill") is not None:
            raise ValidationError("drill metadata is only valid for targeted_drill")
        transfer = data.get("transfer")
        if transfer is not None:
            required_transfer = {
                "drill_attempt_id", "source_attempt_id", "target_codes",
                "opportunity_confirmation", "source_prompt_hash", "transfer_prompt_hash", "outcomes",
            }
            if (
                data["record_type"] != "formal_original"
                or not isinstance(transfer, dict)
                or set(transfer) != required_transfer
            ):
                raise ValidationError("speaking transfer metadata is invalid")
            if not all(
                isinstance(transfer[field], str) and transfer[field].strip()
                for field in {"drill_attempt_id", "source_attempt_id", "source_prompt_hash", "transfer_prompt_hash"}
            ) or not all(
                transfer[field].startswith("sha256:")
                for field in {"source_prompt_hash", "transfer_prompt_hash"}
            ):
                raise ValidationError("speaking transfer metadata IDs are invalid")
            targets = transfer["target_codes"]
            if (
                not isinstance(targets, list) or not targets or len(set(targets)) != len(targets)
                or any(not isinstance(code, str) or not code.strip() for code in targets)
                or transfer["opportunity_confirmation"] != opportunities
            ):
                raise ValidationError("speaking transfer target metadata is invalid")
            outcomes = transfer["outcomes"]
            if not isinstance(outcomes, list) or len(outcomes) != len(targets):
                raise ValidationError("speaking transfer outcomes are invalid")
            seen_codes = set()
            for outcome in outcomes:
                if (
                    not isinstance(outcome, dict)
                    or set(outcome) != {"code", "status", "reason", "evidence_excerpt"}
                    or outcome.get("code") not in targets
                    or outcome["code"] in seen_codes
                    or outcome.get("status") not in {"meets_target", "partially_meets_target", "needs_revision"}
                    or not isinstance(outcome.get("reason"), str) or not outcome["reason"].strip()
                    or not isinstance(outcome.get("evidence_excerpt"), str) or not outcome["evidence_excerpt"].strip()
                ):
                    raise ValidationError("speaking transfer outcome metadata is invalid")
                seen_codes.add(outcome["code"])
    if data["record_type"] in {"revision", "re_evaluation"} and not isinstance(data["parent_attempt_id"], str):
        raise ValidationError("revision or re_evaluation requires parent_attempt_id")
    if data["record_type"] not in {"revision", "re_evaluation"} and data["parent_attempt_id"] is not None:
        raise ValidationError("only revisions or re_evaluations may have parent_attempt_id")
    outcomes = data["revision_outcomes"]
    if data["modality"] == "speaking" and data["record_type"] == "revision":
        revision = data.get("speaking_revision")
        if not isinstance(revision, dict):
            raise ValidationError("speaking revision requires re-recording metadata")
        if outcomes is not None:
            raise ValidationError("speaking revision does not use writing revision_outcomes")
        return
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
    for field in ("event_id", "attempt_id", "code", "suggested_revision", "reason"):
        if not isinstance(data[field], str) or not data[field].strip():
            raise ValidationError(f"{field} must be a non-empty string")
    if type(data["taxonomy_version"]) is not int or data["taxonomy_version"] != 1:
        raise ValidationError("unsupported taxonomy_version")
    if not isinstance(data["level"], str) or data["level"] not in LEVELS:
        raise ValidationError("invalid event level")
    if not isinstance(data["severity"], str) or data["severity"] not in SEVERITIES:
        raise ValidationError("invalid event severity")
    if data["historical_status"] is None:
        if data.get("code") != "UNCLASSIFIED":
            raise ValidationError("invalid historical_status")
    elif (
        not isinstance(data["historical_status"], str)
        or data["historical_status"] not in STATUSES
    ):
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
