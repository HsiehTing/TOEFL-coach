import json
from pathlib import Path

import pytest

from toefl_tracker.models import ValidationError
from toefl_tracker.role_mapping import (
    infer_toefl_role_map_from_asr,
    infer_toefl_role_map_from_single_item_asr,
)


ROOT = Path(__file__).parents[1]


def fixture(name: str) -> list[dict]:
    return json.loads((ROOT / "tests/fixtures/audio" / name).read_text(encoding="utf-8"))


def test_listen_and_repeat_filters_directions_and_maps_seven_pairs() -> None:
    rows = [
        {"start": 0.0, "end": 1.0, "text": "Listen to your trainer and repeat what she says."},
        {"start": 1.2, "end": 1.7, "text": "Repeat only once."},
    ]
    rows.extend(
        {
            **row,
            "start": row["start"] + 2.0,
            "end": row["end"] + 2.0,
        }
        for row in fixture("listen-repeat-transcript.json")
    )

    result = infer_toefl_role_map_from_asr("listen_and_repeat", rows)

    assert result.requires_confirmation is False
    assert len(result.rows) == 14
    assert [(row.item, row.role) for row in result.rows] == [
        (item, role)
        for item in range(1, 8)
        for role in ("examiner", "learner")
    ]
    assert all(row.role_reason.startswith("asr_") for row in result.rows)


def test_listen_and_repeat_filters_scenario_setup_and_trailing_duplicate_fragment() -> None:
    rows = [
        {"start": 0.0, "end": 2.0, "text": "You are explaining the layout to visitors."},
        {"start": 2.2, "end": 3.0, "text": "Listen and repeat what he says."},
    ]
    for item in range(1, 8):
        start = 10.0 + item * 5
        sentence = f"The parking sentence for item {item} is clear."
        rows.extend([
            {"start": start, "end": start + 1.0, "text": sentence},
            {"start": start + 2.0, "end": start + 3.0, "text": sentence},
        ])
    rows.insert(-4, {
        "start": rows[-5]["end"] + 0.2,
        "end": rows[-5]["end"] + 0.5,
        "text": rows[-5]["text"],
    })

    result = infer_toefl_role_map_from_asr("listen_and_repeat", rows)

    assert result.requires_confirmation is False
    assert [(row.item, row.role) for row in result.rows] == [
        (item, role) for item in range(1, 8) for role in ("examiner", "learner")
    ]


def test_listen_and_repeat_selects_complete_late_retry_without_voice_identity() -> None:
    rows = fixture("listen-repeat-transcript.json")
    rows[-1] = {"start": 32.2, "end": 32.8, "text": "Remember to bring your identification card."}
    rows.append({"start": 33.1, "end": 34.5, "text": "Remember to bring your identification card tomorrow."})

    result = infer_toefl_role_map_from_asr("listen_and_repeat", rows)

    assert result.requires_confirmation is False
    assert result.rows[-1].text.endswith("tomorrow.")


def test_listen_and_repeat_marks_unrelated_turn_as_ambiguous() -> None:
    rows = fixture("listen-repeat-transcript.json")
    rows[1]["text"] = "I prefer studying in the library because it is quiet."

    result = infer_toefl_role_map_from_asr("listen_and_repeat", rows)

    assert result.requires_confirmation is True
    assert result.ambiguous_rows[0].item == 1


def test_interview_keeps_question_answer_route_and_does_not_use_repeat_matching() -> None:
    rows = [
        {**row, "start": row["start"] + 38.0, "end": row["end"] + 38.0}
        for row in fixture("interview-transcript.json")
    ]
    rows.insert(0, {"start": 36.0, "end": 37.0, "text": "You are taking an interview about campus life."})

    result = infer_toefl_role_map_from_asr("take_an_interview", rows)

    assert result.requires_confirmation is False
    assert len(result.rows) == 8
    assert [(row.item, row.role) for row in result.rows] == [
        (item, role)
        for item in range(1, 5)
        for role in ("examiner", "learner")
    ]


def test_asr_mapping_rejects_overlap_and_unknown_route() -> None:
    with pytest.raises(ValidationError, match="overlap"):
        infer_toefl_role_map_from_asr(
            "listen_and_repeat",
            [
                {"start": 0.0, "end": 2.0, "text": "The library opens."},
                {"start": 1.0, "end": 3.0, "text": "The library opens."},
            ],
        )
    with pytest.raises(ValidationError, match="unknown TOEFL speaking task"):
        infer_toefl_role_map_from_asr("unknown", [])


def test_single_item_mapping_uses_largest_pause_and_collapses_internal_segments() -> None:
    result = infer_toefl_role_map_from_single_item_asr(
        "listen_and_repeat",
        [
            {"segment_id": "prompt-1", "start": 0.0, "end": 1.2, "text": "The library closes at five."},
            {"segment_id": "prompt-2", "start": 1.25, "end": 1.8, "text": "Please plan ahead."},
            {"segment_id": "answer-1", "start": 3.0, "end": 4.1, "text": "The library closes at five."},
            {"segment_id": "answer-2", "start": 4.2, "end": 4.8, "text": "Please plan ahead."},
        ],
        item=3,
    )

    assert result.requires_confirmation is False
    assert [(row.item, row.role) for row in result.rows] == [(3, "examiner"), (3, "learner")]
    assert result.rows[0].segment_id == "prompt-1+prompt-2"
    assert result.rows[1].segment_id == "answer-1+answer-2"


def test_single_item_mapping_keeps_only_that_item_ambiguous() -> None:
    result = infer_toefl_role_map_from_single_item_asr(
        "listen_and_repeat",
        [{"start": 0.0, "end": 1.0, "text": "The library closes at five."}],
        item=4,
    )

    assert result.requires_confirmation is True
    assert [(row.item, row.reason) for row in result.ambiguous_rows] == [
        (4, "single item needs both prompt and learner turns")
    ]
