"""Local, path-free speech transcription for TOEFL Speaking audio.

The adapter deliberately owns transcription only.  TOEFL role mapping and
task-specific assessment consume the timestamped rows produced here; they do
not use speaker identity, voiceprints, or a cloud transcription service.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "mlx-community/whisper-small-mlx"
DEFAULT_CPP_MODEL = "ggml-small.en.bin"
SCHEMA_VERSION = 1
_WHITESPACE = re.compile(r"\s+")


class TranscriptionError(RuntimeError):
    """Raised when local ASR cannot produce a valid transcript artifact."""


Backend = Callable[..., Mapping[str, Any]]


def _finite_float(value: object, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise TranscriptionError(f"invalid {field}") from error
    if not isfinite(parsed):
        raise TranscriptionError(f"invalid {field}")
    return parsed


def _clean_text(value: object, field: str = "text") -> str:
    if not isinstance(value, str):
        raise TranscriptionError(f"invalid {field}")
    text = _WHITESPACE.sub(" ", value).strip()
    if not text:
        raise TranscriptionError(f"empty {field}")
    return text


def _safe_model_identifier(model: str) -> str:
    """Return a provenance identifier without leaking an absolute model path."""
    if not isinstance(model, str) or not model.strip():
        raise TranscriptionError("model identifier is required")
    value = model.strip()
    if os.path.isabs(value):
        return Path(value).name
    return value


def _file_sha256(path: Path) -> str | None:
    """Hash a local model file when available; repositories have no local hash."""
    if not path.is_file():
        return None
    digest = sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise TranscriptionError("unable to read local model file") from error
    return "sha256:" + digest.hexdigest()


def _load_default_backend() -> Backend:
    try:
        module = importlib.import_module("mlx_whisper")
    except ModuleNotFoundError as error:
        raise TranscriptionError(
            "mlx-whisper is not installed; install the optional audio dependencies "
            "or provide an injected local backend"
        ) from error
    transcribe = getattr(module, "transcribe", None)
    if not callable(transcribe):
        raise TranscriptionError("mlx-whisper does not expose transcribe()")
    return transcribe


def _parse_timestamp(value: object, *, offset_is_milliseconds: bool = False) -> float:
    if type(value) in {int, float}:
        parsed = float(value)
        return parsed / 1000.0 if offset_is_milliseconds else parsed
    if not isinstance(value, str):
        raise TranscriptionError("whisper.cpp timestamp is invalid")
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})", value.strip())
    if not match:
        raise TranscriptionError("whisper.cpp timestamp is invalid")
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def _normalize_whisper_cpp_result(payload: Mapping[str, object]) -> Mapping[str, object]:
    result = payload.get("result") if isinstance(payload.get("result"), Mapping) else payload
    raw_segments = payload.get("transcription")
    if raw_segments is None and isinstance(result, Mapping):
        raw_segments = result.get("transcription")
    if raw_segments is None and isinstance(result, Mapping):
        raw_segments = result.get("segments")
    if not isinstance(raw_segments, Sequence) or isinstance(raw_segments, (str, bytes)):
        raise TranscriptionError("whisper.cpp returned no transcription segments")
    segments: list[dict[str, object]] = []
    for index, raw in enumerate(raw_segments, start=1):
        if not isinstance(raw, Mapping):
            continue
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        timestamps = raw.get("timestamps") if isinstance(raw.get("timestamps"), Mapping) else raw
        offsets = raw.get("offsets") if isinstance(raw.get("offsets"), Mapping) else None
        if isinstance(offsets, Mapping) and "from" in offsets and "to" in offsets:
            start = _parse_timestamp(offsets["from"], offset_is_milliseconds=True)
            end = _parse_timestamp(offsets["to"], offset_is_milliseconds=True)
        elif isinstance(timestamps, Mapping) and "from" in timestamps and "to" in timestamps:
            start = _parse_timestamp(timestamps["from"])
            end = _parse_timestamp(timestamps["to"])
        elif isinstance(raw.get("start"), (int, float)) and isinstance(raw.get("end"), (int, float)):
            start = _parse_timestamp(raw["start"])
            end = _parse_timestamp(raw["end"])
        else:
            raise TranscriptionError("whisper.cpp segment has no timestamps")
        segments.append({
            "id": raw.get("id", index - 1),
            "start": start,
            "end": end,
            "text": text,
        })
    if not segments:
        raise TranscriptionError("whisper.cpp returned an empty transcript")
    language = result.get("language") if isinstance(result, Mapping) else None
    if language is None:
        language = payload.get("language")
    normalized: dict[str, object] = {"segments": segments}
    if isinstance(language, str) and language.strip():
        normalized["language"] = language.strip()
    return normalized


def _cpp_model_path() -> Path | None:
    configured = os.environ.get("TOEFL_WHISPER_CPP_MODEL")
    candidates = [Path(configured)] if configured else []
    candidates.extend((
        Path.home() / ".cache/toefl/whisper.cpp" / DEFAULT_CPP_MODEL,
        Path("/opt/homebrew/share/whisper.cpp/models") / DEFAULT_CPP_MODEL,
    ))
    return next((path for path in candidates if path.is_file()), None)


def _transcribe_with_whisper_cpp(
    path: Path,
    *,
    language: str,
    model: str | None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[Mapping[str, object], str]:
    executable = shutil.which(os.environ.get("TOEFL_WHISPER_CPP_BIN", "whisper-cli"))
    if executable is None:
        raise TranscriptionError("Metal is unavailable and whisper.cpp (whisper-cli) is not installed")
    model_path = Path(model) if model and os.path.isabs(model) else _cpp_model_path()
    if model_path is None or not model_path.is_file():
        raise TranscriptionError(
            "Metal is unavailable; set TOEFL_WHISPER_CPP_MODEL to a local whisper.cpp model file"
        )
    with tempfile.TemporaryDirectory(prefix="toefl-whisper-cpp-") as directory:
        input_path = path
        if path.suffix.casefold() not in {".wav", ".mp3", ".flac", ".ogg"}:
            ffmpeg = shutil.which(os.environ.get("TOEFL_FFMPEG_BIN", "ffmpeg"))
            if ffmpeg is None:
                raise TranscriptionError("whisper.cpp fallback needs ffmpeg to decode this audio format")
            input_path = Path(directory) / "input.wav"
            try:
                converted = runner([
                    ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(path), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                    str(input_path),
                ], capture_output=True, text=True, check=False)
            except OSError as error:
                raise TranscriptionError(f"audio conversion for whisper.cpp failed: {error}") from error
            if converted.returncode != 0 or not input_path.is_file():
                detail = (converted.stderr or converted.stdout or "ffmpeg failed").strip()
                raise TranscriptionError(f"audio conversion for whisper.cpp failed: {detail}")
        output_base = Path(directory) / "transcript"
        command = [
            executable, "-m", str(model_path), "-f", str(input_path),
            "-l", language, "-ojf", "-of", str(output_base),
            "-np", "-ng",
        ]
        try:
            completed = runner(command, capture_output=True, text=True, check=False)
        except OSError as error:
            raise TranscriptionError(f"whisper.cpp fallback failed: {error}") from error
        output_text = (completed.stderr or "") + "\n" + (completed.stdout or "")
        if completed.returncode != 0 or "failed to read audio file" in output_text.casefold():
            detail = (completed.stderr or completed.stdout or "whisper.cpp failed").strip()
            raise TranscriptionError(f"whisper.cpp fallback failed: {detail}")
        json_path = output_base.with_suffix(".json")
        if not json_path.is_file():
            raise TranscriptionError("whisper.cpp fallback produced no JSON transcript")
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise TranscriptionError("whisper.cpp fallback produced invalid JSON") from error
    if not isinstance(payload, Mapping):
        raise TranscriptionError("whisper.cpp fallback returned an invalid artifact")
    return _normalize_whisper_cpp_result(payload), str(model_path)


def _word_artifact(word: Mapping[str, Any], number: int) -> dict[str, object]:
    text = _clean_text(word.get("word"), f"word {number} text")
    start = _finite_float(word.get("start"), f"word {number} start")
    end = _finite_float(word.get("end"), f"word {number} end")
    if start < 0 or end <= start:
        raise TranscriptionError(f"invalid word {number} boundaries")
    artifact: dict[str, object] = {"word": text, "start": start, "end": end}
    if "probability" in word and word["probability"] is not None:
        probability = _finite_float(word["probability"], f"word {number} probability")
        if not 0.0 <= probability <= 1.0:
            raise TranscriptionError(f"invalid word {number} probability")
        artifact["probability"] = probability
    return artifact


def _segment_artifact(segment: Mapping[str, Any], number: int) -> dict[str, object]:
    text = _clean_text(segment.get("text"), f"segment {number} text")
    start = _finite_float(segment.get("start"), f"segment {number} start")
    end = _finite_float(segment.get("end"), f"segment {number} end")
    if start < 0 or end <= start:
        raise TranscriptionError(f"invalid segment {number} boundaries")

    artifact: dict[str, object] = {
        "segment_id": str(segment.get("id", f"asr-{number:03d}")),
        "start": start,
        "end": end,
        "text": text,
    }
    for field in ("avg_logprob", "no_speech_prob", "temperature"):
        if field in segment and segment[field] is not None:
            artifact[field] = _finite_float(segment[field], f"segment {number} {field}")

    words = segment.get("words")
    if words is not None:
        if isinstance(words, (str, bytes)) or not isinstance(words, Sequence):
            raise TranscriptionError(f"invalid segment {number} words")
        normalized_words: list[dict[str, object]] = []
        invalid_word_count = 0
        for index, word in enumerate(words, start=1):
            if not isinstance(word, Mapping):
                raise TranscriptionError(f"invalid segment {number} word entry")
            try:
                normalized_words.append(_word_artifact(word, index))
            except TranscriptionError:
                # Whisper can emit an isolated zero-length word at a segment
                # boundary. Keep the validated segment text and disclose that
                # word-level alignment is partial instead of discarding the
                # whole recording.
                invalid_word_count += 1
        artifact["words"] = normalized_words
        if invalid_word_count:
            artifact["word_timestamp_quality"] = "partial"
            artifact["invalid_word_count"] = invalid_word_count
    return artifact


def normalize_transcription(
    result: Mapping[str, Any],
    *,
    source: Path,
    backend: str,
    model: str,
) -> dict[str, object]:
    """Validate and normalize a backend result into the project ASR schema."""
    if not isinstance(result, Mapping):
        raise TranscriptionError("transcription backend returned a non-mapping")
    raw_segments = result.get("segments")
    if isinstance(raw_segments, (str, bytes)) or not isinstance(raw_segments, Sequence):
        raise TranscriptionError("transcription backend returned no segments")

    segments: list[dict[str, object]] = []
    previous_end = 0.0
    for number, raw_segment in enumerate(raw_segments, start=1):
        if not isinstance(raw_segment, Mapping):
            raise TranscriptionError(f"invalid segment {number}")
        segment = _segment_artifact(raw_segment, number)
        if float(segment["start"]) < previous_end:
            raise TranscriptionError("transcription segments overlap or are unordered")
        previous_end = float(segment["end"])
        segments.append(segment)
    if not segments:
        raise TranscriptionError("transcription backend returned an empty transcript")

    model_identifier = _safe_model_identifier(model)
    artifact: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "transcript_end_seconds": previous_end,
        "backend": backend,
        "model_identifier": model_identifier,
        "segments": segments,
    }
    language = result.get("language")
    if language is not None:
        artifact["language"] = _clean_text(language, "language")
    model_hash = _file_sha256(Path(model)) if os.path.isabs(model) else None
    if model_hash is not None:
        artifact["model_sha256"] = model_hash
    # The source path is intentionally not included in the persisted artifact.
    del source
    return artifact


def transcribe_audio(
    path: Path,
    *,
    model: str | None = None,
    language: str = "en",
    backend: Backend | None = None,
) -> dict[str, object]:
    """Transcribe one local audio file with a lazy, injectable local backend."""
    if not isinstance(path, Path):
        path = Path(path)
    if not path.is_file():
        raise TranscriptionError(f"audio file not found: {path}")
    selected_model = model or os.environ.get("TOEFL_WHISPER_MODEL") or DEFAULT_MODEL
    model_identifier = _safe_model_identifier(selected_model)
    selected_language = _clean_text(language, "language")
    requested_backend = os.environ.get("TOEFL_WHISPER_BACKEND", "auto").strip().casefold()
    if requested_backend not in {"auto", "mlx_whisper", "whisper_cpp"}:
        raise TranscriptionError("TOEFL_WHISPER_BACKEND must be auto, mlx_whisper, or whisper_cpp")
    if backend is None and requested_backend == "whisper_cpp":
        cpp_result, cpp_model = _transcribe_with_whisper_cpp(
            path,
            language=selected_language,
            model=selected_model if os.path.isabs(selected_model) else None,
        )
        return normalize_transcription(
            cpp_result,
            source=path,
            backend="whisper_cpp",
            model=cpp_model,
        )
    try:
        transcriber = backend or _load_default_backend()
    except TranscriptionError as error:
        if backend is None and requested_backend == "auto" and "not installed" in str(error).casefold():
            cpp_result, cpp_model = _transcribe_with_whisper_cpp(
                path,
                language=selected_language,
                model=None,
            )
            return normalize_transcription(
                cpp_result,
                source=path,
                backend="whisper_cpp",
                model=cpp_model,
            )
        raise
    try:
        result = transcriber(
            str(path),
            path_or_hf_repo=selected_model,
            language=selected_language,
            word_timestamps=True,
            condition_on_previous_text=False,
            verbose=False,
        )
    except TranscriptionError:
        raise
    except (OSError, RuntimeError, ValueError, TypeError) as error:
        error_text = str(error).casefold()
        metal_unavailable = "metal" in error_text and (
            "no metal device" in error_text or "metal device" in error_text
        )
        if backend is None and requested_backend == "auto" and metal_unavailable:
            cpp_result, cpp_model = _transcribe_with_whisper_cpp(
                path,
                language=selected_language,
                model=None,
            )
            return normalize_transcription(
                cpp_result,
                source=path,
                backend="whisper_cpp",
                model=cpp_model,
            )
        raise TranscriptionError(f"local transcription failed: {error}") from error
    return normalize_transcription(
        result,
        source=path,
        backend="mlx_whisper",
        model=selected_model,
    )


def dump_transcription(artifact: Mapping[str, object], output: Path | None = None) -> None:
    payload = json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        print(payload, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
