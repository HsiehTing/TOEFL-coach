import json
from pathlib import Path

import pytest

from toefl_tracker.transcription import (
    TranscriptionError,
    dump_transcription,
    normalize_transcription,
    transcribe_audio,
)


def backend_result() -> dict:
    return {
        "language": "en",
        "segments": [
            {
                "id": 3,
                "start": 1.0,
                "end": 2.5,
                "text": "  Welcome   to the park. ",
                "avg_logprob": -0.2,
                "no_speech_prob": 0.01,
                "words": [
                    {"word": " Welcome", "start": 1.0, "end": 1.4, "probability": 0.99},
                    {"word": " to", "start": 1.4, "end": 1.6, "probability": 0.98},
                    {"word": " the park.", "start": 1.6, "end": 2.5, "probability": 0.97},
                ],
            },
        ],
    }


def test_normalize_transcription_is_path_free_and_preserves_timestamps(tmp_path: Path) -> None:
    source = tmp_path / "private.m4a"
    artifact = normalize_transcription(
        backend_result(),
        source=source,
        backend="mlx_whisper",
        model="/private/models/ggml-small.en.bin",
    )

    assert artifact["schema_version"] == 1
    assert "source" not in artifact
    assert "private.m4a" not in json.dumps(artifact)
    assert artifact["model_identifier"] == "ggml-small.en.bin"
    assert artifact["language"] == "en"
    assert artifact["segments"] == [
        {
            "segment_id": "3",
            "start": 1.0,
            "end": 2.5,
            "text": "Welcome to the park.",
            "avg_logprob": -0.2,
            "no_speech_prob": 0.01,
            "words": [
                {"word": "Welcome", "start": 1.0, "end": 1.4, "probability": 0.99},
                {"word": "to", "start": 1.4, "end": 1.6, "probability": 0.98},
                {"word": "the park.", "start": 1.6, "end": 2.5, "probability": 0.97},
            ],
        }
    ]


def test_normalize_transcription_keeps_segment_when_one_word_timestamp_is_invalid(tmp_path: Path) -> None:
    artifact = normalize_transcription(
        {
            "segments": [{
                "start": 0.0,
                "end": 1.0,
                "text": "Hello world",
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.4},
                    {"word": "world", "start": 0.8, "end": 0.8},
                ],
            }]
        },
        source=tmp_path / "private.m4a",
        backend="mlx_whisper",
        model="test-model",
    )

    assert artifact["segments"][0]["text"] == "Hello world"
    assert artifact["segments"][0]["words"] == [
        {"word": "Hello", "start": 0.0, "end": 0.4}
    ]
    assert artifact["segments"][0]["word_timestamp_quality"] == "partial"
    assert artifact["segments"][0]["invalid_word_count"] == 1


def test_transcribe_audio_uses_injected_local_backend(tmp_path: Path) -> None:
    source = tmp_path / "sample.m4a"
    source.write_bytes(b"fixture")
    calls: list[dict] = []

    def fake_backend(*args: object, **kwargs: object) -> dict:
        calls.append({"args": args, "kwargs": kwargs})
        return backend_result()

    result = transcribe_audio(source, model="test-model", backend=fake_backend)

    assert result["backend"] == "mlx_whisper"
    assert calls[0]["args"] == (str(source),)
    assert calls[0]["kwargs"] == {
        "path_or_hf_repo": "test-model",
        "language": "en",
        "word_timestamps": True,
        "condition_on_previous_text": False,
        "verbose": False,
    }


def test_transcribe_audio_records_hash_for_local_model_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.m4a"
    source.write_bytes(b"fixture")
    model = tmp_path / "ggml-small.en.bin"
    model.write_bytes(b"local model fixture")

    result = transcribe_audio(source, model=str(model), backend=lambda *_, **__: backend_result())

    assert result["model_identifier"] == model.name
    assert result["model_sha256"].startswith("sha256:")


def test_transcribe_audio_rejects_missing_file() -> None:
    with pytest.raises(TranscriptionError, match="audio file not found"):
        transcribe_audio(Path("/does/not/exist.m4a"), backend=lambda **_: backend_result())


@pytest.mark.parametrize(
    "result, message",
    [
        ({"segments": []}, "empty transcript"),
        ({"segments": [{"start": 0, "end": 1, "text": "ok"}, {"start": 0.5, "end": 2, "text": "overlap"}]}, "overlap"),
        ({"segments": [{"start": 0, "end": 1, "text": "ok", "words": "bad"}]}, "words"),
    ],
)
def test_normalize_transcription_rejects_invalid_backend_results(result: dict, message: str, tmp_path: Path) -> None:
    with pytest.raises(TranscriptionError, match=message):
        normalize_transcription(result, source=tmp_path / "a.m4a", backend="mlx_whisper", model="model")


def test_dump_transcription_writes_only_requested_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    artifact = {"schema_version": 1, "segments": [{"text": "Hello"}]}
    output = tmp_path / "nested" / "transcript.json"
    dump_transcription(artifact, output)
    assert json.loads(output.read_text(encoding="utf-8")) == artifact
    assert capsys.readouterr().out == ""
