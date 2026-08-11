from pathlib import Path

import toefl_tracker.practice_queue as queue_module

from test_reports import report_event, write_attempt, write_events
from toefl_tracker.practice_queue import build_practice_queue, write_practice_queue


def test_queue_groups_latest_supported_focuses_into_drill_then_transfer(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-EMAIL-1", "email", "formal_original")
    write_attempt(tmp_path, "W-AD-2", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-EMAIL-3", "email", "formal_original")
    write_events(tmp_path, [
        report_event("W-EMAIL-1", "E-1", "GRAM-CLAUSE", task_specific=False),
        report_event("W-EMAIL-3", "E-2", "GRAM-CLAUSE", task_specific=False),
        report_event("W-EMAIL-3", "E-3", "LEX-COLLOCATION", task_specific=False),
    ])

    queue = build_practice_queue(tmp_path)

    assert queue["result_label"] == "diagnostic_practice_queue"
    assert len(queue["actions"]) == 2
    drill, transfer = queue["actions"]
    assert drill["kind"] == "targeted_drill"
    assert drill["source_attempt_id"] == "W-EMAIL-3"
    assert drill["target_codes"] == ["GRAM-CLAUSE", "LEX-COLLOCATION"]
    assert transfer["kind"] == "fresh_transfer_check"
    assert transfer["source_action_id"] == drill["action_id"]
    assert drill["status"] == "ready"
    assert transfer["status"] == "blocked_by_drill"
    assert "task_score" not in queue


def test_queue_is_derived_and_does_not_create_actions_without_supported_evidence(
    tmp_path: Path,
) -> None:
    write_attempt(tmp_path, "W-AD-1", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-3", "academic_discussion", "formal_original")
    write_events(tmp_path, [
        report_event("W-AD-1", "E-1", "GRAM-NEGATION", task_specific=False),
    ])

    queue = build_practice_queue(tmp_path)
    path = write_practice_queue(tmp_path)

    assert queue["actions"] == []
    assert queue["deferred_actions"][0]["status"] == "blocked_by_template"
    assert path == tmp_path / "tracker/writing/practice-queue.md"
    assert "diagnostic planning artifact" in path.read_text(encoding="utf-8").lower()


def test_queue_shows_all_training_plans_and_defers_lower_priority(
    tmp_path: Path, monkeypatch
) -> None:
    write_attempt(tmp_path, "W-EMAIL-1", "email", "formal_original")
    write_attempt(tmp_path, "W-EMAIL-3", "email", "formal_original")
    write_events(tmp_path, [
        report_event("W-EMAIL-1", "E-1", "GRAM-CLAUSE", task_specific=False),
        report_event("W-EMAIL-3", "E-2", "GRAM-AGREEMENT", task_specific=False),
    ])
    plans = {
        "version": 1,
        "recommendations": [
            {
                "recommendation_id": "PLAN-W-EMAIL-1",
                "source_attempt_id": "W-EMAIL-1",
                "task_type": "email",
                "target_codes": ["GRAM-CLAUSE"],
                "drill": {"item_count": 8, "minimum_accuracy": 0.8},
            },
            {
                "recommendation_id": "PLAN-W-EMAIL-3",
                "source_attempt_id": "W-EMAIL-3",
                "task_type": "email",
                "target_codes": ["GRAM-AGREEMENT"],
                "drill": {"item_count": 8, "minimum_accuracy": 0.8},
            },
        ],
    }
    monkeypatch.setattr(queue_module, "build_training_plan", lambda root: plans)

    queue = build_practice_queue(tmp_path)

    assert queue["active_training_plan_count"] == 2
    assert len(queue["actions"]) == 4
    assert queue["actions"][0]["recommendation_id"] == "PLAN-W-EMAIL-3"
    assert queue["actions"][0]["status"] == "ready"
    assert queue["actions"][2]["recommendation_id"] == "PLAN-W-EMAIL-1"
    assert queue["actions"][2]["status"] == "deferred_by_priority"


def test_queue_blocks_a_plan_when_its_source_prompt_has_no_safe_template(
    tmp_path: Path, monkeypatch
) -> None:
    write_attempt(tmp_path, "W-EMAIL-1", "email", "formal_original")
    write_events(tmp_path, [])
    prompt_path = tmp_path / "tracker/writing/attempts/W-EMAIL-1/prompt.md"
    prompt_path.write_text(
        "Write an email asking your professor to extend an academic deadline.",
        encoding="utf-8",
    )
    plans = {
        "version": 1,
        "recommendations": [{
            "recommendation_id": "PLAN-W-EMAIL-1",
            "source_attempt_id": "W-EMAIL-1",
            "task_type": "email",
            "target_codes": ["GRAM-CLAUSE"],
            "drill": {"item_count": 8, "minimum_accuracy": 0.8},
        }],
    }
    monkeypatch.setattr(queue_module, "build_training_plan", lambda root: plans)

    queue = build_practice_queue(tmp_path)

    assert queue["actions"] == []
    assert queue["deferred_actions"][0]["status"] == "blocked_by_template"
    assert "no context-safe Email template" in queue["deferred_actions"][0]["status_reason"]


def test_queue_blocks_transfer_when_one_target_code_is_below_threshold() -> None:
    drill = {
        "drill": {
            "target_codes": ["GRAM-CLAUSE", "GRAM-AGREEMENT"],
            "item_count": 10,
            "correct_count": 8,
            "minimum_accuracy": 0.8,
            "code_results": [
                {"code": "GRAM-CLAUSE", "item_count": 8, "correct_count": 8, "partial_count": 0},
                {"code": "GRAM-AGREEMENT", "item_count": 2, "correct_count": 0, "partial_count": 0},
            ],
        }
    }

    status, reason = queue_module._drill_status(drill)

    assert status == "blocked_by_accuracy"
    assert "GRAM-AGREEMENT" in reason
