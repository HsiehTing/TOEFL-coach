import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from toefl_tracker.audio import AudioInspectionError


DEFAULT_MODEL_PATH = Path(
    "/Users/twinb00599242/Library/Application Support/TOEFL/models/ggml-small.en.bin"
)
_MODEL_BASENAME = "ggml-small.en.bin"
_AUDIO_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".mp4", ".ogg", ".wav"}


@dataclass(frozen=True)
class AudioDependencies:
    ffmpeg: str
    ffprobe: str
    whisper_cli: str
    model_path: Path
    tool_versions: Mapping[str, str]

    @property
    def provenance(self) -> dict[str, object]:
        """Safe, persistable provenance: never includes local absolute paths."""
        return {
            "executables": dict(self.tool_versions),
            "model_identifier": self.model_path.name,
        }


def _tool_version(executable: str, runner: Callable) -> str:
    try:
        result = runner([executable, "--version"], capture_output=True, text=True, check=False)
    except OSError:
        return "unavailable"
    output = (result.stdout or result.stderr).strip().splitlines()
    if not output:
        return "unavailable"
    return output[0]


def preflight_audio_tools(
    model_path: Path | str | None = None,
    *,
    which: Callable[[str], str | None] = shutil.which,
    environ: Mapping[str, str] | None = None,
    repository_root: Path | None = None,
    runner: Callable = subprocess.run,
) -> AudioDependencies:
    """Reject unavailable local-only dependencies before an audio file is read."""
    environment = os.environ if environ is None else environ
    paths: dict[str, str] = {}
    for executable in ("ffmpeg", "ffprobe", "whisper-cli"):
        located = which(executable)
        if not located:
            raise AudioInspectionError(
                f"{executable} is required; install local ffmpeg and whisper-cpp before transcription"
            )
        paths[executable] = located

    configured_model = model_path if model_path is not None else environment.get("TOEFL_WHISPER_MODEL")
    if not configured_model:
        configured_model = DEFAULT_MODEL_PATH
    model = Path(configured_model).expanduser().resolve()
    if model.name != _MODEL_BASENAME:
        raise AudioInspectionError(f"model must be named {_MODEL_BASENAME}")
    if not model.is_file():
        raise AudioInspectionError(f"model is missing: {_MODEL_BASENAME}")
    root = (repository_root or Path.cwd()).resolve()
    if model.is_relative_to(root):
        raise AudioInspectionError("model must be stored outside the repository")

    return AudioDependencies(
        ffmpeg=paths["ffmpeg"],
        ffprobe=paths["ffprobe"],
        whisper_cli=paths["whisper-cli"],
        model_path=model,
        tool_versions={name: _tool_version(path, runner) for name, path in paths.items()},
    )


def _run(runner: Callable, command: list[str]) -> None:
    try:
        result = runner(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise AudioInspectionError(f"{Path(command[0]).name} unavailable: {error}") from error
    if result.returncode != 0:
        raise AudioInspectionError(result.stderr.strip() or f"{Path(command[0]).name} failed")


def _parse_segments(path: Path) -> list[dict[str, float | str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_rows = payload["transcription"]
        if not isinstance(source_rows, list):
            raise ValueError
        rows: list[dict[str, float | str]] = []
        previous_end = 0.0
        for segment in source_rows:
            offsets = segment["offsets"]
            start = float(offsets["from"]) / 1000
            end = float(offsets["to"]) / 1000
            text = segment["text"].strip()
            if (
                not isfinite(start) or not isfinite(end) or start < previous_end
                or start < 0 or end <= start or not text
            ):
                raise ValueError
            rows.append({"start": start, "end": end, "text": text})
            previous_end = end
        return rows
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AudioInspectionError("invalid whisper JSON segments") from error


def transcribe_audio(
    path: Path,
    dependencies: AudioDependencies,
    runner: Callable = subprocess.run,
) -> list[dict[str, float | str]]:
    """Run strictly local normalization and transcription; no upload is possible here."""
    if not isinstance(path, Path) or not path.is_file():
        raise AudioInspectionError("audio file not found")
    if path.suffix.lower() not in _AUDIO_SUFFIXES:
        raise AudioInspectionError(f"unsupported audio format: {path.suffix or 'no extension'}")
    if not isinstance(dependencies, AudioDependencies):
        raise AudioInspectionError("audio dependencies must be preflighted")

    with tempfile.TemporaryDirectory(prefix="toefl-transcription-") as temporary:
        temporary_path = Path(temporary)
        wav_path = temporary_path / "normalized.wav"
        output_prefix = temporary_path / "output"
        _run(runner, [
            dependencies.ffmpeg, "-nostdin", "-y", "-i", str(path), "-ar", "16000", "-ac", "1",
            "-c:a", "pcm_s16le", str(wav_path),
        ])
        _run(runner, [
            dependencies.whisper_cli, "-m", str(dependencies.model_path), "-f", str(wav_path),
            "-oj", "-of", str(output_prefix),
        ])
        return _parse_segments(output_prefix.with_suffix(".json"))
