import json
import shutil
from pathlib import Path

import pytest
import yaml

from toefl_tracker.models import ValidationError
from toefl_tracker.transfer import prepare_transfer_attempt, prompt_hash


def _setup_lineage(root: Path, *, task_type: str = "email") -> dict:
    source_id = "W-SOURCE-001"
    drill_id = "W-DRILL-001"
    pack_id = "WD-0000000000000001"
    source = root / "tracker/writing/attempts" / source_id
    source.mkdir(parents=True)
    (source / "attempt.yaml").write_text(yaml.safe_dump({"attempt_id": source_id, "task_type": task_type}), encoding="utf-8")
    (source / "prompt.md").write_text("Original prompt", encoding="utf-8")
    drill = root / "tracker/writing/attempts" / drill_id
    drill.mkdir(parents=True)
    (drill / "attempt.yaml").write_text(yaml.safe_dump({
        "attempt_id": drill_id,
        "modality": "writing",
        "task_type": task_type,
        "record_type": "targeted_drill",
        "drill": {
            "set_id": "set-1",
            "target_codes": ["GRAM-CLAUSE"],
            "item_count": 8,
            "correct_count": 7,
            "source_attempt_ids": [source_id],
            "drill_pack_id": pack_id,
            "recommendation_id": "PLAN-W-SOURCE-001",
            "minimum_accuracy": 0.8,
            "source_prompt_hash": prompt_hash("Original prompt"),
            "pack_version": 9,
            "artifact_retention": "result_only",
        },
    }), encoding="utf-8")
    pack = root / "tracker/writing/drill-packs" / pack_id
    pack.mkdir(parents=True)
    (pack / "drill-pack.yaml").write_text(yaml.safe_dump({"version": 4, "minimum_accuracy": 0.8, "drill_id": pack_id, "source_attempt_id": source_id, "task_type": task_type, "target_codes": ["GRAM-CLAUSE"]}), encoding="utf-8")
    return {"source_id": source_id, "drill_id": drill_id, "pack_id": pack_id}


def _attempt(task_type: str = "email", opportunities: int = 1) -> dict:
    return {"attempt_id": "W-TRANSFER-001", "modality": "writing", "task_type": task_type, "record_type": "formal_original", "opportunities": {"GRAM-CLAUSE": opportunities}}


def test_transfer_links_source_drill_pack_and_confirmed_opportunity(tmp_path: Path) -> None:
    lineage = _setup_lineage(tmp_path)
    prepared = prepare_transfer_attempt(tmp_path, _attempt(), "A new prompt", lineage["drill_id"], {"GRAM-CLAUSE": 1})

    assert prepared["transfer"]["source_attempt_id"] == lineage["source_id"]
    assert prepared["transfer"]["drill_pack_id"] == lineage["pack_id"]
    assert prepared["transfer"]["target_codes"] == ["GRAM-CLAUSE"]
    assert prepared["transfer"]["source_prompt_hash"] != prepared["transfer"]["transfer_prompt_hash"]


def test_transfer_uses_registered_lineage_after_one_time_pack_is_removed(tmp_path: Path) -> None:
    lineage = _setup_lineage(tmp_path)
    shutil.rmtree(tmp_path / "tracker/writing/drill-packs" / lineage["pack_id"])

    prepared = prepare_transfer_attempt(
        tmp_path, _attempt(), "A new prompt", lineage["drill_id"], {"GRAM-CLAUSE": 1}
    )

    assert prepared["transfer"]["drill_pack_id"] == lineage["pack_id"]


def test_transfer_rejects_drill_below_accuracy_threshold(tmp_path: Path) -> None:
    lineage = _setup_lineage(tmp_path)
    drill_path = tmp_path / "tracker/writing/attempts" / lineage["drill_id"] / "attempt.yaml"
    drill = yaml.safe_load(drill_path.read_text(encoding="utf-8"))
    drill["drill"]["correct_count"] = 0
    drill_path.write_text(yaml.safe_dump(drill), encoding="utf-8")

    with pytest.raises(ValidationError, match="at least 80%"):
        prepare_transfer_attempt(
            tmp_path,
            _attempt(),
            "A new prompt",
            lineage["drill_id"],
            {"GRAM-CLAUSE": 1},
        )


@pytest.mark.parametrize(
    ("prompt", "task_type", "confirmed", "message"),
    [
        ("Original prompt", "email", {"GRAM-CLAUSE": 1}, "new prompt"),
        ("A new prompt", "academic_discussion", {"GRAM-CLAUSE": 1}, "route"),
        ("A new prompt", "email", {"GRAM-CLAUSE": 0}, "confirmation"),
    ],
)
def test_transfer_rejects_reused_prompt_cross_route_or_unconfirmed_opportunity(
    tmp_path: Path, prompt: str, task_type: str, confirmed: dict, message: str
) -> None:
    lineage = _setup_lineage(tmp_path)
    with pytest.raises(ValidationError, match=message):
        prepare_transfer_attempt(tmp_path, _attempt(task_type), prompt, lineage["drill_id"], confirmed)
