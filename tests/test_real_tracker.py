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


def test_real_tracker_preserves_the_historical_writing_record() -> None:
    attempt_dir = ROOT / "tracker/writing/attempts/W-AD-20260731-001"
    attempt = read_yaml(attempt_dir / "attempt.yaml")
    events = [
        json.loads(line)
        for line in (attempt_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert attempt["word_count"] == 183
    assert len(events) == 7
    assert {row["attempt_id"] for row in events} == {"W-AD-20260731-001"}
    # The learner's live tracker grows over time; this regression test protects
    # the historical baseline record without freezing the overall formal count.
    assert _formal_count("writing") >= 1
    assert _formal_count("speaking") == 0
