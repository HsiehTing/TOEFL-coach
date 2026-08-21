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
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "mlx-community/whisper-small-mlx"
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
    transcriber = backend or _load_default_backend()
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
