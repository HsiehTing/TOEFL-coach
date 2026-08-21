import pytest

from toefl_tracker.speaking_feedback import (
    render_segment_usability_feedback,
    validate_segment_usability_feedback,
)


def quality_rows() -> list[dict]:
    return [
        {
            "segment_id": "asr-002",
            "start": 10.0,
            "end": 12.5,
            "text_usable": True,
            "acoustic_usable": False,
            "asr_recognizability": {"status": "proxy", "overlap_segment_count": 1},
        },
        {
            "segment_id": "asr-004",
            "start": 20.0,
            "end": 22.0,
            "text_usable": True,
            "acoustic_usable": True,
            "asr_recognizability": {"status": "proxy", "overlap_segment_count": 1},
        },
    ]


def mapping_rows() -> list[dict]:
    return [
        {"segment_id": "asr-002", "item": 1, "role": "learner"},
        {"segment_id": "asr-004", "item": 2, "role": "learner"},
    ]


def test_renderer_separates_text_and_acoustic_usability_by_route() -> None:
    block = render_segment_usability_feedback(
        "take_an_interview", quality_rows(), mapping_rows()
    )

    assert "Route: `take_an_interview` (Take an Interview)" in block
    assert "Text-usable learner turns: `2/2`" in block
    assert "Acoustic-usable learner turns: `1/2`" in block
    assert "Question 1" in block
    assert "directness, relevance, elaboration" in block
    assert "not phoneme-level proof" in block


def test_validator_requires_the_exact_diagnostic_block() -> None:
    block = render_segment_usability_feedback(
        "listen_and_repeat", quality_rows(), mapping_rows()
    )
    validate_segment_usability_feedback(
        "listen_and_repeat", "# Result\n\n" + block, quality_rows(), mapping_rows()
    )
    with pytest.raises(ValueError, match="segment usability block"):
        validate_segment_usability_feedback(
            "listen_and_repeat", "# Result\n", quality_rows(), mapping_rows()
        )
