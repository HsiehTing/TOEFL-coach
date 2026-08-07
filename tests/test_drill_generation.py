import json
import shutil
from pathlib import Path

import pytest
import yaml

from toefl_tracker.drill_generation import build_drill_pack, write_drill_pack
from toefl_tracker.models import ValidationError


def _source_attempt(root: Path, *, task_type: str, code: str) -> tuple[dict, dict]:
    standards = Path(__file__).parents[1] / "standards"
    if not (root / "standards").exists():
        shutil.copytree(standards, root / "standards")
    attempt_id = "W-SOURCE-001"
    attempt = {
        "attempt_id": attempt_id,
        "modality": "writing",
        "task_type": task_type,
        "record_type": "formal_original",
        "submitted_at": "2026-08-07T10:00:00+08:00",
    }
    event = {
        "event_id": "E-SOURCE-001",
        "attempt_id": attempt_id,
        "taxonomy_version": 1,
        "code": code,
        "source_excerpt": "The original sentence has a weak boundary.",
        "audio_timestamp": None,
        "suggested_revision": "Use a complete clause with a clear connector.",
        "reason": "Fixture evidence.",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": code.startswith(("DISCUSSION-", "EMAIL-")),
        "opportunity_present": True,
        "historical_status": "new",
    }
    directory = root / "tracker/writing/attempts" / attempt_id
    directory.mkdir(parents=True)
    (directory / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
    (directory / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    return attempt, event


def _recommendation(source: dict, code: str) -> dict:
    return {
        "recommendation_id": "PLAN-W-SOURCE-001",
        "source_attempt_id": source["attempt_id"],
        "task_type": source["task_type"],
        "target_codes": [code],
        "drill": {"item_count": 8, "minimum_accuracy": 0.8},
    }


def test_clause_pack_is_traceable_stable_and_hides_answers(tmp_path: Path) -> None:
    source, event = _source_attempt(tmp_path, task_type="email", code="GRAM-CLAUSE")
    recommendation = _recommendation(source, "GRAM-CLAUSE")

    first = build_drill_pack(tmp_path, recommendation, seed=17)
    second = build_drill_pack(tmp_path, recommendation, seed=17)

    assert first == second
    assert len(first["items"]) == 8
    assert first["drill_id"].startswith("WD-")
    assert {item["evidence"]["event_id"] for item in first["items"]} == {event["event_id"]}
    assert {item["evidence"]["code"] for item in first["items"]} == {"GRAM-CLAUSE"}
    assert event["suggested_revision"] not in first["learner_markdown"]
    assert event["source_excerpt"] not in first["learner_markdown"]
    assert "task_score" not in first

    destination = write_drill_pack(tmp_path, first)
    assert (destination / "drill.md").read_text(encoding="utf-8") == first["learner_markdown"]
    assert "Answer key" not in first["learner_markdown"]
    assert "Answer key" in (destination / "answer-key.md").read_text(encoding="utf-8")


def test_discussion_idea_pack_requires_causal_chain_fields(tmp_path: Path) -> None:
    source, _ = _source_attempt(
        tmp_path, task_type="academic_discussion", code="DISCUSSION-ELABORATION"
    )
    pack = build_drill_pack(tmp_path, _recommendation(source, "DISCUSSION-ELABORATION"), seed=1)

    assert all(item["kind"] == "causal_chain" for item in pack["items"])
    assert all(
        item["response_fields"] == ["claim", "mechanism", "concrete_outcome", "link_back"]
        for item in pack["items"]
    )


@pytest.mark.parametrize(
    ("task_type", "code", "expected_kind"),
    [
        ("email", "GRAM-ARTICLE", "article_choice"),
        ("academic_discussion", "GRAM-AGREEMENT", "agreement_control"),
        ("email", "LEX-WORDFORM", "word_form"),
        ("academic_discussion", "LEX-COLLOCATION", "collocation"),
        ("email", "EMAIL-ACTION", "email_action"),
    ],
)
def test_recurring_learner_weaknesses_have_route_safe_drills(
    tmp_path: Path, task_type: str, code: str, expected_kind: str
) -> None:
    source, _ = _source_attempt(tmp_path, task_type=task_type, code=code)
    pack = build_drill_pack(tmp_path, _recommendation(source, code), seed=2)

    assert {item["kind"] for item in pack["items"]} == {expected_kind}
    assert all(item["evidence"]["code"] == code for item in pack["items"])
    assert "suggested_revision" not in pack["learner_markdown"]


@pytest.mark.parametrize(
    ("task_type", "code", "message"),
    [
        ("email", "DISCUSSION-ELABORATION", "does not apply"),
        ("email", "UNKNOWN-CODE", "unknown"),
    ],
)
def test_pack_generation_fails_closed_for_invalid_route_or_code(
    tmp_path: Path, task_type: str, code: str, message: str
) -> None:
    source, _ = _source_attempt(tmp_path, task_type=task_type, code=code)
    with pytest.raises(ValidationError, match=message):
        build_drill_pack(tmp_path, _recommendation(source, code), seed=0)


def test_pack_generation_requires_immutable_evidence(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="email", code="GRAM-CLAUSE")
    (tmp_path / "tracker/writing/attempts/W-SOURCE-001/events.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(ValidationError, match="immutable evidence"):
        build_drill_pack(tmp_path, _recommendation(source, "GRAM-CLAUSE"), seed=0)
