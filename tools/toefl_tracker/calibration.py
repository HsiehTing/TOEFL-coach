"""Fixed-sample regression checks for Writing feedback calibration."""

import json
from pathlib import Path

import yaml

from toefl_tracker.models import ValidationError
from toefl_tracker.writing import validate_writing_assessment


def _read_mapping(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValidationError(f"cannot read calibration mapping: {path}") from error
    if not isinstance(value, dict):
        raise ValidationError(f"calibration mapping must be a mapping: {path}")
    return value


def validate_writing_calibration(root: Path) -> list[dict]:
    cases_path = root / "tests/fixtures/calibration/writing/cases.yaml"
    cases_data = _read_mapping(cases_path)
    cases = cases_data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValidationError("writing calibration requires non-empty cases")
    results: list[dict] = []
    seen_routes: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValidationError("calibration case must be a mapping")
        fixture = cases_path.parent / case.get("fixture", "")
        attempt = _read_mapping(fixture / case.get("attempt_file", "attempt.yaml"))
        response = (fixture / "response.md").read_text(encoding="utf-8")
        feedback = (fixture / "feedback.md").read_text(encoding="utf-8")
        try:
            events = [json.loads(line) for line in (fixture / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError) as error:
            raise ValidationError(f"cannot read calibration events: {fixture}") from error
        validate_writing_assessment(attempt, events, feedback)
        task_type = attempt.get("task_type")
        if task_type not in {"email", "academic_discussion"} or task_type != case.get("task_type"):
            raise ValidationError("calibration task route mismatch")
        score = attempt.get("task_score", {}).get("value")
        expected = case.get("score_range")
        if not isinstance(expected, dict) or type(expected.get("minimum")) is not int or type(expected.get("maximum")) is not int or not expected["minimum"] <= score <= expected["maximum"]:
            raise ValidationError(f"calibration score outside approved range: {case.get('case_id')}")
        required_codes = case.get("required_codes")
        if not isinstance(required_codes, list) or not set(required_codes) <= {event.get("code") for event in events}:
            raise ValidationError(f"calibration required code missing: {case.get('case_id')}")
        for event in events:
            if event.get("level") in {"must_fix", "should_fix"} and event.get("source_excerpt", "").strip() not in response:
                raise ValidationError(f"calibration excerpt does not match response: {event.get('event_id')}")
        if "section band" in feedback.lower():
            raise ValidationError("calibration feedback must not claim a section band")
        seen_routes.add(task_type)
        results.append({"case_id": case.get("case_id"), "task_type": task_type, "result_label": "simulated_task_score", "score": score})
    if seen_routes != {"email", "academic_discussion"}:
        raise ValidationError("calibration suite must cover both Writing routes")
    return results
