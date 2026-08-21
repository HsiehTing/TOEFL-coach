"""Deterministic, route-specific Speaking audio usability feedback."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite


_USABILITY_FIELDS = {"text_usable", "acoustic_usable", "asr_recognizability"}
_TASK_LABELS = {
    "listen_and_repeat": "Listen and Repeat",
    "take_an_interview": "Take an Interview",
}


def _timestamp(seconds: object) -> str:
    if type(seconds) not in {int, float} or not isfinite(float(seconds)) or float(seconds) < 0:
        raise ValueError("segment timestamp is invalid")
    total = int(float(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def _rows(
    task_type: str,
    segment_quality: Sequence[Mapping[str, object]],
    mapping_rows: Sequence[Mapping[str, object]] | None,
) -> list[dict[str, object]]:
    if task_type not in _TASK_LABELS:
        raise ValueError("unknown speaking task")
    if isinstance(segment_quality, (str, bytes)) or not isinstance(segment_quality, Sequence):
        raise ValueError("segment quality must be a sequence")
    quality_rows = [dict(row) for row in segment_quality if isinstance(row, Mapping)]
    if len(quality_rows) != len(segment_quality) or not quality_rows:
        raise ValueError("segment quality rows are invalid")
    if any(not _USABILITY_FIELDS <= set(row) for row in quality_rows):
        raise ValueError("segment usability fields are missing")
    item_by_id: dict[str, int] = {}
    if mapping_rows is not None:
        for row in mapping_rows:
            if not isinstance(row, Mapping) or row.get("role") != "learner":
                continue
            segment_id = row.get("segment_id")
            item = row.get("item")
            if isinstance(segment_id, str) and type(item) is int:
                item_by_id[segment_id] = item
    result: list[dict[str, object]] = []
    for index, row in enumerate(quality_rows, start=1):
        segment_id = row.get("segment_id")
        start, end = row.get("start"), row.get("end")
        if not isinstance(segment_id, str) or not segment_id.strip():
            raise ValueError("segment quality segment_id is invalid")
        if type(start) not in {int, float} or type(end) not in {int, float}:
            raise ValueError("segment quality boundaries are invalid")
        if float(start) < 0 or float(end) <= float(start):
            raise ValueError("segment quality boundaries are invalid")
        result.append({
            **row,
            "item": item_by_id.get(segment_id, index),
            "timestamp": f"{_timestamp(start)}–{_timestamp(end)}",
        })
    return result


def render_segment_usability_feedback(
    task_type: str,
    segment_quality: Sequence[Mapping[str, object]],
    mapping_rows: Sequence[Mapping[str, object]] | None = None,
) -> str:
    """Render the fixed diagnostic block required for ASR-backed feedback."""
    rows = _rows(task_type, segment_quality, mapping_rows)
    text_count = sum(row["text_usable"] is True for row in rows)
    acoustic_count = sum(row["acoustic_usable"] is True for row in rows)
    lines = [
        "## Segment usability (diagnostic only)",
        f"Route: `{task_type}` ({_TASK_LABELS[task_type]})",
        f"Text-usable learner turns: `{text_count}/{len(rows)}`",
        f"Acoustic-usable learner turns: `{acoustic_count}/{len(rows)}`",
        "ASR recognizability is a diagnostic proxy only; it is not phoneme-level proof or a TOEFL Speaking score.",
        "Per learner turn:",
    ]
    for row in rows:
        text_status = "text usable" if row["text_usable"] else "text unavailable"
        acoustic_status = "acoustic usable" if row["acoustic_usable"] else "acoustic limited"
        proxy = row["asr_recognizability"]
        proxy_status = proxy.get("status") if isinstance(proxy, Mapping) else "unavailable"
        overlap_count = proxy.get("overlap_segment_count", 0) if isinstance(proxy, Mapping) else 0
        lines.append(
            f"- {('Item' if task_type == 'listen_and_repeat' else 'Question')} {row['item']} "
            f"(`{row['segment_id']}`, {row['timestamp']}): {text_status}; {acoustic_status}; "
            f"ASR proxy `{proxy_status}` ({overlap_count} segment(s))."
        )
    if task_type == "listen_and_repeat":
        lines.append(
            "Route focus: text-usable turns may support source reconstruction; pronunciation, stress, rhythm, intonation, and intelligibility remain unavailable unless separately observed."
        )
    else:
        lines.append(
            "Route focus: text-usable turns may support directness, relevance, elaboration, coherence, grammar, and vocabulary; fluency, pronunciation, prosody, and intelligibility remain unavailable unless separately observed."
        )
    return "\n".join(lines)


def validate_segment_usability_feedback(
    task_type: str,
    feedback: str,
    segment_quality: Sequence[Mapping[str, object]],
    mapping_rows: Sequence[Mapping[str, object]] | None = None,
) -> None:
    """Require the deterministic block when segment usability is persisted."""
    if not isinstance(feedback, str):
        raise ValueError("speaking feedback is invalid")
    expected = render_segment_usability_feedback(task_type, segment_quality, mapping_rows)
    if feedback.count("## Segment usability (diagnostic only)") != 1 or expected not in feedback:
        raise ValueError("speaking feedback is missing the segment usability block")
