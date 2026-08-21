"""Orchestrate local ASR and TOEFL Speaking role mapping."""

from __future__ import annotations

import subprocess
from pathlib import Path
from collections.abc import Callable, Mapping, Sequence
from math import isfinite

from toefl_tracker.audio import AudioInspectionError, inspect_segment_quality
from toefl_tracker.quality import quality_decision
from toefl_tracker.role_mapping import (
    infer_toefl_role_map_from_asr,
    infer_toefl_role_map_from_single_item_asr,
)
from toefl_tracker.transcription import Backend, transcribe_audio


def _mapping_rows(mapping: Mapping[str, object]) -> list[dict[str, object]]:
    rows = mapping.get("rows")
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValueError("speaking mapping must contain rows")
    result = [dict(row) for row in rows if isinstance(row, Mapping)]
    if len(result) != len(rows):
        raise ValueError("speaking mapping rows are invalid")
    return result


def _asr_overlaps(
    row: Mapping[str, object], transcript_segments: Sequence[Mapping[str, object]]
) -> list[Mapping[str, object]]:
    start, end = row.get("start"), row.get("end")
    if type(start) not in {int, float} or type(end) not in {int, float}:
        raise ValueError("speaking mapping boundaries are invalid")
    return [
        segment
        for segment in transcript_segments
        if isinstance(segment, Mapping)
        and type(segment.get("start")) in {int, float}
        and type(segment.get("end")) in {int, float}
        and float(segment["start"]) < float(end)
        and float(segment["end"]) > float(start)
    ]


def _asr_proxy(
    row: Mapping[str, object], transcript_segments: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    overlaps = _asr_overlaps(row, transcript_segments)
    logprobs = [
        float(segment["avg_logprob"])
        for segment in overlaps
        if type(segment.get("avg_logprob")) in {int, float}
        and isfinite(float(segment["avg_logprob"]))
    ]
    no_speech = [
        float(segment["no_speech_prob"])
        for segment in overlaps
        if type(segment.get("no_speech_prob")) in {int, float}
        and isfinite(float(segment["no_speech_prob"]))
    ]
    proxy: dict[str, object] = {
        "status": "proxy" if overlaps else "unavailable",
        "overlap_segment_count": len(overlaps),
    }
    if logprobs:
        proxy["avg_logprob"] = round(sum(logprobs) / len(logprobs), 6)
    if no_speech:
        proxy["max_no_speech_prob"] = round(max(no_speech), 6)
    return proxy


def build_segment_quality_artifact(
    path: Path,
    mapping: Mapping[str, object],
    transcript: Mapping[str, object],
    *,
    runner: Callable = subprocess.run,
    ffmpeg: str = "ffmpeg",
) -> list[dict[str, object]]:
    """Build path-free quality/usability rows for learner ASR turns.

    ``acoustic_usable`` is only a technical recording-quality signal.  It does
    not establish pronunciation, prosody, fluency, or intelligibility evidence.
    """
    rows = _mapping_rows(mapping)
    learner_rows = [row for row in rows if row.get("role") == "learner"]
    if not learner_rows:
        raise ValueError("speaking mapping has no learner rows")
    raw_segments = transcript.get("segments") if isinstance(transcript, Mapping) else None
    if isinstance(raw_segments, (str, bytes)) or not isinstance(raw_segments, Sequence):
        raise ValueError("speaking transcript must contain segments")
    transcript_segments = [row for row in raw_segments if isinstance(row, Mapping)]
    if len(transcript_segments) != len(raw_segments):
        raise ValueError("speaking transcript segments are invalid")
    task_type = mapping.get("task_type")
    if task_type == "listen_and_repeat":
        reliable_dimensions = ["content", "grammar", "reconstruction", "vocabulary"]
    elif task_type == "take_an_interview":
        reliable_dimensions = ["content", "grammar", "vocabulary"]
    else:
        raise ValueError("speaking mapping task type is invalid")
    try:
        measured = inspect_segment_quality(
            path,
            [
                {"start": row["start"], "end": row["end"]}
                for row in learner_rows
            ],
            runner=runner,
            ffmpeg=ffmpeg,
        )
    except AudioInspectionError:
        raise
    if len(measured) != len(learner_rows):
        raise ValueError("segment quality count does not match learner rows")
    result: list[dict[str, object]] = []
    for row, metrics in zip(learner_rows, measured):
        decision = quality_decision({**metrics, "decodable": True})
        quality = {
            "policy_version": decision.policy_version,
            "standard_basis": decision.standard_basis,
            "usable": decision.usable,
            "dimension_set": decision.dimension_set,
        }
        text = row.get("text")
        text_usable = isinstance(text, str) and bool(text.strip())
        result.append({
            "segment_id": row.get("segment_id"),
            "start": metrics["start"],
            "end": metrics["end"],
            "mean_dbfs": metrics["mean_dbfs"],
            "peak_dbfs": metrics["peak_dbfs"],
            "clipping": metrics["clipping"],
            "decodable": True,
            "quality": quality,
            "text_usable": text_usable,
            "acoustic_usable": quality["usable"] is True and quality["dimension_set"] == "all",
            "asr_recognizability": _asr_proxy(row, transcript_segments),
            # Formal audio-performance dimensions still require separately
            # persisted human observations; this starts as text-only evidence.
            "reliable_dimensions": reliable_dimensions,
        })
    return result


def prepare_speaking_session(
    path: Path,
    task_type: str,
    *,
    model: str | None = None,
    language: str = "en",
    backend: Backend | None = None,
    merge_gap_seconds: float = 0.15,
    include_segment_quality: bool = False,
    quality_runner: Callable = subprocess.run,
    ffmpeg: str = "ffmpeg",
) -> dict[str, object]:
    """Return a path-free transcript plus task-specific role mapping."""
    transcript = transcribe_audio(
        path,
        model=model,
        language=language,
        backend=backend,
    )
    mapping = infer_toefl_role_map_from_asr(
        task_type,
        transcript,
        merge_gap_seconds=merge_gap_seconds,
    )
    artifact: dict[str, object] = {
        "schema_version": 1,
        "task_type": task_type,
        "status": "needs_confirmation" if mapping.requires_confirmation else "ready_for_diagnostic",
        "transcript": transcript,
        "mapping": mapping.artifact(),
    }
    if include_segment_quality:
        artifact["segment_quality"] = build_segment_quality_artifact(
            path,
            artifact["mapping"],
            transcript,
            runner=quality_runner,
            ffmpeg=ffmpeg,
        )
    return artifact


def prepare_speaking_item_batch(
    paths: Sequence[Path],
    task_type: str,
    *,
    model: str | None = None,
    language: str = "en",
    backend: Backend | None = None,
    include_segment_quality: bool = False,
    quality_runner: Callable = subprocess.run,
    ffmpeg: str = "ffmpeg",
) -> dict[str, object]:
    """Prepare a batch where each local recording contains exactly one item.

    File order is the item order; every item is mapped independently so one
    weak or missing recording cannot shift the remaining items.
    """
    if isinstance(paths, (str, bytes)) or not isinstance(paths, Sequence) or not paths:
        raise ValueError("audio item paths are required")
    expected = 7 if task_type == "listen_and_repeat" else 4 if task_type == "take_an_interview" else 0
    if expected == 0:
        raise ValueError("unknown speaking task")
    if len(paths) != expected:
        raise ValueError(f"expected exactly {expected} item recordings")
    items: list[dict[str, object]] = []
    all_ready = True
    for item_number, raw_path in enumerate(paths, start=1):
        path = Path(raw_path)
        transcript = transcribe_audio(path, model=model, language=language, backend=backend)
        mapping = infer_toefl_role_map_from_single_item_asr(
            task_type, transcript, item=item_number
        )
        item_artifact: dict[str, object] = {
            "item": item_number,
            "status": "needs_confirmation" if mapping.requires_confirmation else "ready_for_diagnostic",
            "transcript": transcript,
            "mapping": mapping.artifact(),
        }
        if include_segment_quality and mapping.rows:
            item_artifact["segment_quality"] = build_segment_quality_artifact(
                path,
                mapping.artifact(),
                transcript,
                runner=quality_runner,
                ffmpeg=ffmpeg,
            )
        all_ready = all_ready and not mapping.requires_confirmation
        items.append(item_artifact)
    return {
        "schema_version": 1,
        "task_type": task_type,
        "status": "ready_for_diagnostic" if all_ready else "needs_confirmation",
        "item_count": len(items),
        "items": items,
    }
