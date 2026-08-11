"""Explicit drill-to-new-prompt transfer lifecycle for Writing."""

import hashlib
from copy import deepcopy
from pathlib import Path

from toefl_tracker.io import read_yaml
from toefl_tracker.models import ValidationError


DEFAULT_MINIMUM_ACCURACY = 0.8


def prompt_hash(prompt: str) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValidationError("transfer prompt must be non-empty")
    normalized = prompt.replace("\r\n", "\n").strip()
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def suggest_opportunities(response: str, target_codes: list[str]) -> dict[str, dict]:
    """Offer a transparent suggestion; the learner/coach must confirm it."""
    if not isinstance(response, str):
        raise ValidationError("transfer response must be text")
    sentences = max(0, sum(response.count(mark) for mark in ".!?"))
    return {
        code: {"suggested_count": sentences if code == "GRAM-CLAUSE" else 0, "requires_confirmation": True}
        for code in target_codes
    }


def prepare_transfer_attempt(root: Path, attempt: dict, prompt: str, drill_attempt_id: str, confirmed_opportunities: dict[str, int]) -> dict:
    """Attach an auditable transfer link without mutating any source record."""
    if not isinstance(drill_attempt_id, str) or not drill_attempt_id:
        raise ValidationError("transfer requires a drill_attempt_id")
    if not isinstance(confirmed_opportunities, dict) or any(type(value) is not int or value < 0 for value in confirmed_opportunities.values()):
        raise ValidationError("transfer opportunity confirmation is invalid")
    drill = read_yaml(root / "tracker/writing/attempts" / drill_attempt_id / "attempt.yaml")
    metadata = drill.get("drill")
    if drill.get("record_type") != "targeted_drill" or not isinstance(metadata, dict):
        raise ValidationError("transfer must reference a persisted targeted drill")
    target_codes = metadata.get("target_codes")
    source_ids = metadata.get("source_attempt_ids")
    pack_id = metadata.get("drill_pack_id")
    if not isinstance(target_codes, list) or not target_codes or not isinstance(source_ids, list) or len(source_ids) != 1 or not isinstance(pack_id, str):
        raise ValidationError("targeted drill lacks a complete transfer lineage")
    source_id = source_ids[0]
    source = read_yaml(root / "tracker/writing/attempts" / source_id / "attempt.yaml")
    pack = read_yaml(root / "tracker/writing/drill-packs" / pack_id / "drill-pack.yaml")
    item_count = metadata.get("item_count")
    correct_count = metadata.get("correct_count")
    minimum_accuracy = pack.get("minimum_accuracy", DEFAULT_MINIMUM_ACCURACY)
    if (
        type(item_count) is not int
        or item_count <= 0
        or type(correct_count) is not int
        or not 0 <= correct_count <= item_count
        or type(minimum_accuracy) not in {int, float}
        or not 0 < minimum_accuracy <= 1
    ):
        raise ValidationError("targeted drill has invalid accuracy metadata")
    if correct_count / item_count < minimum_accuracy:
        raise ValidationError(
            f"transfer requires drill accuracy of at least {minimum_accuracy:.0%}"
        )
    if (
        attempt.get("modality") != "writing"
        or attempt.get("record_type") != "formal_original"
        or attempt.get("task_type") != drill.get("task_type")
        or source.get("task_type") != drill.get("task_type")
        or pack.get("source_attempt_id") != source_id
        or pack.get("task_type") != drill.get("task_type")
        or pack.get("target_codes") != target_codes
        or pack.get("version", 0) < 4
    ):
        raise ValidationError("transfer route or drill-pack lineage does not match")
    if set(confirmed_opportunities) != set(target_codes) or attempt.get("opportunities", {}) != confirmed_opportunities:
        raise ValidationError("transfer opportunity confirmation must match the persisted attempt opportunities")
    source_prompt_hash = prompt_hash((root / "tracker/writing/attempts" / source_id / "prompt.md").read_text(encoding="utf-8"))
    new_prompt_hash = prompt_hash(prompt)
    if source_prompt_hash == new_prompt_hash:
        raise ValidationError("transfer must use a new prompt")
    prepared = deepcopy(attempt)
    prepared["transfer"] = {
        "drill_attempt_id": drill_attempt_id,
        "drill_pack_id": pack_id,
        "source_attempt_id": source_id,
        "target_codes": target_codes,
        "opportunity_confirmation": confirmed_opportunities,
        "source_prompt_hash": source_prompt_hash,
        "transfer_prompt_hash": new_prompt_hash,
    }
    return prepared
