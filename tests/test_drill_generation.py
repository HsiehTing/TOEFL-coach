import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from toefl_tracker.drill_generation import (
    attach_generated_drill_lineage,
    build_drill_pack,
    retire_registered_drill_attempt_content,
    retire_registered_drill_pack,
    validate_drill_pack,
    write_assessment_hints,
    write_drill_pack,
)
from toefl_tracker.models import ValidationError


def _source_attempt(
    root: Path, *, task_type: str, code: str, prompt_override: str | None = None
) -> tuple[dict, dict]:
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
    prompt = prompt_override or (
        "Your professor is teaching a class on marketing. Discuss whether brands should "
        "update their advertising to match customer preferences."
        if task_type == "academic_discussion"
        else "Write a professional email asking the university to add an AI laboratory for students."
    )
    (directory / "prompt.md").write_text(prompt, encoding="utf-8")
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
    answer_key = (destination / "answer-key.md").read_text(encoding="utf-8")
    assert "Answer key" in answer_key
    assert "One sample answer:" in answer_key
    assert "One sample answer:" not in first["learner_markdown"]
    assessment = json.loads((destination / "assessment.json").read_text(encoding="utf-8"))
    assert [row["item_id"] for row in assessment] == [item["item_id"] for item in first["items"]]
    assert all(row["status"] == "" and row["reason"] == "" for row in assessment)
    (destination / "assessment.json").unlink()
    assert write_drill_pack(tmp_path, first) == destination
    assert (destination / "assessment.json").exists()


def test_clause_prompts_include_concrete_source_material(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="email", code="GRAM-CLAUSE")
    pack = build_drill_pack(tmp_path, _recommendation(source, "GRAM-CLAUSE"), seed=0)

    prompts = [item["prompt"] for item in pack["items"]]
    assert all(prompt.strip() for prompt in prompts)
    assert all("fresh example" not in prompt for prompt in prompts)
    assert all("`" in prompt for prompt in prompts)
    assert any("Because AI is increasingly used" in prompt for prompt in prompts)
    assert any("Although building the laboratory" in prompt for prompt in prompts)


def test_collocation_prompt_is_directly_answerable(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="email", code="LEX-COLLOCATION")
    pack = build_drill_pack(tmp_path, _recommendation(source, "LEX-COLLOCATION"), seed=0)

    assert all("Write a fresh sentence" not in item["prompt"] for item in pack["items"])
    assert "practical using skills" in pack["items"][0]["prompt"]
    assert len({item["prompt"] for item in pack["items"]}) == len(pack["items"])
    assert all(item["response_fields"] == ["response"] for item in pack["items"])
    assert all(item["response_mode"] == "open_response" for item in pack["items"])


def test_discussion_idea_pack_requires_one_bounded_causal_chain_response(tmp_path: Path) -> None:
    source, _ = _source_attempt(
        tmp_path, task_type="academic_discussion", code="DISCUSSION-ELABORATION"
    )
    pack = build_drill_pack(tmp_path, _recommendation(source, "DISCUSSION-ELABORATION"), seed=1)

    assert all(item["kind"] == "causal_chain" for item in pack["items"])
    assert all(item["response_fields"] == ["response"] for item in pack["items"])
    assert all("25–35 words in one sentence" in item["prompt"] for item in pack["items"])
    assert pack["context_summary"] == "brand identity, advertising updates, and customer reactions"
    assert all("brand identity" in item["prompt"] for item in pack["items"])
    assert all("public transportation" not in item["prompt"].lower() for item in pack["items"])


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


def test_discussion_pack_fails_closed_without_source_context(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="academic_discussion", code="GRAM-CLAUSE")
    (tmp_path / "tracker/writing/attempts" / source["attempt_id"] / "prompt.md").unlink()

    with pytest.raises(ValidationError, match="source prompt"):
        build_drill_pack(tmp_path, _recommendation(source, "GRAM-CLAUSE"), seed=0)


def test_pack_quality_gate_rejects_duplicate_prompts_before_writing(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="email", code="GRAM-CLAUSE")
    pack = build_drill_pack(tmp_path, _recommendation(source, "GRAM-CLAUSE"), seed=0)
    invalid = deepcopy(pack)
    invalid["items"][1]["prompt"] = invalid["items"][0]["prompt"]

    with pytest.raises(ValidationError, match="duplicate prompts"):
        validate_drill_pack(invalid)
    with pytest.raises(ValidationError, match="duplicate prompts"):
        write_drill_pack(tmp_path, invalid)


def test_pack_quality_gate_rejects_items_without_source_context(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="academic_discussion", code="GRAM-AGREEMENT")
    pack = build_drill_pack(tmp_path, _recommendation(source, "GRAM-AGREEMENT"), seed=0)
    invalid = deepcopy(pack)
    invalid["items"][0]["prompt"] = "Correct the verb: `Regular updates keeps a brand relevant.`"

    with pytest.raises(ValidationError, match="not bound to its source context"):
        validate_drill_pack(invalid)


def test_pack_quality_gate_rejects_answer_key_leakage(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="email", code="GRAM-CLAUSE")
    pack = build_drill_pack(tmp_path, _recommendation(source, "GRAM-CLAUSE"), seed=0)
    invalid = deepcopy(pack)
    invalid["learner_markdown"] += "\nOne sample answer: This must stay in the answer key.\n"

    with pytest.raises(ValidationError, match="leaks answer-key content"):
        validate_drill_pack(invalid)


def test_pack_quality_gate_requires_an_explicit_response_mode(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="email", code="GRAM-CLAUSE")
    pack = build_drill_pack(tmp_path, _recommendation(source, "GRAM-CLAUSE"), seed=0)
    invalid = deepcopy(pack)
    invalid["items"][0].pop("response_mode")

    with pytest.raises(ValidationError, match="invalid response mode"):
        validate_drill_pack(invalid)


def test_pack_generation_fails_closed_without_a_context_safe_template(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="academic_discussion", code="GRAM-CLAUSE")
    prompt_path = tmp_path / "tracker/writing/attempts" / source["attempt_id"] / "prompt.md"
    prompt_path.write_text("Discuss whether studying history helps solve future social problems.", encoding="utf-8")

    with pytest.raises(ValidationError, match="no context-safe"):
        build_drill_pack(tmp_path, _recommendation(source, "GRAM-CLAUSE"), seed=0)


def test_career_advice_email_uses_its_own_context_safe_templates(tmp_path: Path) -> None:
    source, _ = _source_attempt(
        tmp_path,
        task_type="email",
        code="GRAM-CLAUSE",
        prompt_override=(
            "Write an email to Sarah, who is considering a new job opportunity in another city. "
            "Offer advice based on her career goals and personal priorities, and encourage her to weigh her options."
        ),
    )
    pack = build_drill_pack(tmp_path, _recommendation(source, "GRAM-CLAUSE"), seed=0)

    assert pack["template_family"] == "email_career_decision_advice"
    assert pack["context_summary"] == "career options, personal priorities, and practical advice"
    assert all("career options" in item["prompt"] for item in pack["items"])
    assert all("laboratory" not in item["prompt"].lower() for item in pack["items"])
    assert "Sarah should" in pack["answer_key_markdown"]


def test_printing_problem_email_uses_its_own_context_safe_templates(tmp_path: Path) -> None:
    source, _ = _source_attempt(
        tmp_path,
        task_type="email",
        code="GRAM-AGREEMENT",
        prompt_override=(
            "Write an email to the printing shop's manager. The shop delivered the wrong version "
            "of your presentation file, so request corrected printed materials urgently."
        ),
    )
    pack = build_drill_pack(tmp_path, _recommendation(source, "GRAM-AGREEMENT"), seed=0)

    assert pack["template_family"] == "email_printing_problem_resolution"
    assert pack["context_summary"] == "an incorrect printed file and an urgent correction request"
    assert all("incorrect printed file" in item["prompt"] for item in pack["items"])
    assert all("laboratory" not in item["prompt"].lower() for item in pack["items"])
    assert "incorrect copies need to be replaced" in pack["answer_key_markdown"]


def test_completed_pack_can_be_retired_after_its_minimum_lineage_is_copied(tmp_path: Path) -> None:
    source, _ = _source_attempt(tmp_path, task_type="email", code="GRAM-CLAUSE")
    pack = build_drill_pack(tmp_path, _recommendation(source, "GRAM-CLAUSE"), seed=0)
    destination = write_drill_pack(tmp_path, pack)
    attempt = {
        "drill": {
            "set_id": "one-time-set",
            "source_attempt_ids": [source["attempt_id"]],
            "target_codes": ["GRAM-CLAUSE"],
            "item_count": len(pack["items"]),
            "correct_count": 0,
        }
    }

    attach_generated_drill_lineage(attempt, pack)
    assert attempt["drill"]["minimum_accuracy"] == 0.8
    assert attempt["drill"]["source_prompt_hash"] == pack["source_prompt_hash"]
    attempt["attempt_id"] = "W-DRILL-RESULT-ONLY"
    attempt["record_type"] = "targeted_drill"
    attempt_path = tmp_path / "tracker/writing/attempts/W-DRILL-RESULT-ONLY"
    attempt_path.mkdir(parents=True)
    (attempt_path / "attempt.yaml").write_text(yaml.safe_dump(attempt), encoding="utf-8")
    (attempt_path / "prompt.md").write_text("one-time prompt", encoding="utf-8")
    (attempt_path / "response-original.md").write_text("one-time response", encoding="utf-8")
    retire_registered_drill_attempt_content(tmp_path, attempt["attempt_id"])
    retire_registered_drill_pack(tmp_path, pack)

    assert not destination.exists()
    assert not (attempt_path / "prompt.md").exists()
    assert not (attempt_path / "response-original.md").exists()


def test_assessment_hints_check_causal_response_shape_without_scoring_meaning(tmp_path: Path) -> None:
    source, _ = _source_attempt(
        tmp_path, task_type="academic_discussion", code="DISCUSSION-ELABORATION"
    )
    pack = build_drill_pack(
        tmp_path,
        _recommendation(source, "DISCUSSION-ELABORATION") | {"drill": {"item_count": 1}},
        seed=0,
    )
    destination = write_drill_pack(tmp_path, pack)
    markdown_path = destination / "drill.md"
    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8").replace(
            "- response: [write your answer here]",
            "- response: Updates attract customers.",
        ),
        encoding="utf-8",
    )

    hints_path = write_assessment_hints(destination)
    hints = json.loads(hints_path.read_text(encoding="utf-8"))
    checks = hints["items"][0]["fields"][0]["checks"]

    assert hints["review_mode"] == "diagnostic_only"
    assert hints["scoring_authority"] == "coach_required"
    assert hints["items"][0]["response_mode"] == "open_response"
    assert {check["check"] for check in checks} == {
        "sentence_ending", "one_sentence", "word_range_25_35"
    }
    assert any(check["status"] == "attention" for check in checks)
    assert "meets_target" not in hints_path.read_text(encoding="utf-8")
