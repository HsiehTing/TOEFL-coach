import json
import os
import shutil
import tempfile
import time
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Callable, Iterator

import yaml

from toefl_tracker.canonical import (
    canonical_jsonl,
    load_canonical_events,
    write_aggregate_events,
)
from toefl_tracker.io import atomic_write_text, canonical_source_hash, read_yaml
from toefl_tracker.models import (
    ValidatedPracticeRegistration,
    ValidatedReevaluationRegistration,
    ValidationError,
)
from toefl_tracker.validation import validate_attempt, validate_error_event

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
    for path in attempts.iterdir():
        is_known_staging = path.name.startswith(
            (_STAGING_PREFIX, ".W-", ".S-")
        )
        if path.is_dir() and is_known_staging:
            # A completed staging directory is durable crash-recovery state.
            marker = path / ".ready"
            attempt_file = path / "attempt.yaml"
            if marker.exists() and attempt_file.exists():
                try:
                    attempt_id = read_yaml(attempt_file)["attempt_id"]
                    destination = attempts / attempt_id
                    if not destination.exists():
                        path.rename(destination)
                        continue
                except (OSError, KeyError, ValidationError, yaml.YAMLError):
                    pass
            shutil.rmtree(path)


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


def _validate_existing_attempts(root: Path, attempt: dict, attempts: Path) -> None:
    for directory in _attempt_directories(root, attempt["modality"]):
        existing = read_yaml(directory / "attempt.yaml")
        if existing["attempt_id"] == attempt["attempt_id"]:
            raise ValidationError("attempt_id already exists")
        if existing["source_hash"] == attempt["source_hash"]:
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
            atomic_write_text(staging / ".ready", "ready\n")
            if failpoint is not None:
                failpoint("before_publish")
            staging.rename(destination)
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
