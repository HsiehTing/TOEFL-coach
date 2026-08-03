import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from toefl_tracker.models import ValidationError
from toefl_tracker.role_mapping import infer_toefl_role_map


ROOT = Path(__file__).parents[1]


def _rows(name: str) -> list[dict]:
    return json.loads((ROOT / "tests/fixtures/audio" / name).read_text(encoding="utf-8"))


def _pairs(count: int) -> list[tuple[int, str]]:
    return [
        (item, role)
        for item in range(1, count + 1)
        for role in ("examiner", "learner")
    ]


def test_seven_repeat_pairs_are_inferred_without_voice_biometrics() -> None:
    result = infer_toefl_role_map("listen_and_repeat", _rows("listen-repeat-transcript.json"))

    assert [(row.item, row.role) for row in result.rows] == _pairs(7)
    assert all(row.role_reason in {"expected_item_order", "repeat_similarity"} for row in result.rows)
    assert result.requires_confirmation is False
    assert result.ambiguous_rows == ()


def test_four_interview_pairs_use_question_answer_structure() -> None:
    result = infer_toefl_role_map("take_an_interview", _rows("interview-transcript.json"))

    assert [(row.item, row.role) for row in result.rows] == _pairs(4)
    assert all(row.confidence == "high" for row in result.rows)
    assert result.requires_confirmation is False


def test_missing_interview_answer_marks_only_affected_item_ambiguous() -> None:
    rows = _rows("interview-transcript.json")
    del rows[3]

    result = infer_toefl_role_map("take_an_interview", rows)

    assert result.requires_confirmation is True
    assert {row.item for row in result.ambiguous_rows} == {2}
    assert all(row.item != 2 for row in result.rows)


@pytest.mark.parametrize(
    "task_type, rows, message",
    [
        ("take_an_interview", [
            {**row, "text": "Please answer now."} if index == 0 else row
            for index, row in enumerate(_rows("interview-transcript.json"))
        ], "question"),
    ],
)
def test_non_confirmable_transcripts_fail_closed(
    task_type: str, rows: list[dict], message: str
) -> None:
    result = infer_toefl_role_map(task_type, rows)

    assert result.requires_confirmation is True
    assert result.rows == ()
    assert message in result.reason


def test_non_toefl_task_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown TOEFL speaking task"):
        infer_toefl_role_map("not_toefl", _rows("interview-transcript.json"))


def test_overlapping_transcript_is_rejected_before_role_assignment() -> None:
    rows = _rows("interview-transcript.json")
    rows[1]["start"] = rows[0]["end"] - 0.1

    with pytest.raises(ValidationError, match="overlap"):
        infer_toefl_role_map("take_an_interview", rows)


def test_non_mapping_input_is_rejected() -> None:
    with pytest.raises(ValidationError, match="transcript rows"):
        infer_toefl_role_map("listen_and_repeat", ["not a segment"])


def test_prepare_cli_writes_review_artifacts_without_registering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from prepare_speaking_session import main

    source = tmp_path / "private.m4a"
    source.write_bytes(b"private audio")
    output = tmp_path / "review"
    inspection = {
        "path": str(source), "duration_seconds": 40.0, "codec": "aac",
        "sample_rate_hz": 48000, "channels": 1, "mean_dbfs": -30.0,
        "peak_dbfs": -5.0, "clipping": False, "decodable": True,
        "quality": {"usable": True, "dimension_set": "all"}, "provenance": {},
    }
    monkeypatch.setattr(
        "prepare_speaking_session.preflight_audio_tools",
        lambda: SimpleNamespace(ffmpeg="ffmpeg", ffprobe="ffprobe", provenance={}),
    )
    monkeypatch.setattr("prepare_speaking_session.inspect_audio", lambda *args, **kwargs: inspection)
    monkeypatch.setattr(
        "prepare_speaking_session.transcribe_audio",
        lambda *args, **kwargs: _rows("listen-repeat-transcript.json"),
    )
    monkeypatch.setattr(sys, "argv", [
        "prepare_speaking_session.py", "--audio", str(source), "--task-type",
        "listen_and_repeat", "--output-dir", str(output),
    ])

    assert main() == 0
    assert {path.name for path in output.iterdir()} == {
        "audio-inspection.json", "transcript-segments.yaml", "segments.yaml", "source-reference.txt"
    }
    assert not list(output.glob("*.m4a"))
    artifact = json.loads((output / "audio-inspection.json").read_text())
    assert artifact["path"] == str(source)
    mapping = yaml.safe_load((output / "transcript-segments.yaml").read_text())
    assert mapping["requires_confirmation"] is False
