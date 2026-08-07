import os
import subprocess
import sys
from pathlib import Path

import pytest

from toefl_tracker.canonical import load_canonical_events
from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidatedPracticeRegistration
import toefl_tracker.register as register_module
from test_validation import MANIFEST, valid_attempt, valid_error_event


ROOT = Path(__file__).parents[1]
HELPER = ROOT / "tests/helpers/register_subprocess.py"
ATTEMPT_ID = "W-AD-KILL-001"
_PUBLISHED_BUNDLE = {
    "attempt.yaml",
    "prompt.md",
    "response-original.md",
    "feedback-round-1.md",
    "events.jsonl",
}


def published_attempt_ids(root: Path, modality: str) -> set[str]:
    attempts = root / "tracker" / modality / "attempts"
    if not attempts.exists():
        return set()
    return {
        path.name
        for path in attempts.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }


def staging_directories(root: Path, modality: str) -> set[Path]:
    attempts = root / "tracker" / modality / "attempts"
    if not attempts.exists():
        return set()
    return {
        path
        for path in attempts.iterdir()
        if path.is_dir() and path.name.startswith(".register-")
    }


def valid_registration() -> ValidatedPracticeRegistration:
    attempt = valid_attempt()
    attempt["source_hash"] = canonical_source_hash("prompt", "response")
    return ValidatedPracticeRegistration(
        attempt=attempt,
        prompt="prompt",
        response="response",
        feedback="feedback",
        events=(valid_error_event(),),
    )


@pytest.mark.parametrize(
    "point",
    [
        "after_attempt",
        "after_events",
        "after_staging_fsync",
        "before_rename",
        "after_rename",
    ],
)
def test_process_death_never_separates_attempt_and_events(
    tmp_path: Path, point: str
) -> None:
    completed = subprocess.run(
        [sys.executable, str(HELPER), str(tmp_path), point],
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT / "tools")},
    )

    assert completed.returncode == 91
    register_module.recover_registration_state(tmp_path)
    attempts = published_attempt_ids(tmp_path, "writing")
    events = load_canonical_events(tmp_path, "writing")
    assert staging_directories(tmp_path, "writing") == set()
    if point == "after_rename":
        assert attempts == {ATTEMPT_ID}
        bundle = tmp_path / "tracker/writing/attempts" / ATTEMPT_ID
        assert _PUBLISHED_BUNDLE <= {path.name for path in bundle.iterdir()}
        assert {row["attempt_id"] for row in events} == {ATTEMPT_ID}
    else:
        assert attempts == set()
        assert events == []


def test_recovery_discards_ready_staging_instead_of_publishing_it(tmp_path: Path) -> None:
    staging = tmp_path / "tracker/writing/attempts/.register-W-AD-KILL-001.crashed"
    staging.mkdir(parents=True)
    (staging / ".ready").write_text("ready\n", encoding="utf-8")
    (staging / "attempt.yaml").write_text("attempt_id: W-AD-KILL-001\n", encoding="utf-8")

    register_module.recover_registration_state(tmp_path)

    assert not staging.exists()
    assert published_attempt_ids(tmp_path, "writing") == set()


def test_publish_fsyncs_staging_before_rename_and_attempts_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, Path, Path | None]] = []
    original_rename = Path.rename

    def record_fsync(path: Path) -> None:
        calls.append(("fsync", Path(path), None))

    def record_rename(path: Path, target: Path) -> Path:
        calls.append(("rename", Path(path), Path(target)))
        return original_rename(path, target)

    monkeypatch.setattr(register_module, "fsync_directory", record_fsync)
    monkeypatch.setattr(Path, "rename", record_rename)

    destination = register_module.publish_registration(
        tmp_path, MANIFEST, valid_registration()
    )

    attempts = tmp_path / "tracker/writing/attempts"
    assert [name for name, _, _ in calls] == ["fsync", "rename", "fsync"]
    staging = calls[0][1]
    assert staging.name.startswith(".register-")
    assert calls[1] == ("rename", staging, destination)
    assert calls[2] == ("fsync", attempts, None)
