import json
from pathlib import Path

from toefl_tracker.io import read_yaml


ROOT = Path(__file__).parents[1]


def _formal_count(modality: str) -> int:
    base = ROOT / "tracker" / modality / "attempts"
    return sum(
        read_yaml(path / "attempt.yaml").get("record_type") == "formal_original"
        for path in base.glob("*")
        if path.is_dir() and (path / "attempt.yaml").exists()
    )


def _historical_events(attempt_dir: Path, attempt_id: str) -> list[dict]:
    sidecar = attempt_dir / "events.jsonl"
    if sidecar.exists():
        text = sidecar.read_text(encoding="utf-8")
    else:
        # The checked-in baseline predates canonical sidecars. A learner's
        # migrated live tracker uses the sidecar path above; the fallback keeps
        # this regression fixture portable without mutating it during tests.
        ledger = ROOT / "tracker/writing/error-events.jsonl"
        text = "\n".join(
            line for line in ledger.read_text(encoding="utf-8").splitlines()
            if json.loads(line).get("attempt_id") == attempt_id
        )
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_real_tracker_preserves_the_historical_writing_record() -> None:
    attempt_dir = ROOT / "tracker/writing/attempts/W-AD-20260731-001"
    attempt = read_yaml(attempt_dir / "attempt.yaml")
    events = _historical_events(attempt_dir, "W-AD-20260731-001")

    assert attempt["word_count"] == 183
    assert len(events) == 7
    assert {row["attempt_id"] for row in events} == {"W-AD-20260731-001"}
    # The learner's live tracker grows over time; this regression test protects
    # the historical baseline record without freezing the overall formal count.
    assert _formal_count("writing") >= 1
    assert _formal_count("speaking") == 0
