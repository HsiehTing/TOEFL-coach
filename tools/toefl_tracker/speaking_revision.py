"""Preflight and immutable registration for transcript-supported re-recordings."""

import json
from pathlib import Path

import yaml

from toefl_tracker.canonical import write_aggregate_events
from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.models import ValidatedPracticeRegistration
from toefl_tracker.register import _registration_lock, publish_registration
from toefl_tracker.reports import rebuild_modality
from toefl_tracker.speaking_progress import write_speaking_progress_overview
from toefl_tracker.taxonomy import load_taxonomy


_AUDIO_CODES = {
    "SPK-PRONUNCIATION", "SPK-STRESS", "SPK-RHYTHM", "SPK-INTONATION",
    "SPK-FLUENCY", "SPK-INTELLIGIBILITY",
}
_ITEM_LIMITS = {"listen_and_repeat": 7, "take_an_interview": 4}
_STATUSES = {"meets_target", "partially_meets_target", "needs_revision"}
_FIELDS = {"parent_attempt_id", "scope", "target_codes", "source_event_ids", "items", "outcomes"}


def validate_transcript_rerecording(root: Path, task_type: str, revision: object) -> None:
    """Reject incomplete lineage and claims a transcript cannot safely support."""
    if task_type not in _ITEM_LIMITS or not isinstance(revision, dict) or set(revision) != _FIELDS:
        raise ValidationError("speaking re-recording fields are invalid")
    if not isinstance(revision["parent_attempt_id"], str) or not revision["parent_attempt_id"].strip():
        raise ValidationError("speaking re-recording parent is invalid")
    if revision["scope"] not in {"partial", "complete"}:
        raise ValidationError("speaking re-recording scope is invalid")
    codes = revision["target_codes"]
    taxonomy = load_taxonomy(root)
    if not isinstance(codes, list) or not codes or len(set(codes)) != len(codes):
        raise ValidationError("speaking re-recording target codes are invalid")
    for code in codes:
        entry = taxonomy.get(code)
        if (
            not isinstance(code, str) or entry is None or entry.modality != "speaking"
            or task_type not in entry.task_types or code in _AUDIO_CODES
        ):
            raise ValidationError("speaking re-recording target code is unsupported")
    source_event_ids = revision["source_event_ids"]
    if not isinstance(source_event_ids, list) or not source_event_ids or any(
        not isinstance(value, str) or not value.strip() for value in source_event_ids
    ) or len(set(source_event_ids)) != len(source_event_ids):
        raise ValidationError("speaking re-recording source events are invalid")
    items = revision["items"]
    if not isinstance(items, list) or not items:
        raise ValidationError("speaking re-recording items are invalid")
    seen_items = set()
    transcripts: dict[int, str] = {}
    for item in items:
        if (
            not isinstance(item, dict) or set(item) != {"item_id", "prompt_excerpt", "learner_transcript"}
            or type(item.get("item_id")) is not int or not 1 <= item["item_id"] <= _ITEM_LIMITS[task_type]
            or item["item_id"] in seen_items
            or not isinstance(item.get("prompt_excerpt"), str) or not item["prompt_excerpt"].strip()
            or not isinstance(item.get("learner_transcript"), str) or not item["learner_transcript"].strip()
        ):
            raise ValidationError("speaking re-recording item is invalid")
        seen_items.add(item["item_id"])
        transcripts[item["item_id"]] = item["learner_transcript"]
    expected = set(range(1, _ITEM_LIMITS[task_type] + 1))
    if revision["scope"] == "complete" and seen_items != expected:
        raise ValidationError("complete speaking re-recording must include every item")
    if revision["scope"] == "partial" and seen_items == expected:
        raise ValidationError("partial speaking re-recording must name a subset of items")
    outcomes = revision["outcomes"]
    if not isinstance(outcomes, list) or len(outcomes) != len(codes):
        raise ValidationError("speaking re-recording requires an outcome for every target code")
    seen_codes = set()
    for outcome in outcomes:
        if (
            not isinstance(outcome, dict)
            or set(outcome) != {"code", "item_ids", "status", "reason", "evidence_excerpt"}
            or outcome.get("code") not in codes or outcome["code"] in seen_codes
            or not isinstance(outcome.get("item_ids"), list) or not outcome["item_ids"]
            or any(type(item_id) is not int or item_id not in seen_items for item_id in outcome["item_ids"])
            or len(set(outcome["item_ids"])) != len(outcome["item_ids"])
            or outcome.get("status") not in _STATUSES
            or not isinstance(outcome.get("reason"), str) or not outcome["reason"].strip()
            or not isinstance(outcome.get("evidence_excerpt"), str) or not outcome["evidence_excerpt"].strip()
            or not any(outcome["evidence_excerpt"] in transcripts[item_id] for item_id in outcome["item_ids"])
        ):
            raise ValidationError("speaking re-recording outcome is invalid or lacks transcript evidence")
        seen_codes.add(outcome["code"])


def _render_rerecording_prompt(revision: dict) -> str:
    return "\n\n".join(
        f"## Item {item['item_id']}\n{item['prompt_excerpt']}"
        for item in revision["items"]
    )


def _render_rerecording_transcript(revision: dict) -> str:
    return "\n\n".join(
        f"## Item {item['item_id']}\n{item['learner_transcript']}"
        for item in revision["items"]
    )


def register_transcript_rerecording(
    root: Path, manifest: dict, attempt: dict, revision: object, feedback: str,
) -> Path:
    """Persist a transcript re-recording without treating it as a formal session."""
    if (
        not isinstance(attempt, dict)
        or attempt.get("modality") != "speaking"
        or attempt.get("record_type") != "revision"
    ):
        raise ValidationError("speaking re-recording registration requires a speaking revision")
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValidationError("speaking re-recording feedback is missing")
    validate_transcript_rerecording(root, attempt.get("task_type", ""), revision)
    assert isinstance(revision, dict)
    parent_path = root / "tracker/speaking/attempts" / revision["parent_attempt_id"] / "attempt.yaml"
    if not parent_path.exists():
        raise ValidationError("speaking re-recording parent session does not exist")
    parent = read_yaml(parent_path)
    if (
        parent.get("record_type") != "formal_original"
        or parent.get("modality") != "speaking"
        or parent.get("task_type") != attempt.get("task_type")
    ):
        raise ValidationError("speaking re-recording parent must be a matching formal session")
    events_path = parent_path.parent / "events.jsonl"
    try:
        parent_events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError("speaking re-recording parent events are unavailable") from error
    selected = [event for event in parent_events if event.get("event_id") in revision["source_event_ids"]]
    if len(selected) != len(revision["source_event_ids"]) or not all(
        any(event.get("code") == code for event in selected) for code in revision["target_codes"]
    ):
        raise ValidationError("speaking re-recording source events do not cover target codes")
    prompt = _render_rerecording_prompt(revision)
    transcript = _render_rerecording_transcript(revision)
    prepared = dict(attempt)
    prepared["speaking_revision"] = revision
    prepared["revision_outcomes"] = None
    prepared["source_hash"] = canonical_source_hash(prompt, transcript)
    metrics = dict(prepared.get("task_metrics", {}))
    metrics["rerecorded_item_count"] = len(revision["items"])
    prepared["task_metrics"] = metrics
    destination = publish_registration(
        root,
        manifest,
        ValidatedPracticeRegistration(
            attempt=prepared,
            prompt=prompt,
            response=transcript,
            feedback=feedback,
            events=(),
            extra_files={
                "re-recording.yaml": yaml.safe_dump(revision, allow_unicode=True, sort_keys=False),
            },
        ),
    )
    with _registration_lock(root):
        write_aggregate_events(root, "speaking")
        rebuild_modality(root, "speaking")
        write_speaking_progress_overview(root)
    return destination
