import json
import sys
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from toefl_tracker.audio import AudioInspectionError, inspect_audio, inspect_segment_quality
from toefl_tracker.transcription import AudioDependencies


def runner_success(command: list[str], **kwargs: object) -> CompletedProcess[str]:
    if command[0] == "ffprobe":
        payload = {
            "format": {"duration": "12.50"},
            "streams": [{"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 1}],
        }
        return CompletedProcess(command, 0, json.dumps(payload), "")
    return CompletedProcess(
        command,
        0,
        "",
        "[Parsed_volumedetect_0] mean_volume: -30.0 dB\n"
        "[Parsed_volumedetect_0] max_volume: -5.4 dB\n",
    )


def test_inspection_parses_audio_facts_without_language_judgment(tmp_path: Path) -> None:
    path = tmp_path / "sample.m4a"
    path.write_bytes(b"fixture")
    result = inspect_audio(path, runner_success)
    assert result == {
        "duration_seconds": 12.5,
        "codec": "aac",
        "sample_rate_hz": 48000,
        "channels": 1,
        "mean_dbfs": -30.0,
        "peak_dbfs": -5.4,
        "clipping": False,
        "decodable": True,
    }
    assert "pronunciation" not in result


def test_missing_audio_stream_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.m4a"
    path.write_bytes(b"fixture")

    def no_audio(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(command, 0, '{"format": {}, "streams": []}', "")

    with pytest.raises(AudioInspectionError, match="audio stream"):
        inspect_audio(path, no_audio)


@pytest.mark.parametrize("payload", ["not json", "[]", '{"format": {}}'])
def test_malformed_ffprobe_payload_is_rejected(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "bad.m4a"
    path.write_bytes(b"fixture")

    def malformed(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(command, 0, payload, "")

    with pytest.raises(AudioInspectionError):
        inspect_audio(path, malformed)


def test_invalid_stream_metrics_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.m4a"
    path.write_bytes(b"fixture")

    def invalid_metrics(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        payload = {
            "format": {"duration": "zero"},
            "streams": [{"codec_type": "audio", "codec_name": "aac", "sample_rate": "none", "channels": 0}],
        }
        return CompletedProcess(command, 0, json.dumps(payload), "")

    with pytest.raises(AudioInspectionError, match="invalid audio metadata"):
        inspect_audio(path, invalid_metrics)


def test_missing_volume_metrics_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.m4a"
    path.write_bytes(b"fixture")

    def no_volume(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        if command[0] == "ffprobe":
            payload = {
                "format": {"duration": "1"},
                "streams": [{"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 1}],
            }
            return CompletedProcess(command, 0, json.dumps(payload), "")
        return CompletedProcess(command, 0, "", "no metrics")

    with pytest.raises(AudioInspectionError, match="volume metrics"):
        inspect_audio(path, no_volume)


def test_missing_ffprobe_binary_is_reported_as_inspection_error(tmp_path: Path) -> None:
    path = tmp_path / "sample.m4a"
    path.write_bytes(b"fixture")

    def unavailable(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        raise FileNotFoundError(command[0])

    with pytest.raises(AudioInspectionError, match="ffprobe"):
        inspect_audio(path, unavailable)


def test_segment_inspection_measures_each_requested_time_range(tmp_path: Path) -> None:
    path = tmp_path / "sample.m4a"
    path.write_bytes(b"fixture")
    commands: list[list[str]] = []

    def segment_runner(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        commands.append(command)
        return CompletedProcess(
            command,
            0,
            "",
            "[Parsed_volumedetect_0] mean_volume: -30.0 dB\n"
            "[Parsed_volumedetect_0] max_volume: -5.4 dB\n",
        )

    result = inspect_segment_quality(
        path,
        [{"start": 2.0, "end": 5.8}, {"start": 7.0, "end": 8.5}],
        runner=segment_runner,
    )

    assert result == [
        {"start": 2.0, "end": 5.8, "mean_dbfs": -30.0, "peak_dbfs": -5.4, "clipping": False},
        {"start": 7.0, "end": 8.5, "mean_dbfs": -30.0, "peak_dbfs": -5.4, "clipping": False},
    ]
    assert all(command[:7] == ["ffmpeg", "-nostdin", "-hide_banner", "-ss", command[4], "-t", command[6]] for command in commands)


def test_inspect_cli_preflight_prints_safe_tool_and_model_provenance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from inspect_audio import main

    model = tmp_path / "ggml-small.en.bin"
    model.write_bytes(b"fixture")
    dependencies = AudioDependencies(
        ffmpeg="/private/local/ffmpeg",
        ffprobe="/private/local/ffprobe",
        whisper_cli="/private/local/whisper-cli",
        model_path=model,
        tool_versions={"ffmpeg": "ffmpeg 7.0", "ffprobe": "ffprobe 7.0", "whisper-cli": "whisper 1.0"},
    )
    monkeypatch.setattr("inspect_audio.preflight_audio_tools", lambda: dependencies)
    monkeypatch.setattr(sys, "argv", ["inspect_audio.py", "--preflight"])

    assert main() == 0
    output = capsys.readouterr().out
    assert "ggml-small.en.bin" in output
    assert str(model) not in output
    assert "/private/local" not in output
