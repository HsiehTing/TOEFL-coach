import json
import os
import shutil
import tempfile
import time
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

import yaml

from toefl_tracker.io import atomic_write_text, canonical_source_hash, read_yaml
from toefl_tracker.models import ValidationError
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
        }
        or not isinstance(content, str)
        for name, content in extra_files.items()
    ):
        raise ValidationError("extra attempt files are invalid")
    expected_hash = canonical_source_hash(prompt, response)
    if attempt["source_hash"] != expected_hash:
        raise ValidationError("source_hash does not match prompt and response")
    validate_attempt(attempt, manifest)
    for event in events:
        validate_error_event(event)
        if event["attempt_id"] != attempt["attempt_id"]:
            raise ValidationError("event attempt_id does not match attempt")
    with _registration_lock(root):
        attempts = root / "tracker" / attempt["modality"] / "attempts"
        _cleanup_abandoned_staging(attempts)
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
        attempts.mkdir(parents=True, exist_ok=True)
        destination = attempts / attempt["attempt_id"]
        staging = Path(
            tempfile.mkdtemp(
                prefix=f"{_STAGING_PREFIX}{attempt['attempt_id']}.", dir=attempts
            )
        )
        ledger = root / "tracker" / attempt["modality"] / "error-events.jsonl"
        ledger_existed = ledger.exists()
        previous = ledger.read_text(encoding="utf-8") if ledger_existed else ""
        ledger_updated = False
        try:
            atomic_write_text(
                staging / "attempt.yaml",
                yaml.safe_dump(attempt, allow_unicode=True, sort_keys=False),
            )
            atomic_write_text(staging / "prompt.md", prompt.rstrip() + "\n")
            response_name = _response_filename(attempt["modality"], attempt["record_type"])
            atomic_write_text(staging / response_name, response.rstrip() + "\n")
            atomic_write_text(staging / "feedback-round-1.md", feedback.rstrip() + "\n")
            for name, content in extra_files.items():
                atomic_write_text(staging / name, content)
            appended = "".join(
                json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
                for event in events
            )
            # The sidecar lets a later registration recover evidence even if the
            # process dies after the aggregate ledger is written.
            atomic_write_text(staging / "events.jsonl", appended)
            atomic_write_text(staging / ".ready", "ready\n")
            atomic_write_text(ledger, previous + appended)
            ledger_updated = True
            staging.rename(destination)
        except Exception:
            if ledger_updated:
                if ledger_existed:
                    atomic_write_text(ledger, previous)
                else:
                    ledger.unlink(missing_ok=True)
            raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return destination
