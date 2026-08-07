import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.models import MODALITIES, ValidationError
from toefl_tracker.validation import validate_error_event


@dataclass(frozen=True)
class MigrationResult:
    created: tuple[str, ...]
    unchanged: tuple[str, ...]


def canonical_jsonl(events: Iterable[Mapping]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in events
    )


def _attempt_directories(root: Path, modality: str) -> list[Path]:
    base = root / "tracker" / modality / "attempts"
    if not base.exists():
        return []
    return sorted(
        path for path in base.iterdir() if path.is_dir() and not path.name.startswith(".")
    )


def _read_events(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValidationError(f"cannot read canonical event sidecar: {path}") from error
    events: list[dict] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise ValidationError(f"blank event row: {path}:{line_number}")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValidationError(f"invalid event JSON: {path}:{line_number}") from error
        if not isinstance(event, dict):
            raise ValidationError(f"event row is not a mapping: {path}:{line_number}")
        validate_error_event(event)
        events.append(event)
    return events


def load_canonical_events(root: Path, modality: str) -> list[dict]:
    if modality not in MODALITIES:
        raise ValidationError(f"unknown modality: {modality}")
    events: list[dict] = []
    event_ids: set[str] = set()
    for directory in _attempt_directories(root, modality):
        sidecar = directory / "events.jsonl"
        if not sidecar.exists():
            raise ValidationError(f"missing canonical event sidecar: {directory.name}")
        for event in _read_events(sidecar):
            if event["attempt_id"] != directory.name:
                raise ValidationError("canonical event sidecar attempt_id does not match directory")
            if event["event_id"] in event_ids:
                raise ValidationError(f"duplicate event_id: {event['event_id']}")
            event_ids.add(event["event_id"])
            events.append(event)
    return events


def render_aggregate_events(root: Path, modality: str) -> str:
    return canonical_jsonl(load_canonical_events(root, modality))


def write_aggregate_events(root: Path, modality: str) -> Path:
    ledger = root / "tracker" / modality / "error-events.jsonl"
    atomic_write_text(ledger, render_aggregate_events(root, modality))
    return ledger


def _read_legacy_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return _read_events(path)


def migrate_event_sidecars(root: Path, apply: bool) -> MigrationResult:
    created: list[str] = []
    unchanged: list[str] = []
    planned_writes: list[tuple[Path, str]] = []
    for modality in sorted(MODALITIES):
        attempts = _attempt_directories(root, modality)
        by_attempt: dict[str, list[dict]] = defaultdict(list)
        event_ids: set[str] = set()
        for event in _read_legacy_ledger(root / "tracker" / modality / "error-events.jsonl"):
            attempt_id = event["attempt_id"]
            if event["event_id"] in event_ids:
                raise ValidationError(f"duplicate event_id: {event['event_id']}")
            event_ids.add(event["event_id"])
            by_attempt[attempt_id].append(event)
        attempt_ids = {directory.name for directory in attempts}
        for attempt_id in by_attempt:
            if attempt_id not in attempt_ids:
                raise ValidationError(f"orphan event for attempt_id: {attempt_id}")
        for directory in attempts:
            attempt = read_yaml(directory / "attempt.yaml")
            if attempt.get("attempt_id") != directory.name:
                raise ValidationError("attempt directory does not match attempt_id")
            expected = canonical_jsonl(by_attempt[directory.name])
            sidecar = directory / "events.jsonl"
            if sidecar.exists():
                actual = sidecar.read_text(encoding="utf-8")
                if actual != expected:
                    raise ValidationError(
                        f"conflicting canonical event sidecar: {directory.name}"
                    )
                unchanged.append(directory.name)
                continue
            created.append(directory.name)
            planned_writes.append((sidecar, expected))
    if apply:
        for sidecar, expected in planned_writes:
            atomic_write_text(sidecar, expected)
    return MigrationResult(tuple(created), tuple(unchanged))
