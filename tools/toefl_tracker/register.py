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
        if registration.result_only:
            if (
                attempt["record_type"] != "targeted_drill"
                or registration.events
                or registration.prompt
                or registration.response
            ):
                raise ValidationError("result-only registration must contain only drill results")
        else:
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


def persisted_attempt_relationship_problems(
    attempts: list[dict], incoming_attempt_id: str | None = None
) -> list[tuple[str, str]]:
    """Return every independently verifiable cross-attempt contract violation."""
    problems: list[tuple[str, str]] = []
    by_id: dict[str, dict] = {}
    source_hashes: dict[str, dict] = {}
    for attempt in attempts:
        attempt_id = attempt.get("attempt_id")
        if not isinstance(attempt_id, str) or not attempt_id:
            problems.append(("<unknown>", "attempt_id must be a non-empty string"))
            continue
        if attempt_id in by_id:
            problems.append((attempt_id, "duplicate attempt_id"))
            continue
        by_id[attempt_id] = attempt
        if attempt.get("record_type") != "re_evaluation":
            source_hash = attempt.get("source_hash")
            if source_hash in source_hashes:
                problems.append(
                    (attempt_id, f"duplicate source_hash: {source_hashes[source_hash]['attempt_id']}")
                )
            else:
                source_hashes[source_hash] = attempt

    by_parent: dict[str, list[dict]] = {}
    for attempt_id, attempt in by_id.items():
        if attempt.get("record_type") not in {"revision", "re_evaluation"}:
            continue
        parent_id = attempt.get("parent_attempt_id")
        parent = by_id.get(parent_id)
        if parent is None:
            problems.append((attempt_id, "revision parent does not exist"))
            continue
        expected_parent_types = (
            {"formal_original"}
            if attempt.get("record_type") == "re_evaluation"
            else {"formal_original", "revision"}
        )
        if (
            parent.get("record_type") not in expected_parent_types
            or parent.get("modality") != attempt.get("modality")
            or parent.get("task_type") != attempt.get("task_type")
        ):
            problems.append((
                attempt_id,
                "re-evaluation parent must be matching formal original"
                if attempt.get("record_type") == "re_evaluation"
                else "revision parent must be matching formal original or revision",
            ))
            continue
        if attempt.get("record_type") == "revision":
            try:
                if _normalized_lineage_timestamp(parent.get("submitted_at"), "revision parent submitted_at") >= _normalized_lineage_timestamp(attempt.get("submitted_at"), "revision submitted_at"):
                    problems.append((attempt_id, "revision must be submitted after its parent"))
            except ValidationError as error:
                problems.append((attempt_id, str(error)))
            continue
        if attempt.get("record_type") == "re_evaluation":
            try:
                if attempt.get("schema_version") == 2:
                    validate_reevaluation_metadata(attempt)
                elif attempt.get("schema_version") != 1:
                    raise ValidationError("re-evaluation has an unsupported schema_version")
            except ValidationError as error:
                problems.append((attempt_id, str(error)))
                continue
            if attempt.get("source_hash") != parent.get("source_hash"):
                problems.append((attempt_id, "re-evaluation source_hash must match formal parent"))
                continue
            by_parent.setdefault(parent_id, []).append(attempt)

    for parent_id, reevaluations in by_parent.items():
        if incoming_attempt_id is not None:
            incoming = next(
                (row for row in reevaluations if row["attempt_id"] == incoming_attempt_id),
                None,
            )
            if incoming is not None:
                existing = [row for row in reevaluations if row is not incoming]
                try:
                    predecessor = max(existing, key=_reevaluation_order_key) if existing else by_id[parent_id]
                    incoming_key = _reevaluation_order_key(incoming)
                    predecessor_key = _reevaluation_order_key(predecessor)
                except ValidationError as error:
                    problems.append((incoming["attempt_id"], str(error)))
                    continue
                expected_supersedes = (
                    f"{predecessor['attempt_id']}@{predecessor['rubric_version']}"
                )
                if incoming["supersedes_evaluation_id"] != expected_supersedes:
                    problems.append(
                        (incoming["attempt_id"], "supersedes_evaluation_id must identify the immediate predecessor")
                    )
                elif incoming_key <= predecessor_key:
                    problems.append(
                        (incoming["attempt_id"], "re-evaluation ordering key must be strictly later than its immediate predecessor")
                    )
                continue
        predecessor = by_id[parent_id]
        ordered: list[tuple[tuple[datetime, str], dict]] = []
        for attempt in reevaluations:
            try:
                ordered.append((_reevaluation_order_key(attempt), attempt))
            except ValidationError as error:
                problems.append((attempt["attempt_id"], str(error)))
        for attempt_key, attempt in sorted(ordered):
            try:
                if attempt_key <= _reevaluation_order_key(predecessor):
                    raise ValidationError(
                        "re-evaluation ordering key must be strictly later than its immediate predecessor"
                    )
            except ValidationError as error:
                problems.append((attempt["attempt_id"], str(error)))
                predecessor = attempt
                continue
            if attempt.get("schema_version") == 1:
                predecessor = attempt
                continue
            expected_supersedes = (
                f"{predecessor['attempt_id']}@{predecessor['rubric_version']}"
            )
            if attempt["supersedes_evaluation_id"] != expected_supersedes:
                problems.append(
                    (attempt["attempt_id"], "supersedes_evaluation_id must identify the immediate predecessor")
                )
                predecessor = attempt
                continue
            predecessor = attempt
    return problems


def validate_persisted_attempt_relationships(
    attempts: list[dict], incoming_attempt_id: str | None = None
) -> None:
    """Apply registration's cross-attempt invariants with fail-fast semantics."""
    problems = persisted_attempt_relationship_problems(attempts, incoming_attempt_id)
    if problems:
        raise ValidationError(problems[0][1])


def _validate_existing_attempts(root: Path, attempt: dict, attempts: Path) -> None:
    existing_attempts: list[dict] = []
    for directory in _attempt_directories(root, attempt["modality"]):
        existing = read_yaml(directory / "attempt.yaml")
        existing_attempts.append(existing)
        if existing["attempt_id"] == attempt["attempt_id"]:
            raise ValidationError("attempt_id already exists")
        if (
            attempt["record_type"] != "re_evaluation"
            and existing["source_hash"] == attempt["source_hash"]
        ):
            raise ValidationError(f"duplicate source_hash: {existing['attempt_id']}")
    validate_persisted_attempt_relationships(
        [*existing_attempts, attempt], incoming_attempt_id=attempt["attempt_id"]
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
                if not registration.result_only:
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
