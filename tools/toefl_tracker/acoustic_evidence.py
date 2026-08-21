"""Conservative, path-free acoustic proxies and text/audio fusion for Speaking."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from math import isfinite
from pathlib import Path

from toefl_tracker.audio import AudioInspectionError


_TOKEN = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
_SILENCE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


def _rows(mapping: Mapping[str, object]) -> list[dict[str, object]]:
    rows = mapping.get("rows")
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValueError("speaking mapping must contain rows")
    result = [dict(row) for row in rows if isinstance(row, Mapping)]
    if len(result) != len(rows):
        raise ValueError("speaking mapping rows are invalid")
    return result


def _parse_silences(output: str, duration: float) -> tuple[int, float]:
    starts: list[float] = []
    pauses: list[float] = []
    for line in output.splitlines():
        start_match = _SILENCE_START.search(line)
        if start_match:
            starts.append(float(start_match.group(1)))
        end_match = _SILENCE_END.search(line)
        if end_match and starts:
            start = starts.pop(0)
            end = float(end_match.group(1))
            pauses.append(max(0.0, min(duration, end) - max(0.0, start)))
    return len(pauses), round(sum(pauses), 3)


def _run_silencedetect(
    path: Path,
    start: float,
    duration: float,
    *,
    runner: Callable = subprocess.run,
    ffmpeg: str = "ffmpeg",
) -> tuple[int, float]:
    try:
        result = runner([
            ffmpeg, "-nostdin", "-hide_banner", "-ss", str(start), "-t", str(duration),
            "-i", str(path), "-af", "silencedetect=noise=-35dB:d=0.25", "-f", "null", "-",
        ], capture_output=True, text=True, check=False)
    except OSError as error:
        raise AudioInspectionError(f"{ffmpeg} unavailable: {error}") from error
    if result.returncode != 0:
        raise AudioInspectionError(result.stderr.strip() or f"{ffmpeg} failed")
    return _parse_silences(result.stderr + "\n" + result.stdout, duration)


def build_acoustic_evidence(
    path: Path,
    mapping: Mapping[str, object],
    transcript: Mapping[str, object],
    *,
    runner: Callable = subprocess.run,
    ffmpeg: str = "ffmpeg",
) -> list[dict[str, object]]:
    """Return segment-scoped speech-dynamics proxies without audio claims.

    Speech rate and pauses are bounded diagnostic proxies.  Pronunciation,
    prosody, and intelligibility remain unavailable until a dedicated validated
    acoustic evaluator exists; ASR recognizability is never promoted to those
    dimensions.
    """
    mapping_rows = _rows(mapping)
    learner_rows = [row for row in mapping_rows if row.get("role") == "learner"]
    raw_segments = transcript.get("segments") if isinstance(transcript, Mapping) else None
    if isinstance(raw_segments, (str, bytes)) or not isinstance(raw_segments, Sequence):
        raise ValueError("speaking transcript must contain segments")
    by_id = {
        str(row.get("segment_id", row.get("id"))): row
        for row in raw_segments
        if isinstance(row, Mapping)
    }
    evidence: list[dict[str, object]] = []
    for row in learner_rows:
        try:
            start = float(row["start"])
            end = float(row["end"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("learner mapping boundaries are invalid") from error
        duration = end - start
        if start < 0 or not isfinite(start) or not isfinite(end) or duration <= 0:
            raise ValueError("learner mapping boundaries are invalid")
        segment = by_id.get(str(row.get("segment_id")), row)
        words = segment.get("words") if isinstance(segment, Mapping) else None
        if isinstance(words, Sequence) and not isinstance(words, (str, bytes)):
            word_count = sum(
                isinstance(word, Mapping) and isinstance(word.get("word"), str)
                for word in words
            )
        else:
            word_count = len(_TOKEN.findall(str(row.get("text", ""))))
        pause_count, pause_seconds = _run_silencedetect(
            path, start, duration, runner=runner, ffmpeg=ffmpeg
        )
        speech_seconds = max(0.001, duration - pause_seconds)
        evidence.append({
            "segment_id": row.get("segment_id"),
            "start": start,
            "end": end,
            "word_count": word_count,
            "speech_rate_wpm": round(word_count / speech_seconds * 60.0, 1),
            "pause_count": pause_count,
            "pause_seconds": pause_seconds,
            "pause_ratio": round(min(1.0, pause_seconds / duration), 3),
            "evidence_status": "diagnostic_only",
            "dimensions": {
                "fluency": "proxy",
                "pronunciation": "unavailable",
                "prosody": "unavailable",
                "intelligibility": "unavailable",
            },
        })
    return evidence


def _tokens(text: object) -> set[str]:
    return set(_TOKEN.findall(str(text).casefold()))


def fuse_speaking_evidence(
    task_type: str,
    mapping: Mapping[str, object],
    segment_quality: Sequence[Mapping[str, object]],
    acoustic_evidence: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Join text evidence and acoustic proxies without inventing scores."""
    mapping_rows = _rows(mapping)
    quality_by_id = {
        str(row.get("segment_id")): row for row in segment_quality if isinstance(row, Mapping)
    }
    acoustic_by_id = {
        str(row.get("segment_id")): row for row in acoustic_evidence if isinstance(row, Mapping)
    }
    examiner_by_item = {
        row.get("item"): row for row in mapping_rows if row.get("role") == "examiner"
    }
    learner_by_item = {
        row.get("item"): row for row in mapping_rows if row.get("role") == "learner"
    }
    items: list[dict[str, object]] = []
    for item in sorted(learner_by_item):
        learner = learner_by_item[item]
        examiner = examiner_by_item.get(item, {})
        segment_id = str(learner.get("segment_id"))
        text_result: dict[str, object] = {
            "status": "usable" if learner.get("text") else "unavailable",
        }
        if task_type == "listen_and_repeat":
            source_tokens = _tokens(examiner.get("text"))
            learner_tokens = _tokens(learner.get("text"))
            union = source_tokens | learner_tokens
            text_result["reconstruction_similarity"] = round(
                len(source_tokens & learner_tokens) / len(union), 3
            ) if union else 0.0
        quality = quality_by_id.get(segment_id, {})
        acoustic = acoustic_by_id.get(segment_id, {})
        items.append({
            "item": item,
            "segment_id": segment_id,
            "text": text_result,
            "technical_audio": {
                "text_usable": quality.get("text_usable"),
                "acoustic_usable": quality.get("acoustic_usable"),
            },
            "acoustic": dict(acoustic),
            "conclusion": "text evidence plus fluency proxy; pronunciation, prosody, and intelligibility unavailable",
        })
    return {
        "result_type": "diagnostic_only",
        "task_type": task_type,
        "items": items,
        "limitations": [
            "Speech rate and pause metrics are diagnostic proxies, not TOEFL scores.",
            "Pronunciation, prosody, and intelligibility are unavailable without a validated acoustic evaluator.",
            "ASR recognizability is not phoneme-level pronunciation evidence.",
        ],
    }
