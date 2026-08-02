import os
import subprocess
import sys
from pathlib import Path

import pytest

from toefl_tracker.canonical import load_canonical_events
import toefl_tracker.register as register_module


ROOT = Path(__file__).parents[1]
HELPER = ROOT / "tests/helpers/register_subprocess.py"
ATTEMPT_ID = "W-AD-KILL-001"


def published_attempt_ids(root: Path, modality: str) -> set[str]:
    attempts = root / "tracker" / modality / "attempts"
    if not attempts.exists():
        return set()
    return {
        path.name
        for path in attempts.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }


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
    if ATTEMPT_ID in attempts:
        assert {row["attempt_id"] for row in events} == {ATTEMPT_ID}
    else:
        assert events == []


def test_recovery_discards_ready_staging_instead_of_publishing_it(tmp_path: Path) -> None:
    staging = tmp_path / "tracker/writing/attempts/.register-W-AD-KILL-001.crashed"
    staging.mkdir(parents=True)
    (staging / ".ready").write_text("ready\n", encoding="utf-8")
    (staging / "attempt.yaml").write_text("attempt_id: W-AD-KILL-001\n", encoding="utf-8")

    register_module.recover_registration_state(tmp_path)

    assert not staging.exists()
    assert published_attempt_ids(tmp_path, "writing") == set()
