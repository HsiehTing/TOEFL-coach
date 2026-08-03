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


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.casefold()))


def _similarity(first: str, second: str) -> float:
    first_tokens, second_tokens = _tokens(first), _tokens(second)
    if not first_tokens or not second_tokens:
        return 0.0
    return len(first_tokens & second_tokens) / len(first_tokens | second_tokens)


def _question(text: str) -> bool:
    return bool(re.match(
        r"^(?:what|why|how|who|where|when|which|describe|tell|do|does|did|can|could|would|will)\b",
        text.strip(),
        flags=re.IGNORECASE,
    )) or text.rstrip().endswith("?")


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
    for item in range(1, 8):
        prompt, response = rows[(item - 1) * 2:item * 2]
        if _question(prompt.text) or _question(response.text) or _similarity(prompt.text, response.text) < 0.5:
            return _ambiguous("listen_and_repeat", rows, "repeat similarity cannot confirm TOEFL item", (item,))
        mapped.extend((
            _mapped(item, "examiner", prompt, "expected_item_order"),
            _mapped(item, "learner", response, "repeat_similarity"),
        ))
    return RoleMapResult(
        task_type="listen_and_repeat",
        rows=tuple(mapped),
        ambiguous_rows=(),
        requires_confirmation=False,
        reason="complete TOEFL Listen and Repeat structure",
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
        if len(_tokens(answer.text)) < 4:
            ambiguous.append(AmbiguousRoleRow(item, "learner answer is too short to confirm"))
            position += 1
            continue
        mapped.extend((
            _mapped(item, "examiner", question, "question_answer_structure"),
            _mapped(item, "learner", answer, "question_answer_structure"),
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
