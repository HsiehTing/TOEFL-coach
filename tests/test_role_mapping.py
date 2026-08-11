import json
from pathlib import Path

import pytest

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


def test_one_repeat_similarity_failure_preserves_other_mapped_items() -> None:
    rows = _rows("listen-repeat-transcript.json")
    rows[3]["text"] = "An unrelated sentence that is not a repetition."

    result = infer_toefl_role_map("listen_and_repeat", rows)

    assert result.requires_confirmation is True
    assert {row.item for row in result.ambiguous_rows} == {2}
    assert {row.item for row in result.rows} == {1, 3, 4, 5, 6, 7}


def test_interview_examiner_instruction_is_not_a_learner_answer() -> None:
    rows = _rows("interview-transcript.json")
    for index in (1, 3, 5, 7):
        rows[index]["text"] = "Please answer this question with enough detail now."

    result = infer_toefl_role_map("take_an_interview", rows)

    assert result.requires_confirmation is True
    assert {row.item for row in result.ambiguous_rows} == {1, 2, 3, 4}


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
