import json
from pathlib import Path

import yaml

from toefl_tracker.io import atomic_write_text, canonical_source_hash, read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.validation import validate_attempt, validate_error_event


def _attempt_directories(root: Path, modality: str) -> list[Path]:
    base = root / "tracker" / modality / "attempts"
    return sorted(path for path in base.glob("*") if path.is_dir()) if base.exists() else []


def _response_filename(modality: str, record_type: str) -> str:
    if modality == "writing":
        return "response-revision.md" if record_type == "revision" else "response-original.md"
    return "transcript-revision.md" if record_type == "revision" else "transcript-original.md"


def register_attempt(
    root: Path,
    manifest: dict,
    attempt: dict,
    prompt: str,
    response: str,
    feedback: str,
    events: list[dict],
) -> Path:
    expected_hash = canonical_source_hash(prompt, response)
    if attempt["source_hash"] != expected_hash:
        raise ValidationError("source_hash does not match prompt and response")
    validate_attempt(attempt, manifest)
    for event in events:
        validate_error_event(event)
        if event["attempt_id"] != attempt["attempt_id"]:
            raise ValidationError("event attempt_id does not match attempt")
    for directory in _attempt_directories(root, attempt["modality"]):
        existing = read_yaml(directory / "attempt.yaml")
        if existing["attempt_id"] == attempt["attempt_id"]:
            raise ValidationError("attempt_id already exists")
        if existing["source_hash"] == attempt["source_hash"]:
            raise ValidationError(f"duplicate source_hash: {existing['attempt_id']}")
    if attempt["record_type"] == "revision":
        parent = (
            root
            / "tracker"
            / attempt["modality"]
            / "attempts"
            / attempt["parent_attempt_id"]
        )
        if not (parent / "attempt.yaml").exists():
            raise ValidationError("revision parent does not exist")
    destination = root / "tracker" / attempt["modality"] / "attempts" / attempt["attempt_id"]
    destination.mkdir(parents=True, exist_ok=False)
    atomic_write_text(
        destination / "attempt.yaml", yaml.safe_dump(attempt, allow_unicode=True, sort_keys=False)
    )
    atomic_write_text(destination / "prompt.md", prompt.rstrip() + "\n")
    response_name = _response_filename(attempt["modality"], attempt["record_type"])
    atomic_write_text(destination / response_name, response.rstrip() + "\n")
    atomic_write_text(destination / "feedback-round-1.md", feedback.rstrip() + "\n")
    ledger = root / "tracker" / attempt["modality"] / "error-events.jsonl"
    previous = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
    appended = "".join(
        json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events
    )
    atomic_write_text(ledger, previous + appended)
    return destination
