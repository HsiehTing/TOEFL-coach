import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import toefl_tracker.register as register_module
from test_validation import MANIFEST, valid_attempt, valid_error_event
from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.register import register_attempt


def test_register_writes_immutable_attempt_and_events(tmp_path: Path) -> None:
    attempt = valid_attempt()
    attempt["source_hash"] = canonical_source_hash("prompt", "response")
    event = {
        "event_id": "ERR-20260731-0001",
        "attempt_id": attempt["attempt_id"],
        "taxonomy_version": 1,
        "code": "GRAM-NEGATION",
        "source_excerpt": "do not think it is not",
        "audio_timestamp": None,
        "suggested_revision": "do not think it is",
        "reason": "Double negative.",
        "level": "must_fix",
        "severity": "meaning_changing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }

    path = register_attempt(
        tmp_path, MANIFEST, attempt, "prompt", "response", "feedback", [event]
    )

    assert (path / "attempt.yaml").exists()
    assert (path / "prompt.md").read_text() == "prompt\n"
    assert (path / "response-original.md").read_text() == "response\n"
    rows = (tmp_path / "tracker/writing/error-events.jsonl").read_text().splitlines()
    assert json.loads(rows[0])["event_id"] == event["event_id"]


def test_duplicate_source_hash_is_rejected(tmp_path: Path) -> None:
    attempt = valid_attempt()
    attempt["source_hash"] = canonical_source_hash("prompt", "response")
    register_attempt(tmp_path, MANIFEST, attempt, "prompt", "response", "feedback", [])
    duplicate = {**attempt, "attempt_id": "W-AD-20260731-002"}

    with pytest.raises(ValidationError, match="duplicate"):
        register_attempt(
            tmp_path, MANIFEST, duplicate, "prompt", "response", "feedback", []
        )


def test_revision_uses_revision_filename_and_parent_link(tmp_path: Path) -> None:
    original = valid_attempt()
    register_attempt(tmp_path, MANIFEST, original, "prompt", "response", "feedback", [])
    revision = {
        **valid_attempt(),
        "attempt_id": "W-AD-20260731-001-R1",
        "record_type": "revision",
        "parent_attempt_id": original["attempt_id"],
        "revision_outcomes": {
            "assigned": 2,
            "resolved": 1,
            "partly_resolved": 1,
            "unresolved": 0,
            "new_errors": 0,
            "resolution_rate": 0.5,
        },
        "source_hash": canonical_source_hash("prompt", "revised response"),
    }

    path = register_attempt(
        tmp_path, MANIFEST, revision, "prompt", "revised response", "feedback", []
    )

    assert (path / "response-revision.md").read_text() == "revised response\n"
    assert not (path / "response-original.md").exists()


def test_registration_rolls_back_when_ledger_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempt = valid_attempt()
    original_write = register_module.atomic_write_text

    def fail_ledger_write(path: Path, content: str) -> None:
        if path.name == "error-events.jsonl":
            raise OSError("ledger unavailable")
        original_write(path, content)

    monkeypatch.setattr(register_module, "atomic_write_text", fail_ledger_write)

    with pytest.raises(OSError, match="ledger unavailable"):
        register_attempt(
            tmp_path, MANIFEST, attempt, "prompt", "response", "feedback", []
        )

    attempts = tmp_path / "tracker/writing/attempts"
    assert not (attempts / attempt["attempt_id"]).exists()
    assert not list(attempts.iterdir())
    assert not (tmp_path / "tracker/writing/error-events.jsonl").exists()


def test_registration_restores_ledger_when_attempt_publish_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_attempt = valid_attempt()
    first_event = valid_error_event()
    register_attempt(
        tmp_path,
        MANIFEST,
        first_attempt,
        "prompt",
        "response",
        "feedback",
        [first_event],
    )
    second_attempt = {
        **valid_attempt(),
        "attempt_id": "W-AD-20260731-002",
        "source_hash": canonical_source_hash("prompt", "second response"),
    }
    second_event = {
        **valid_error_event(),
        "event_id": "ERR-20260731-0002",
        "attempt_id": second_attempt["attempt_id"],
    }
    original_rename = Path.rename

    def fail_attempt_publish(path: Path, target: Path) -> Path:
        if Path(target).name == second_attempt["attempt_id"]:
            raise OSError("attempt publish failed")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_attempt_publish)

    with pytest.raises(OSError, match="attempt publish failed"):
        register_attempt(
            tmp_path,
            MANIFEST,
            second_attempt,
            "prompt",
            "second response",
            "feedback",
            [second_event],
        )

    rows = (tmp_path / "tracker/writing/error-events.jsonl").read_text().splitlines()
    assert [json.loads(row)["event_id"] for row in rows] == [first_event["event_id"]]
    attempts = tmp_path / "tracker/writing/attempts"
    assert not (attempts / second_attempt["attempt_id"]).exists()
    assert {path.name for path in attempts.iterdir()} == {first_attempt["attempt_id"]}


def test_concurrent_registrations_preserve_all_ledger_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_attempt = valid_attempt()
    first_event = valid_error_event()
    second_attempt = {
        **valid_attempt(),
        "attempt_id": "W-AD-20260731-002",
        "source_hash": canonical_source_hash("prompt", "second response"),
    }
    second_event = {
        **valid_error_event(),
        "event_id": "ERR-20260731-0002",
        "attempt_id": second_attempt["attempt_id"],
    }
    original_write = register_module.atomic_write_text
    first_ledger_write_started = threading.Event()
    second_ledger_write_started = threading.Event()
    ledger_call_lock = threading.Lock()
    ledger_calls = 0

    def coordinate_ledger_writes(path: Path, content: str) -> None:
        nonlocal ledger_calls
        if path.name != "error-events.jsonl":
            original_write(path, content)
            return
        with ledger_call_lock:
            ledger_calls += 1
            call_number = ledger_calls
        if call_number == 1:
            first_ledger_write_started.set()
            second_ledger_write_started.wait(timeout=0.25)
        else:
            second_ledger_write_started.set()
        original_write(path, content)

    monkeypatch.setattr(
        register_module, "atomic_write_text", coordinate_ledger_writes
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            register_attempt,
            tmp_path,
            MANIFEST,
            first_attempt,
            "prompt",
            "response",
            "feedback",
            [first_event],
        )
        assert first_ledger_write_started.wait(timeout=1)
        second = executor.submit(
            register_attempt,
            tmp_path,
            MANIFEST,
            second_attempt,
            "prompt",
            "second response",
            "feedback",
            [second_event],
        )
        first.result(timeout=2)
        second.result(timeout=2)

    rows = (tmp_path / "tracker/writing/error-events.jsonl").read_text().splitlines()
    assert {json.loads(row)["event_id"] for row in rows} == {
        first_event["event_id"],
        second_event["event_id"],
    }


def test_registration_reclaims_stale_directory_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale_lock = tmp_path / "tracker/.register.lock"
    stale_lock.mkdir(parents=True)
    (stale_lock / "owner.json").write_text('{"pid": 999999999}\n')
    monotonic_values = iter([0.0, 11.0])
    monkeypatch.setattr(
        register_module.time, "monotonic", lambda: next(monotonic_values)
    )

    path = register_attempt(
        tmp_path, MANIFEST, valid_attempt(), "prompt", "response", "feedback", []
    )

    assert (path / "attempt.yaml").exists()
    assert not stale_lock.is_dir()


def test_registration_cleans_abandoned_hidden_staging_directory(
    tmp_path: Path,
) -> None:
    attempts = tmp_path / "tracker/writing/attempts"
    abandoned = attempts / ".W-AD-20260730-999.crashed"
    abandoned.mkdir(parents=True)
    (abandoned / "prompt.md").write_text("partial\n")

    path = register_attempt(
        tmp_path, MANIFEST, valid_attempt(), "prompt", "response", "feedback", []
    )

    assert (path / "attempt.yaml").exists()
    assert not abandoned.exists()


def test_hash_mismatch_is_rejected_before_writing(tmp_path: Path) -> None:
    attempt = valid_attempt()
    attempt["source_hash"] = canonical_source_hash("different", "content")

    with pytest.raises(ValidationError, match="source_hash"):
        register_attempt(
            tmp_path, MANIFEST, attempt, "prompt", "response", "feedback", []
        )

    assert not (tmp_path / "tracker").exists()


def test_event_must_belong_to_registered_attempt(tmp_path: Path) -> None:
    event = {**valid_error_event(), "attempt_id": "W-AD-20260731-999"}

    with pytest.raises(ValidationError, match="does not match"):
        register_attempt(
            tmp_path, MANIFEST, valid_attempt(), "prompt", "response", "feedback", [event]
        )


def test_invalid_event_is_rejected_before_writing(tmp_path: Path) -> None:
    event = valid_error_event()
    del event["severity"]

    with pytest.raises(ValidationError, match="missing event fields"):
        register_attempt(
            tmp_path, MANIFEST, valid_attempt(), "prompt", "response", "feedback", [event]
        )

    assert not (tmp_path / "tracker").exists()


def test_duplicate_attempt_id_is_rejected(tmp_path: Path) -> None:
    original = valid_attempt()
    register_attempt(tmp_path, MANIFEST, original, "prompt", "response", "feedback", [])
    duplicate = {
        **valid_attempt(),
        "source_hash": canonical_source_hash("prompt", "different response"),
    }

    with pytest.raises(ValidationError, match="attempt_id"):
        register_attempt(
            tmp_path,
            MANIFEST,
            duplicate,
            "prompt",
            "different response",
            "feedback",
            [],
        )


def test_revision_requires_persisted_parent(tmp_path: Path) -> None:
    revision = {
        **valid_attempt(),
        "attempt_id": "W-AD-20260731-001-R1",
        "record_type": "revision",
        "parent_attempt_id": "W-AD-20260731-001",
        "revision_outcomes": {
            "assigned": 1,
            "resolved": 1,
            "partly_resolved": 0,
            "unresolved": 0,
            "new_errors": 0,
            "resolution_rate": 1.0,
        },
        "source_hash": canonical_source_hash("prompt", "revision"),
    }

    with pytest.raises(ValidationError, match="parent"):
        register_attempt(
            tmp_path, MANIFEST, revision, "prompt", "revision", "feedback", []
        )


def test_speaking_attempt_uses_transcript_filename(tmp_path: Path) -> None:
    attempt = {
        **valid_attempt(),
        "attempt_id": "S-LR-20260731-001",
        "modality": "speaking",
        "task_type": "listen_and_repeat",
        "rubric_version": "ets-speaking-blueprint-2026-diagnostic",
        "result_type": "diagnostic_only",
    }

    path = register_attempt(
        tmp_path, MANIFEST, attempt, "prompt", "response", "feedback", []
    )

    assert (path / "transcript-original.md").read_text() == "response\n"
    assert not (path / "response-original.md").exists()
