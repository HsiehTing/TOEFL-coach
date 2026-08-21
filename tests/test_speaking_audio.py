from pathlib import Path
from subprocess import CompletedProcess

from toefl_tracker.speaking import _validate_segment_quality_artifact
from toefl_tracker.speaking_audio import prepare_speaking_session


def asr_backend(*_: object, **__: object) -> dict:
    segments = [
        {"id": 1, "start": 0.0, "end": 0.6, "text": "Listen to your trainer and repeat what she says."},
        {"id": 2, "start": 0.8, "end": 1.1, "text": "Repeat only once."},
    ]
    for item in range(1, 8):
        start = 10.0 + (item - 1) * 4.0
        sentence = f"The campus library opens at eight for item {item}."
        segments.extend([
            {"id": item * 2 + 1, "start": start, "end": start + 1.0, "text": sentence},
            {"id": item * 2 + 2, "start": start + 1.2, "end": start + 2.4, "text": sentence},
        ])
    return {"language": "en", "segments": segments}


def test_prepare_speaking_session_returns_route_mapping_without_audio_path(tmp_path: Path) -> None:
    audio = tmp_path / "private.m4a"
    audio.write_bytes(b"fixture")

    artifact = prepare_speaking_session(
        audio,
        "listen_and_repeat",
        model="test-model",
        backend=asr_backend,
    )

    assert artifact["status"] == "ready_for_diagnostic"
    assert artifact["task_type"] == "listen_and_repeat"
    assert artifact["mapping"]["requires_confirmation"] is False
    assert len(artifact["mapping"]["rows"]) == 14
    assert str(audio) not in str(artifact)


def test_prepare_speaking_session_keeps_text_usable_separate_from_low_audio_quality(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "private.m4a"
    audio.write_bytes(b"fixture")

    def low_quality_runner(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(
            command,
            0,
            "",
            "mean_volume: -46.0 dB\nmax_volume: -10.0 dB\n",
        )

    artifact = prepare_speaking_session(
        audio,
        "listen_and_repeat",
        model="test-model",
        backend=asr_backend,
        include_segment_quality=True,
        quality_runner=low_quality_runner,
    )

    rows = artifact["segment_quality"]
    assert len(rows) == 7
    assert all(row["text_usable"] is True for row in rows)
    assert all(row["acoustic_usable"] is False for row in rows)
    assert all(row["quality"]["dimension_set"] == "none" for row in rows)
    assert all(row["asr_recognizability"]["status"] == "proxy" for row in rows)
    assert str(audio) not in str(artifact)
    assert _validate_segment_quality_artifact(rows)[0]["acoustic_usable"] is False
