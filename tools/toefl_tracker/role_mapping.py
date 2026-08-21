"""Transcript-structure role inference for the two TOEFL Speaking tasks.

This module deliberately never reads acoustic identity data.  It only accepts
chronological ASR rows and fails closed when their TOEFL turn structure cannot
prove which words belong to the learner.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite

from toefl_tracker.models import ValidationError


MAPPING_METHOD = "toefl_transcript_structure"
MAPPING_VERSION = 1
ITEM_COUNTS = {"listen_and_repeat": 7, "take_an_interview": 4}
_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")


@dataclass(frozen=True)
class RoleMapRow:
    segment_id: str
    item: int
    role: str
    start: float
    end: float
    text: str
    confidence: str
    role_reason: str

    def artifact(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "item": self.item,
            "role": self.role,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "confidence": self.confidence,
            "role_reason": self.role_reason,
        }


@dataclass(frozen=True)
class AmbiguousRoleRow:
    item: int
    reason: str

    def artifact(self) -> dict[str, object]:
        return {"item": self.item, "reason": self.reason}


@dataclass(frozen=True)
class RoleMapResult:
    task_type: str
    rows: tuple[RoleMapRow, ...]
    ambiguous_rows: tuple[AmbiguousRoleRow, ...]
    requires_confirmation: bool
    reason: str
    source_transcript_hash: str
    mapping_method: str = MAPPING_METHOD
    mapping_version: int = MAPPING_VERSION

    def artifact(self) -> dict[str, object]:
        """Return the reviewable, path-free role-mapping artifact."""
        return {
            "schema_version": 1,
            "task_type": self.task_type,
            "source_transcript_hash": self.source_transcript_hash,
            "mapping_method": self.mapping_method,
            "mapping_version": self.mapping_version,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
            "rows": [row.artifact() for row in self.rows],
            "ambiguities": [row.artifact() for row in self.ambiguous_rows],
        }


@dataclass(frozen=True)
class _TranscriptRow:
    segment_id: str
    start: float
    end: float
    text: str


def _source_hash(rows: Sequence[_TranscriptRow]) -> str:
    payload = [
        {"segment_id": row.segment_id, "start": row.start, "end": row.end, "text": row.text}
        for row in rows
    ]
    return "sha256:" + sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _validate_rows(transcript_rows: Sequence[Mapping]) -> tuple[_TranscriptRow, ...]:
    if isinstance(transcript_rows, (str, bytes)) or not isinstance(transcript_rows, Sequence):
        raise ValidationError("transcript rows must be a sequence of mappings")
    result: list[_TranscriptRow] = []
    previous_end: float | None = None
    for number, source in enumerate(transcript_rows, start=1):
        if not isinstance(source, Mapping):
            raise ValidationError("transcript rows must be a sequence of mappings")
        if any(field in source for field in ("speaker", "speaker_id", "voice_id", "voiceprint")):
            raise ValidationError("transcript role mapping does not accept speaker identity data")
        start, end, text = source.get("start"), source.get("end"), source.get("text")
        if (
            type(start) not in {int, float}
            or type(end) not in {int, float}
            or not isfinite(start)
            or not isfinite(end)
            or start < 0
            or end <= start
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise ValidationError("transcript row is invalid")
        if previous_end is not None and start < previous_end:
            raise ValidationError("overlap in transcript rows")
        segment_id = source.get("segment_id", f"asr-{number:03d}")
        if not isinstance(segment_id, str) or not segment_id.strip():
            raise ValidationError("transcript segment_id is invalid")
        result.append(_TranscriptRow(segment_id, float(start), float(end), text.strip()))
        previous_end = float(end)
    return tuple(result)


def _asr_rows(transcript: Mapping | Sequence[Mapping]) -> tuple[_TranscriptRow, ...]:
    """Read either a normalized ASR artifact or its segment list."""
    if isinstance(transcript, Mapping):
        rows = transcript.get("segments")
    else:
        rows = transcript
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise ValidationError("ASR transcript must contain a segment sequence")
    return _validate_rows(rows)


def _merge_adjacent_rows(
    rows: Sequence[_TranscriptRow], *, max_gap_seconds: float
) -> tuple[_TranscriptRow, ...]:
    """Join only near-contiguous ASR fragments from one spoken turn."""
    if not isfinite(max_gap_seconds) or max_gap_seconds < 0:
        raise ValidationError("ASR merge gap is invalid")
    merged: list[_TranscriptRow] = []
    for row in rows:
        gap = row.start - merged[-1].end if merged else None
        if (
            merged
            # A zero-gap boundary can be a real source→learner turn change;
            # only merge fragments with a small positive pause.
            and gap is not None
            and 0.05 <= gap <= max_gap_seconds
            and (
                _similarity(merged[-1].text, row.text) >= 0.25
                or min(len(_tokens(merged[-1].text)), len(_tokens(row.text))) <= 3
            )
        ):
            previous = merged[-1]
            merged[-1] = _TranscriptRow(
                segment_id=f"{previous.segment_id}+{row.segment_id}",
                start=previous.start,
                end=max(previous.end, row.end),
                text=f"{previous.text} {row.text}".strip(),
            )
        else:
            merged.append(row)
    return tuple(merged)


def _is_repeat_direction(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    return (
        normalized.startswith("repeat only once")
        or normalized.startswith("listen and repeat")
        or ("listen" in normalized and "repeat" in normalized)
    )


def _is_repeat_setup(text: str) -> bool:
    """Filter scenario narration before the seven sentence pairs."""
    normalized = " ".join(text.casefold().split())
    return normalized.startswith((
        "you are explaining ",
        "you are describing ",
        "in this task ",
        "in this scenario ",
    ))


def _is_interview_direction(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    return "interview" in normalized and not _question(normalized)


def _filter_directions(task_type: str, rows: Sequence[_TranscriptRow]) -> tuple[_TranscriptRow, ...]:
    if task_type == "listen_and_repeat":
        return tuple(
            row for row in rows
            if not _is_repeat_direction(row.text) and not _is_repeat_setup(row.text)
        )
    return tuple(row for row in rows if not _is_interview_direction(row.text))


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.casefold()))


def _similarity(first: str, second: str) -> float:
    first_tokens, second_tokens = _tokens(first), _tokens(second)
    if not first_tokens or not second_tokens:
        return 0.0
    return len(first_tokens & second_tokens) / len(first_tokens | second_tokens)


def _drop_near_duplicate_rows(
    rows: Sequence[_TranscriptRow], *, max_gap_seconds: float = 0.5
) -> tuple[_TranscriptRow, ...]:
    """Drop a short trailing ASR fragment that repeats the prior turn."""
    result: list[_TranscriptRow] = []
    for row in rows:
        if result:
            previous = result[-1]
            if (
                row.end - row.start <= 0.75
                and 0 <= row.start - previous.end <= max_gap_seconds
                and _similarity(previous.text, row.text) >= 0.8
            ):
                continue
        result.append(row)
    return tuple(result)


def _question(text: str) -> bool:
    return bool(re.match(
        r"^(?:what|why|how|who|where|when|which|describe|tell|do|does|did|can|could|would|will)\b",
        text.strip(),
        flags=re.IGNORECASE,
    )) or text.rstrip().endswith("?")


def _examiner_instruction(text: str) -> bool:
    """Reject examiner directions that merely look like an answer turn."""
    return bool(re.match(
        r"^(?:please\s+)?(?:answer|respond|describe|explain|give|tell)\b",
        text.strip(),
        flags=re.IGNORECASE,
    )) or bool(re.search(
        r"\b(?:answer|respond)\s+(?:this|the)\s+question\b|\bwith\s+(?:enough|more)\s+detail\b",
        text,
        flags=re.IGNORECASE,
    ))


def _answer_discourse_evidence(question: str, answer: str) -> bool:
    """Require a plausible response turn, not just a non-question sentence."""
    if _examiner_instruction(answer):
        return False
    answer_tokens = _tokens(answer)
    question_tokens = _tokens(question)
    if len(answer_tokens) < 4:
        return False
    # A response should either contain ordinary first-person/discourse material
    # or be materially developed relative to the prompt.
    discourse_markers = {
        "i", "me", "my", "mine", "we", "our", "because", "since",
        "although", "however", "also", "so", "if", "when", "while",
    }
    return bool(answer_tokens & discourse_markers) or len(answer_tokens) >= max(
        8, int(len(question_tokens) * 0.8)
    )


def _ambiguous(task_type: str, rows: Sequence[_TranscriptRow], reason: str, items: Sequence[int] | None = None) -> RoleMapResult:
    expected = ITEM_COUNTS.get(task_type, 0)
    affected = tuple(items if items is not None else range(1, expected + 1))
    return RoleMapResult(
        task_type=task_type,
        rows=(),
        ambiguous_rows=tuple(AmbiguousRoleRow(item, reason) for item in affected),
        requires_confirmation=True,
        reason=reason,
        source_transcript_hash=_source_hash(rows),
    )


def _mapped(item: int, role: str, row: _TranscriptRow, reason: str) -> RoleMapRow:
    return RoleMapRow(
        segment_id=row.segment_id,
        item=item,
        role=role,
        start=row.start,
        end=row.end,
        text=row.text,
        confidence="high",
        role_reason=reason,
    )


def _listen_and_repeat(rows: Sequence[_TranscriptRow]) -> RoleMapResult:
    if len(rows) != ITEM_COUNTS["listen_and_repeat"] * 2:
        return _ambiguous("listen_and_repeat", rows, "incomplete TOEFL transcript mapping")
    mapped: list[RoleMapRow] = []
    ambiguous: list[AmbiguousRoleRow] = []
    for item in range(1, 8):
        prompt, response = rows[(item - 1) * 2:item * 2]
        if _question(prompt.text) or _question(response.text) or _similarity(prompt.text, response.text) < 0.5:
            ambiguous.append(AmbiguousRoleRow(item, "repeat similarity cannot confirm TOEFL item"))
            continue
        mapped.extend((
            _mapped(item, "examiner", prompt, "expected_item_order"),
            _mapped(item, "learner", response, "repeat_similarity"),
        ))
    return RoleMapResult(
        task_type="listen_and_repeat",
        rows=tuple(mapped),
        ambiguous_rows=tuple(ambiguous),
        requires_confirmation=bool(ambiguous),
        reason=(
            "repeat similarity cannot confirm TOEFL item"
            if ambiguous else "complete TOEFL Listen and Repeat structure"
        ),
        source_transcript_hash=_source_hash(rows),
    )


def _interview(rows: Sequence[_TranscriptRow]) -> RoleMapResult:
    if len(rows) not in {7, 8}:
        return _ambiguous("take_an_interview", rows, "incomplete TOEFL transcript mapping")
    mapped: list[RoleMapRow] = []
    ambiguous: list[AmbiguousRoleRow] = []
    position = 0
    for item in range(1, 5):
        if position >= len(rows) or not _question(rows[position].text):
            return _ambiguous("take_an_interview", rows, "interview question structure cannot be confirmed")
        question = rows[position]
        position += 1
        if position >= len(rows):
            ambiguous.append(AmbiguousRoleRow(item, "missing learner answer"))
            continue
        answer = rows[position]
        if _question(answer.text):
            ambiguous.append(AmbiguousRoleRow(item, "missing learner answer"))
            continue
        if not _answer_discourse_evidence(question.text, answer.text):
            ambiguous.append(AmbiguousRoleRow(item, "learner answer lacks response discourse evidence"))
            position += 1
            continue
        mapped.extend((
            _mapped(item, "examiner", question, "question_answer_structure"),
            _mapped(item, "learner", answer, "answer_discourse_evidence"),
        ))
        position += 1
    if position != len(rows):
        return _ambiguous("take_an_interview", rows, "extra transcript turn prevents TOEFL mapping")
    return RoleMapResult(
        task_type="take_an_interview",
        rows=tuple(mapped),
        ambiguous_rows=tuple(ambiguous),
        requires_confirmation=bool(ambiguous),
        reason="missing learner answer" if ambiguous else "complete TOEFL interview structure",
        source_transcript_hash=_source_hash(rows),
    )


def infer_toefl_role_map(task_type: str, transcript_rows: Sequence[Mapping]) -> RoleMapResult:
    """Infer TOEFL examiner/learner roles from transcript structure only."""
    rows = _validate_rows(transcript_rows)
    if task_type not in ITEM_COUNTS:
        raise ValidationError("unknown TOEFL speaking task")
    if task_type == "listen_and_repeat":
        return _listen_and_repeat(rows)
    return _interview(rows)


def _asr_repeat_role_map(rows: Sequence[_TranscriptRow]) -> RoleMapResult:
    """Map ASR rows with directions and occasional extra response attempts."""
    expected = ITEM_COUNTS["listen_and_repeat"]
    mapped: list[RoleMapRow] = []
    ambiguities: list[AmbiguousRoleRow] = []
    cursor = 0
    for item in range(1, expected + 1):
        if cursor >= len(rows):
            ambiguities.append(AmbiguousRoleRow(item, "missing source or learner ASR turn"))
            continue
        source = rows[cursor]
        candidates = list(rows[cursor + 1:cursor + 3])
        if not candidates:
            ambiguities.append(AmbiguousRoleRow(item, "missing learner ASR turn"))
            continue
        ranked = sorted(
            ((_similarity(source.text, candidate.text), index, candidate) for index, candidate in enumerate(candidates)),
            key=lambda row: (-row[0], row[1]),
        )
        best_score, best_offset, response = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else -1.0
        if best_score < 0.15:
            ambiguities.append(AmbiguousRoleRow(item, "ASR source and learner turns are not similar enough"))
            # Preserve the expected source→response stride so a bad or
            # repeated response does not shift every later item by one turn.
            cursor += 2
            continue
        if best_offset > 0 and best_score - second_score < 0.10:
            ambiguities.append(AmbiguousRoleRow(item, "multiple learner ASR turns have ambiguous pairing"))
        mapped.extend((
            _mapped(item, "examiner", source, "asr_expected_item_order"),
            _mapped(item, "learner", response, "asr_repeat_similarity"),
        ))
        cursor += best_offset + 2

    if cursor < len(rows):
        ambiguities.append(AmbiguousRoleRow(expected, "extra ASR turn remains after the expected seven items"))
    return RoleMapResult(
        task_type="listen_and_repeat",
        rows=tuple(mapped),
        ambiguous_rows=tuple(ambiguities),
        requires_confirmation=bool(ambiguities),
        reason=(
            "ASR structure requires item confirmation"
            if ambiguities else "complete ASR Listen and Repeat structure"
        ),
        source_transcript_hash=_source_hash(rows),
    )


def infer_toefl_role_map_from_asr(
    task_type: str,
    transcript: Mapping | Sequence[Mapping],
    *,
    merge_gap_seconds: float = 0.15,
) -> RoleMapResult:
    """Infer TOEFL roles from normalized local-ASR segments.

    Directions are removed before route-specific mapping.  The function is
    intentionally conservative: uncertain pairings are returned as
    ``ambiguous_rows`` instead of assigning a speaker identity from acoustics.
    """
    if task_type not in ITEM_COUNTS:
        raise ValidationError("unknown TOEFL speaking task")
    rows = _merge_adjacent_rows(_asr_rows(transcript), max_gap_seconds=merge_gap_seconds)
    filtered = _drop_near_duplicate_rows(_filter_directions(task_type, rows))
    if task_type == "listen_and_repeat":
        return _asr_repeat_role_map(filtered)
    if len(filtered) != ITEM_COUNTS["take_an_interview"] * 2:
        return _ambiguous("take_an_interview", filtered, "ASR interview structure is incomplete or contains extra turns")
    return _interview(filtered)


def _collapse_asr_rows(rows: Sequence[_TranscriptRow]) -> _TranscriptRow:
    if not rows:
        raise ValidationError("cannot collapse empty ASR turn")
    return _TranscriptRow(
        segment_id="+".join(row.segment_id for row in rows),
        start=rows[0].start,
        end=rows[-1].end,
        text=" ".join(row.text for row in rows).strip(),
    )


def infer_toefl_role_map_from_single_item_asr(
    task_type: str,
    transcript: Mapping | Sequence[Mapping],
    *,
    item: int = 1,
    minimum_boundary_pause: float = 0.25,
) -> RoleMapResult:
    """Map one complete prompt→learner recording without global item drift.

    The largest pause is used as the candidate prompt/response boundary. This
    is deliberately item-local: a missing turn makes only this item ambiguous
    instead of shifting every later item in a batch.
    """
    if task_type not in ITEM_COUNTS:
        raise ValidationError("unknown TOEFL speaking task")
    if type(item) is not int or not 1 <= item <= ITEM_COUNTS[task_type]:
        raise ValidationError("single-item number is invalid")
    if not isfinite(minimum_boundary_pause) or minimum_boundary_pause < 0:
        raise ValidationError("single-item boundary pause is invalid")
    rows = _merge_adjacent_rows(_asr_rows(transcript), max_gap_seconds=0.15)
    filtered = _drop_near_duplicate_rows(_filter_directions(task_type, rows))
    if len(filtered) < 2:
        return _ambiguous(task_type, filtered, "single item needs both prompt and learner turns", [item])
    gaps = [filtered[index + 1].start - filtered[index].end for index in range(len(filtered) - 1)]
    split = max(range(len(gaps)), key=gaps.__getitem__)
    if gaps[split] < minimum_boundary_pause:
        return _ambiguous(task_type, filtered, "single-item prompt/learner pause is not clear", [item])
    prompt = _collapse_asr_rows(filtered[: split + 1])
    response = _collapse_asr_rows(filtered[split + 1 :])
    if task_type == "listen_and_repeat":
        if _similarity(prompt.text, response.text) < 0.15:
            return _ambiguous(task_type, filtered, "single-item repeat similarity cannot confirm pairing", [item])
        reasons = ("asr_item_pause", "asr_item_repeat_similarity")
    else:
        if not _question(prompt.text) or not _answer_discourse_evidence(prompt.text, response.text):
            return _ambiguous(task_type, filtered, "single-item interview pairing cannot be confirmed", [item])
        reasons = ("asr_item_pause", "asr_item_answer_discourse")
    return RoleMapResult(
        task_type=task_type,
        rows=(
            _mapped(item, "examiner", prompt, reasons[0]),
            _mapped(item, "learner", response, reasons[1]),
        ),
        ambiguous_rows=(),
        requires_confirmation=False,
        reason="complete single-item prompt/learner structure",
        source_transcript_hash=_source_hash(filtered),
    )
