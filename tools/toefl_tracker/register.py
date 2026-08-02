import json
import os
import shutil
import tempfile
import time
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Callable, Iterator

import yaml

from toefl_tracker.canonical import (
    canonical_jsonl,
    load_canonical_events,
    write_aggregate_events,
)
from toefl_tracker.io import atomic_write_text, canonical_source_hash, fsync_directory, read_yaml
from toefl_tracker.models import (
    ValidatedPracticeRegistration,
    ValidatedReevaluationRegistration,
    ValidationError,
)
from toefl_tracker.event_validation import validate_event_context
from toefl_tracker.validation import (
    validate_attempt,
    validate_error_event,
    validate_reevaluation_metadata,
)

if os.name == "nt":
    import msvcrt
else:
    import fcntl


_LEGACY_LOCK_STALE_SECONDS = 300
_STAGING_PREFIX = ".register-"


def _attempt_directories(root: Path, modality: str) -> list[Path]:
    base = root / "tracker" / modality / "attempts"
    return (
        sorted(
            path
            for path in base.glob("*")
            if path.is_dir() and not path.name.startswith(".")
        )
        if base.exists()
        else []
    )


def _response_filename(modality: str, record_type: str) -> str:
    if modality == "writing":
        return "response-revision.md" if record_type == "revision" else "response-original.md"
    return "transcript-revision.md" if record_type == "revision" else "transcript-original.md"


def _process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _reclaim_legacy_directory_lock(lock: Path) -> None:
    if not lock.is_dir():
        return
    owner_is_dead = False
    try:
        owner = json.loads((lock / "owner.json").read_text(encoding="utf-8"))
        pid = owner.get("pid")
        owner_is_dead = type(pid) is int and pid > 0 and not _process_is_alive(pid)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    try:
        old_enough = time.time() - lock.stat().st_mtime >= _LEGACY_LOCK_STALE_SECONDS
    except FileNotFoundError:
        return
    if not (owner_is_dead or old_enough):
        raise TimeoutError(f"active legacy registration lock: {lock}")
    try:
        shutil.rmtree(lock)
    except (FileNotFoundError, NotADirectoryError):
        pass


def _acquire_file_lock(handle: BinaryIO) -> None:
    if os.name == "nt":
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.01)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _release_file_lock(handle: BinaryIO) -> None:
    if os.name == "nt":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _registration_lock(root: Path) -> Iterator[None]:
    lock = root / "tracker" / ".register.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    _reclaim_legacy_directory_lock(lock)
    with lock.open("a+b") as handle:
        _acquire_file_lock(handle)
        try:
            yield
        finally:
            _release_file_lock(handle)


def _cleanup_abandoned_staging(attempts: Path) -> None:
    if not attempts.exists():
        return
    removed_staging = False
    for path in attempts.iterdir():
        if path.is_dir() and path.name.startswith(_STAGING_PREFIX):
            shutil.rmtree(path)
            removed_staging = True
    if removed_staging:
        fsync_directory(attempts)


def recover_registration_state(root: Path, modality: str = "writing") -> None:
    with _registration_lock(root):
        _cleanup_abandoned_staging(root / "tracker" / modality / "attempts")


def _validate_extra_files(extra_files: Mapping[str, str]) -> None:
    if not isinstance(extra_files, Mapping) or any(
        not isinstance(name, str)
        or Path(name).name != name
        or name in {
            "attempt.yaml",
            "prompt.md",
            "response-original.md",
            "response-revision.md",
            "transcript-original.md",
            "transcript-revision.md",
            "feedback-round-1.md",
            "events.jsonl",
            ".ready",
        }
        or not isinstance(content, str)
        for name, content in extra_files.items()
    ):
        raise ValidationError("extra attempt files are invalid")


def _validate_registration(
    manifest: dict,
    registration: ValidatedPracticeRegistration | ValidatedReevaluationRegistration,
) -> None:
    attempt = registration.attempt
    validate_attempt(attempt, manifest)
    if isinstance(registration, ValidatedPracticeRegistration):
        if attempt["record_type"] == "re_evaluation":
            raise ValidationError("registration bundle does not match record_type")
        _validate_extra_files(registration.extra_files)
        expected_hash = canonical_source_hash(registration.prompt, registration.response)
        if attempt["source_hash"] != expected_hash:
            raise ValidationError("source_hash does not match prompt and response")
        event_ids: set[str] = set()
        for event in registration.events:
            validate_error_event(event)
            if event["attempt_id"] != attempt["attempt_id"]:
                raise ValidationError("event attempt_id does not match attempt")
            if event["event_id"] in event_ids:
                raise ValidationError(f"duplicate event_id: {event['event_id']}")
            event_ids.add(event["event_id"])
        return
    if isinstance(registration, ValidatedReevaluationRegistration):
        if attempt["record_type"] != "re_evaluation":
            raise ValidationError("registration bundle does not match record_type")
        return
    raise TypeError("registration must be a validated registration bundle")


def _normalized_lineage_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be an ISO 8601 timestamp")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(f"{label} must be an ISO 8601 timestamp") from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValidationError(f"{label} must include a UTC offset for lineage")
    return timestamp.astimezone(timezone.utc)


def _reevaluation_order_key(attempt: dict) -> tuple[datetime, str]:
    attempt_id = attempt.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id:
        raise ValidationError("re-evaluation attempt_id must be a non-empty string")
    if attempt.get("record_type") == "formal_original":
        return (
            _normalized_lineage_timestamp(
                attempt.get("submitted_at"), "formal parent submitted_at"
            ),
            attempt_id,
        )
    if attempt.get("schema_version") == 2:
        return (
            _normalized_lineage_timestamp(
                attempt.get("evaluated_at"), "re-evaluation evaluated_at"
            ),
            attempt_id,
        )
    if attempt.get("schema_version") == 1:
        # Schema-1 records predate evaluated_at. submitted_at is the only
        # durable ordering fact, so it is the conservative lineage fallback.
        return (
            _normalized_lineage_timestamp(
                attempt.get("submitted_at"), "legacy re-evaluation submitted_at"
            ),
            attempt_id,
        )
    raise ValidationError("re-evaluation has an unsupported schema_version")


def _validate_existing_attempts(root: Path, attempt: dict, attempts: Path) -> None:
    for directory in _attempt_directories(root, attempt["modality"]):
        existing = read_yaml(directory / "attempt.yaml")
        if existing["attempt_id"] == attempt["attempt_id"]:
            raise ValidationError("attempt_id already exists")
        if (
            attempt["record_type"] != "re_evaluation"
            and existing["source_hash"] == attempt["source_hash"]
        ):
            raise ValidationError(f"duplicate source_hash: {existing['attempt_id']}")
    if attempt["record_type"] in {"revision", "re_evaluation"}:
        parent = attempts / attempt["parent_attempt_id"]
        if not (parent / "attempt.yaml").exists():
            raise ValidationError("revision parent does not exist")
        parent_attempt = read_yaml(parent / "attempt.yaml")
        if (
            parent_attempt.get("record_type") != "formal_original"
            or parent_attempt.get("modality") != attempt["modality"]
            or parent_attempt.get("task_type") != attempt["task_type"]
        ):
            raise ValidationError("revision parent must be matching formal original")
        if attempt["record_type"] == "re_evaluation":
            validate_reevaluation_metadata(attempt)
            if attempt["source_hash"] != parent_attempt["source_hash"]:
                raise ValidationError("re-evaluation source_hash must match formal parent")
            prior_reevaluations: list[dict] = []
            for directory in _attempt_directories(root, attempt["modality"]):
                candidate = read_yaml(directory / "attempt.yaml")
                if (
                    candidate.get("record_type") == "re_evaluation"
                    and candidate.get("parent_attempt_id") == attempt["parent_attempt_id"]
                ):
                    prior_reevaluations.append(candidate)
            if prior_reevaluations:
                predecessor = max(
                    prior_reevaluations,
                    key=_reevaluation_order_key,
                )
            else:
                predecessor = parent_attempt
            expected_supersedes = (
                f"{predecessor['attempt_id']}@{predecessor['rubric_version']}"
            )
            if attempt["supersedes_evaluation_id"] != expected_supersedes:
                raise ValidationError(
                    "supersedes_evaluation_id must identify the immediate predecessor"
                )
            if _reevaluation_order_key(attempt) <= _reevaluation_order_key(predecessor):
                raise ValidationError(
                    "re-evaluation ordering key must be strictly later than its immediate predecessor"
                )


def _historical_registration_state(root: Path, modality: str) -> tuple[list[dict], list[dict]]:
    attempts = [
        read_yaml(directory / "attempt.yaml")
        for directory in _attempt_directories(root, modality)
    ]
    attempts.sort(
        key=lambda row: (str(row.get("submitted_at", "")), str(row.get("attempt_id", "")))
    )
    return attempts, load_canonical_events(root, modality)


def validate_practice_events(
    root: Path,
    attempt: dict,
    response: str,
    events: tuple[dict, ...],
    speaking_context: object | None = None,
) -> None:
    """Validate evidence/status against the complete persisted modality history.

    The caller must hold ``_registration_lock`` whenever this result is used to
    publish. Gate builders also invoke it as a preflight for direct API users;
    publication repeats it under the lock to close that race.
    """
    historical_attempts, historical_events = _historical_registration_state(
        root, attempt["modality"]
    )
    for event in events:
        validate_event_context(
            root=root,
            attempt=attempt,
            response=response,
            event=event,
            current_events=events,
            historical_attempts=historical_attempts,
            historical_events=historical_events,
            speaking_context=speaking_context,
        )


def validate_practice_context(
    root: Path,
    registration: ValidatedPracticeRegistration,
) -> None:
    """Compatibility adapter for publication of a typed registration bundle."""
    validate_practice_events(
        root,
        registration.attempt,
        registration.response,
        registration.events,
        registration.speaking_context,
    )


def _validate_canonical_event_ids(
    root: Path,
    attempt: dict,
    registration: ValidatedPracticeRegistration | ValidatedReevaluationRegistration,
) -> None:
    if not isinstance(registration, ValidatedPracticeRegistration):
        return
    existing_event_ids = {
        event["event_id"]
        for event in load_canonical_events(root, attempt["modality"])
    }
    for event in registration.events:
        if event["event_id"] in existing_event_ids:
            raise ValidationError(f"duplicate event_id: {event['event_id']}")


def publish_registration(
    root: Path,
    manifest: dict,
    registration: ValidatedPracticeRegistration | ValidatedReevaluationRegistration,
    failpoint: Callable[[str], None] | None = None,
) -> Path:
    _validate_registration(manifest, registration)
    attempt = registration.attempt
    with _registration_lock(root):
        attempts = root / "tracker" / attempt["modality"] / "attempts"
        _cleanup_abandoned_staging(attempts)
        _validate_existing_attempts(root, attempt, attempts)
        _validate_canonical_event_ids(root, attempt, registration)
        if (
            isinstance(registration, ValidatedPracticeRegistration)
            and registration.require_contextual_validation
        ):
            validate_practice_context(root, registration)
        attempts.mkdir(parents=True, exist_ok=True)
        destination = attempts / attempt["attempt_id"]
        staging = Path(
            tempfile.mkdtemp(
                prefix=f"{_STAGING_PREFIX}{attempt['attempt_id']}.", dir=attempts
            )
        )
        try:
            atomic_write_text(
                staging / "attempt.yaml",
                yaml.safe_dump(attempt, allow_unicode=True, sort_keys=False),
            )
            if failpoint is not None:
                failpoint("after_attempt")
            if isinstance(registration, ValidatedPracticeRegistration):
                atomic_write_text(staging / "prompt.md", registration.prompt.rstrip() + "\n")
                response_name = _response_filename(
                    attempt["modality"], attempt["record_type"]
                )
                atomic_write_text(
                    staging / response_name, registration.response.rstrip() + "\n"
                )
                for name, content in registration.extra_files.items():
                    atomic_write_text(staging / name, content)
                events = registration.events
            else:
                events = ()
            atomic_write_text(
                staging / "feedback-round-1.md", registration.feedback.rstrip() + "\n"
            )
            atomic_write_text(staging / "events.jsonl", canonical_jsonl(events))
            if failpoint is not None:
                failpoint("after_events")
            fsync_directory(staging)
            if failpoint is not None:
                failpoint("after_staging_fsync")
                failpoint("before_rename")
            staging.rename(destination)
            fsync_directory(attempts)
            if failpoint is not None:
                failpoint("after_rename")
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return destination


def register_attempt(
    root: Path,
    manifest: dict,
    attempt: dict,
    prompt: str,
    response: str,
    feedback: str,
    events: list[dict],
    extra_files: Mapping[str, str] | None = None,
) -> Path:
    if extra_files is None:
        extra_files = {}
    registration = ValidatedPracticeRegistration(
        attempt=attempt,
        prompt=prompt,
        response=response,
        feedback=feedback,
        events=tuple(events),
        extra_files=extra_files,
    )
    destination = publish_registration(root, manifest, registration)
    with _registration_lock(root):
        write_aggregate_events(root, attempt["modality"])
    return destination
