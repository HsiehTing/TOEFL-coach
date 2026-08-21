from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

from toefl_tracker.acoustic_evidence import build_acoustic_evidence, fuse_speaking_evidence


def _mapping() -> dict:
    return {
        "task_type": "listen_and_repeat",
        "rows": [
            {"segment_id": "source-1", "item": 1, "role": "examiner", "text": "Welcome to class."},
            {
                "segment_id": "learner-1",
                "item": 1,
                "role": "learner",
                "start": 10.0,
                "end": 14.0,
                "text": "Welcome to class.",
            },
        ],
    }


def test_build_acoustic_evidence_returns_bounded_pause_proxy(tmp_path: Path) -> None:
    audio = tmp_path / "sample.m4a"
    audio.write_bytes(b"fixture")
    calls: list[list[str]] = []

    def runner(command: list[str], **_: object) -> CompletedProcess[str]:
        calls.append(command)
        return CompletedProcess(
            command,
            0,
            "",
            "silence_start: 0.500\nsilence_end: 1.000\n",
        )

    evidence = build_acoustic_evidence(
        audio,
        _mapping(),
        {"segments": [{"segment_id": "learner-1", "words": [{"word": "Welcome"}, {"word": "to"}, {"word": "class"}]}]},
        runner=runner,
    )

    assert len(calls) == 1
    assert evidence[0]["word_count"] == 3
    assert evidence[0]["pause_count"] == 1
    assert evidence[0]["pause_seconds"] == 0.5
    assert evidence[0]["evidence_status"] == "diagnostic_only"
    assert evidence[0]["dimensions"] == {
        "fluency": "proxy",
        "pronunciation": "unavailable",
        "prosody": "unavailable",
        "intelligibility": "unavailable",
    }


def test_fuse_speaking_evidence_keeps_pronunciation_fail_closed() -> None:
    result = fuse_speaking_evidence(
        "listen_and_repeat",
        _mapping(),
        [{"segment_id": "learner-1", "text_usable": True, "acoustic_usable": True}],
        [{
            "segment_id": "learner-1",
            "dimensions": {"fluency": "proxy", "pronunciation": "unavailable"},
            "speech_rate_wpm": 90.0,
        }],
    )

    item = result["items"][0]
    assert result["result_type"] == "diagnostic_only"
    assert item["text"]["reconstruction_similarity"] == 1.0
    assert item["acoustic"]["dimensions"]["pronunciation"] == "unavailable"
    assert "not phoneme-level pronunciation evidence" in result["limitations"][2]
