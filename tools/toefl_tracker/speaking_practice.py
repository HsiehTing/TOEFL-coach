"""Result-only, transcript-supported Speaking drill registration."""

import json
from hashlib import sha256
from pathlib import Path

from toefl_tracker.canonical import write_aggregate_events
from toefl_tracker.io import read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.register import _registration_lock, publish_registration
from toefl_tracker.reports import rebuild_modality
from toefl_tracker.speaking_progress import write_speaking_progress_overview
from toefl_tracker.taxonomy import load_taxonomy
from toefl_tracker.models import ValidatedPracticeRegistration


_AUDIO_CODES = {
    "SPK-PRONUNCIATION", "SPK-STRESS", "SPK-RHYTHM", "SPK-INTONATION",
    "SPK-FLUENCY", "SPK-INTELLIGIBILITY",
}
_STATUSES = {"meets_target", "partially_meets_target", "needs_revision"}
_INPUT_FIELDS = {"source_attempt_id", "target_codes", "item_results", "minimum_accuracy"}
_PERSISTED_FIELDS = _INPUT_FIELDS | {
    "item_count", "correct_count", "code_results", "artifact_retention", "result_hash",
}


def validate_transcript_drill(root: Path, task_type: str, drill: object) -> None:
    """Fail closed until a speaking audio-performance contract is implemented."""
    if not isinstance(drill, dict) or set(drill) != _INPUT_FIELDS:
        raise ValidationError("speaking transcript drill fields are invalid")
    codes = drill["target_codes"]
    if not isinstance(codes, list) or not codes or len(set(codes)) != len(codes):
        raise ValidationError("speaking transcript drill target_codes are invalid")
    taxonomy = load_taxonomy(root)
    for code in codes:
        entry = taxonomy.get(code)
        if (
            not isinstance(code, str) or entry is None or entry.modality != "speaking"
            or task_type not in entry.task_types or code in _AUDIO_CODES
        ):
            raise ValidationError("speaking transcript drill target code is unsupported")
    if type(drill["minimum_accuracy"]) not in {int, float} or not 0 < drill["minimum_accuracy"] <= 1:
        raise ValidationError("speaking transcript drill accuracy is invalid")
    items = drill["item_results"]
    if not isinstance(items, list) or not items:
        raise ValidationError("speaking transcript drill requires item results")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"item_id", "code", "status", "reason"}:
            raise ValidationError("speaking transcript drill item fields are invalid")
        if (
            not isinstance(item["item_id"], str) or not item["item_id"].strip()
            or item["item_id"] in seen or item["code"] not in codes
            or item["status"] not in _STATUSES
            or not isinstance(item["reason"], str) or not item["reason"].strip()
        ):
            raise ValidationError("speaking transcript drill item is invalid")
        seen.add(item["item_id"])
    if not all(any(item["code"] == code for item in items) for code in codes):
        raise ValidationError("speaking transcript drill must assess every target code")


def finalize_transcript_drill(root: Path, task_type: str, drill: object) -> dict:
    """Derive the minimal immutable result lineage from a reviewed drill."""
    validate_transcript_drill(root, task_type, drill)
    assert isinstance(drill, dict)
    items = drill["item_results"]
    code_results = []
    for code in drill["target_codes"]:
        code_items = [item for item in items if item["code"] == code]
        code_results.append({
            "code": code,
            "item_count": len(code_items),
            "correct_count": sum(item["status"] == "meets_target" for item in code_items),
            "partial_count": sum(item["status"] == "partially_meets_target" for item in code_items),
        })
    result = {
        **drill,
        "item_count": len(items),
        "correct_count": sum(item["status"] == "meets_target" for item in items),
        "code_results": code_results,
        "artifact_retention": "result_only",
    }
    digest = sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**result, "result_hash": f"sha256:{digest}"}


def validate_persisted_transcript_drill(root: Path, task_type: str, drill: object) -> None:
    """Ensure retained results still exactly match the approved drill contract."""
    if not isinstance(drill, dict) or set(drill) != _PERSISTED_FIELDS:
        raise ValidationError("persisted speaking transcript drill fields are invalid")
    raw = {field: drill[field] for field in _INPUT_FIELDS}
    expected = finalize_transcript_drill(root, task_type, raw)
    if drill != expected:
        raise ValidationError("persisted speaking transcript drill results do not reconcile")


def register_transcript_drill(
    root: Path, manifest: dict, attempt: dict, drill: object, feedback: str,
) -> Path:
    """Publish an immutable speaking drill record without prompt or transcript files."""
    if not isinstance(attempt, dict) or attempt.get("modality") != "speaking":
        raise ValidationError("speaking drill registration requires a speaking attempt")
    if attempt.get("record_type") != "targeted_drill":
        raise ValidationError("speaking drill registration requires targeted_drill")
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValidationError("speaking drill feedback is missing")
    finalized = finalize_transcript_drill(root, attempt.get("task_type", ""), drill)
    source_path = root / "tracker/speaking/attempts" / finalized["source_attempt_id"] / "attempt.yaml"
    if not source_path.exists():
        raise ValidationError("speaking drill source attempt does not exist")
    source = read_yaml(source_path)
    if (
        source.get("record_type") != "formal_original"
        or source.get("modality") != "speaking"
        or source.get("task_type") != attempt.get("task_type")
    ):
        raise ValidationError("speaking drill source attempt must be a matching formal session")
    prepared = dict(attempt)
    prepared["drill"] = finalized
    prepared["source_hash"] = finalized["result_hash"]
    metrics = dict(prepared.get("task_metrics", {}))
    metrics.update({"drill_item_count": finalized["item_count"]})
    prepared["task_metrics"] = metrics
    registration = ValidatedPracticeRegistration(
        attempt=prepared,
        prompt="",
        response="",
        feedback=feedback,
        events=(),
        result_only=True,
    )
    destination = publish_registration(root, manifest, registration)
    with _registration_lock(root):
        write_aggregate_events(root, "speaking")
        rebuild_modality(root, "speaking")
        write_speaking_progress_overview(root)
    return destination
