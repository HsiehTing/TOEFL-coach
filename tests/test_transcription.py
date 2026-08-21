import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from toefl_tracker.transcription import (
    TranscriptionError,
    dump_transcription,
    normalize_transcription,
    transcribe_audio,
)
import toefl_tracker.transcription as transcription_module


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


def test_transcribe_audio_falls_back_to_whisper_cpp_when_metal_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.m4a"
    source.write_bytes(b"fixture")
    monkeypatch.delenv("TOEFL_WHISPER_BACKEND", raising=False)
    monkeypatch.setattr(
        transcription_module,
        "_load_default_backend",
        lambda: lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("[metal::load_device] No Metal device available")
        ),
    )
    monkeypatch.setattr(
        transcription_module,
        "_transcribe_with_whisper_cpp",
        lambda *_args, **_kwargs: (
            {"segments": [{"start": 0.0, "end": 1.0, "text": "fallback transcript"}]},
            "/models/ggml-small.en.bin",
        ),
    )

    result = transcribe_audio(source, model="test-model")

    assert result["backend"] == "whisper_cpp"
    assert result["model_identifier"] == "ggml-small.en.bin"
    assert result["segments"][0]["text"] == "fallback transcript"


def test_normalize_whisper_cpp_json_supports_timestamped_transcription() -> None:
    result = transcription_module._normalize_whisper_cpp_result({
        "result": {
            "language": "en",
            "transcription": [{
                "id": 0,
                "timestamps": {"from": "00:00:01,000", "to": "00:00:02,500"},
                "text": " fallback transcript ",
            }],
        }
    })

    assert result == {
        "language": "en",
        "segments": [{
            "id": 0,
            "start": 1.0,
            "end": 2.5,
            "text": " fallback transcript ",
        }],
    }


def test_whisper_cpp_fallback_converts_m4a_to_temporary_wav(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.m4a"
    source.write_bytes(b"fixture")
    model = tmp_path / "ggml-small.en.bin"
    model.write_bytes(b"model")
    calls: list[list[str]] = []

    def fake_runner(command: list[str], **_: object) -> CompletedProcess[str]:
        calls.append(command)
        if "ffmpeg" in command[0]:
            Path(command[-1]).write_bytes(b"wav")
        else:
            output_base = Path(command[command.index("-of") + 1])
            output_base.with_suffix(".json").write_text(
                json.dumps({
                    "result": {"language": "en"},
                    "transcription": [{
                        "timestamps": {"from": "00:00:00,000", "to": "00:00:01,000"},
                        "text": " fallback ",
                    }],
                }),
                encoding="utf-8",
            )
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(transcription_module.shutil, "which", lambda name: name)
    result, model_identifier = transcription_module._transcribe_with_whisper_cpp(
        source,
        language="en",
        model=str(model),
        runner=fake_runner,
    )

    assert model_identifier == str(model)
    assert result["segments"][0]["text"] == " fallback "
    assert len(calls) == 2
    assert calls[0][0] == "ffmpeg"
    assert calls[1][calls[1].index("-f") + 1].endswith("input.wav")
