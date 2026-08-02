import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from test_validation import MANIFEST, valid_attempt, valid_error_event
from toefl_tracker.canonical import (
    canonical_jsonl,
    load_canonical_events,
    migrate_event_sidecars,
    render_aggregate_events,
)
from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError, ValidatedPracticeRegistration
from toefl_tracker.register import publish_registration


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _registration(attempt_id: str, response: str = "response") -> ValidatedPracticeRegistration:
    attempt = valid_attempt()
    attempt["attempt_id"] = attempt_id
    attempt["source_hash"] = canonical_source_hash("prompt", response)
    event = valid_error_event()
    event["attempt_id"] = attempt_id
    event["event_id"] = f"ERR-{attempt_id[-3:]}"
    return ValidatedPracticeRegistration(
        attempt=attempt,
        prompt="prompt",
        response=response,
        feedback="feedback",
        events=(event,),
    )


@pytest.fixture
def manifest() -> dict:
    return MANIFEST


@pytest.fixture
def valid_registration() -> ValidatedPracticeRegistration:
    return _registration("W-AD-20260731-001")


@dataclass(frozen=True)
class PopulatedCanonicalAttempts:
    expected_jsonl: tuple[str, ...]


@pytest.fixture
def populated_canonical_attempts(tmp_path: Path, manifest: dict) -> PopulatedCanonicalAttempts:
    first = _registration("W-AD-20260731-001")
    second = _registration("W-AD-20260731-002", response="second response")
    publish_registration(tmp_path, manifest, first)
    publish_registration(tmp_path, manifest, second)
    return PopulatedCanonicalAttempts(
        expected_jsonl=(canonical_jsonl(first.events), canonical_jsonl(second.events))
    )


@pytest.fixture
def legacy_tracker(tmp_path: Path) -> Path:
    attempt = valid_attempt()
    attempt["source_hash"] = canonical_source_hash("prompt", "response")
    attempt_directory = tmp_path / "tracker/writing/attempts" / attempt["attempt_id"]
    attempt_directory.mkdir(parents=True)
    import yaml

    (attempt_directory / "attempt.yaml").write_text(
        yaml.safe_dump(attempt, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    event = valid_error_event()
    (tmp_path / "tracker/writing/error-events.jsonl").write_text(
        canonical_jsonl((event,)), encoding="utf-8"
    )
    return tmp_path / "tracker/writing"


def test_published_attempt_contains_its_own_event_sidecar(
    tmp_path: Path, manifest: dict, valid_registration: ValidatedPracticeRegistration
) -> None:
    destination = publish_registration(tmp_path, manifest, valid_registration)

    assert (destination / "events.jsonl").read_text(encoding="utf-8") == canonical_jsonl(
        valid_registration.events
    )
    assert not (tmp_path / "tracker/writing/error-events.jsonl").exists()


def test_aggregate_ledger_is_rendered_from_attempt_sidecars(
    tmp_path: Path, populated_canonical_attempts: PopulatedCanonicalAttempts
) -> None:
    expected = "".join(populated_canonical_attempts.expected_jsonl)

    assert render_aggregate_events(tmp_path, "writing") == expected
    assert load_canonical_events(tmp_path, "writing") == [
        json.loads(row)
        for sidecar in populated_canonical_attempts.expected_jsonl
        for row in sidecar.splitlines()
    ]


def test_migration_dry_run_is_non_mutating_and_apply_is_idempotent(
    tmp_path: Path, legacy_tracker: Path
) -> None:
    before = tree_digest(tmp_path)

    result = migrate_event_sidecars(tmp_path, apply=False)

    assert result.created == ("W-AD-20260731-001",)
    assert tree_digest(tmp_path) == before
    migrate_event_sidecars(tmp_path, apply=True)
    after_first = tree_digest(tmp_path)
    migrate_event_sidecars(tmp_path, apply=True)
    assert tree_digest(tmp_path) == after_first


def test_migration_stops_on_existing_conflicting_sidecar(
    tmp_path: Path, legacy_tracker: Path
) -> None:
    sidecar = legacy_tracker / "attempts/W-AD-20260731-001/events.jsonl"
    sidecar.write_text('{"event_id":"CONFLICT"}\n', encoding="utf-8")

    with pytest.raises(ValidationError, match="conflicting canonical event sidecar"):
        migrate_event_sidecars(tmp_path, apply=True)


def test_migration_rejects_orphan_event(tmp_path: Path, legacy_tracker: Path) -> None:
    orphan = valid_error_event()
    orphan["attempt_id"] = "W-AD-20260731-999"
    ledger = legacy_tracker / "error-events.jsonl"
    ledger.write_text(canonical_jsonl((orphan,)), encoding="utf-8")

    with pytest.raises(ValidationError, match="orphan event"):
        migrate_event_sidecars(tmp_path, apply=True)


def test_migration_rejects_duplicate_event_id(tmp_path: Path, legacy_tracker: Path) -> None:
    event = valid_error_event()
    ledger = legacy_tracker / "error-events.jsonl"
    ledger.write_text(canonical_jsonl((event, event)), encoding="utf-8")

    with pytest.raises(ValidationError, match="duplicate event_id"):
        migrate_event_sidecars(tmp_path, apply=True)
