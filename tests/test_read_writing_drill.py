import json
import shutil
from pathlib import Path

import pytest
import yaml

from toefl_tracker.drill_generation import build_drill_pack, read_completed_drill, write_drill_pack
from toefl_tracker.models import ValidationError


def _source_attempt(root: Path) -> dict:
    standards = Path(__file__).parents[1] / "standards"
    shutil.copytree(standards, root / "standards")
    attempt_id = "W-SOURCE-DRILL-001"
    attempt = {
        "attempt_id": attempt_id,
        "modality": "writing",
        "task_type": "email",
        "record_type": "formal_original",
        "submitted_at": "2026-08-08T10:00:00+08:00",
    }
    event = {
        "event_id": "E-SOURCE-DRILL-001",
        "attempt_id": attempt_id,
        "taxonomy_version": 1,
        "code": "GRAM-CLAUSE",
        "source_excerpt": "The original sentence has a weak boundary.",
        "audio_timestamp": None,
        "suggested_revision": "Use a complete clause with a clear connector.",
        "reason": "Fixture evidence.",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }
    directory = root / "tracker/writing/attempts" / attempt_id
    directory.mkdir(parents=True)
    (directory / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
    (directory / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    return attempt


def test_read_completed_drill_uses_drill_md_as_source(tmp_path: Path) -> None:
    source = _source_attempt(tmp_path)
    recommendation = {
        "recommendation_id": "PLAN-W-SOURCE-DRILL-001",
        "source_attempt_id": source["attempt_id"],
        "task_type": "email",
        "target_codes": ["GRAM-CLAUSE"],
        "drill": {"item_count": 2},
    }
    pack = build_drill_pack(tmp_path, recommendation, seed=0)
    destination = write_drill_pack(tmp_path, pack)
    markdown = (destination / "drill.md").read_text(encoding="utf-8")
    markdown = markdown.replace("- response: [write your answer here]", "- response: Students need practical AI training.", 1)
    markdown = markdown.replace("- response: [write your answer here]", "- response: Please support the proposal.", 1)
    (destination / "drill.md").write_text(markdown, encoding="utf-8")

    completed = read_completed_drill(destination)

    assert completed["responses"]["I01"]["response"] == "Students need practical AI training."
    assert "Students need practical AI training." not in completed["prompt"]
    assert "I01.response: Students need practical AI training." in completed["response"]
    assert not (destination / "answer-key.md").read_text(encoding="utf-8").startswith(completed["response"])


def test_read_completed_drill_rejects_unanswered_fields(tmp_path: Path) -> None:
    source = _source_attempt(tmp_path)
    recommendation = {
        "recommendation_id": "PLAN-W-SOURCE-DRILL-002",
        "source_attempt_id": source["attempt_id"],
        "task_type": "email",
        "target_codes": ["GRAM-CLAUSE"],
        "drill": {"item_count": 1},
    }
    destination = write_drill_pack(tmp_path, build_drill_pack(tmp_path, recommendation, seed=0))

    with pytest.raises(ValidationError, match="incomplete"):
        read_completed_drill(destination)


def test_read_completed_drill_rejects_item_mismatch(tmp_path: Path) -> None:
    source = _source_attempt(tmp_path)
    recommendation = {
        "recommendation_id": "PLAN-W-SOURCE-DRILL-003",
        "source_attempt_id": source["attempt_id"],
        "task_type": "email",
        "target_codes": ["GRAM-CLAUSE"],
        "drill": {"item_count": 1},
    }
    destination = write_drill_pack(tmp_path, build_drill_pack(tmp_path, recommendation, seed=0))
    markdown = (destination / "drill.md").read_text(encoding="utf-8").replace("## I01", "## I99")
    (destination / "drill.md").write_text(markdown, encoding="utf-8")

    with pytest.raises(ValidationError, match="item IDs"):
        read_completed_drill(destination)


def test_read_completed_drill_rejects_legacy_pack_version(tmp_path: Path) -> None:
    source = _source_attempt(tmp_path)
    recommendation = {
        "recommendation_id": "PLAN-W-SOURCE-DRILL-004",
        "source_attempt_id": source["attempt_id"],
        "task_type": "email",
        "target_codes": ["GRAM-CLAUSE"],
        "drill": {"item_count": 1},
    }
    destination = write_drill_pack(tmp_path, build_drill_pack(tmp_path, recommendation, seed=0))
    metadata_path = destination / "drill-pack.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    metadata["version"] = 3
    metadata_path.write_text(yaml.safe_dump(metadata), encoding="utf-8")

    with pytest.raises(ValidationError, match="legacy or incompatible"):
        read_completed_drill(destination)


def test_read_completed_drill_rejects_non_response_content(tmp_path: Path) -> None:
    source = _source_attempt(tmp_path)
    recommendation = {
        "recommendation_id": "PLAN-W-SOURCE-DRILL-005",
        "source_attempt_id": source["attempt_id"],
        "task_type": "email",
        "target_codes": ["GRAM-CLAUSE"],
        "drill": {"item_count": 1},
    }
    destination = write_drill_pack(tmp_path, build_drill_pack(tmp_path, recommendation, seed=0))
    markdown_path = destination / "drill.md"
    markdown = markdown_path.read_text(encoding="utf-8")
    markdown = markdown.replace(
        "- response: [write your answer here]",
        "示範正確答案：This line is not a learner response.\n\n- response: Students need practical AI training.",
    )
    markdown_path.write_text(markdown, encoding="utf-8")

    with pytest.raises(ValidationError, match="stale or contains non-response"):
        read_completed_drill(destination)
