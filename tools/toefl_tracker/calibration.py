"""Fixed-sample regression checks for Writing feedback calibration."""

import json
import re
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


def _required_strings(case: dict, field: str) -> list[str]:
    values = case.get(field)
    if not isinstance(values, list) or not values or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ValidationError(f"calibration {field} must be a non-empty list of strings")
    return values


def _feedback_section(feedback: str, heading: str) -> str:
    headings = list(re.finditer(r"(?m)^# (?P<title>[^\r\n]+)\s*$", feedback))
    for index, match in enumerate(headings):
        if match.group("title") == heading:
            end = headings[index + 1].start() if index + 1 < len(headings) else len(feedback)
            return feedback[match.end():end]
    raise ValidationError(f"calibration feedback is missing {heading}")


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
        if attempt.get("attempt_id") != case.get("attempt_id"):
            raise ValidationError(f"calibration attempt ID mismatch: {case.get('case_id')}")
        if attempt.get("rubric_version") != case.get("rubric_version"):
            raise ValidationError(f"calibration rubric version mismatch: {case.get('case_id')}")
        score = attempt.get("task_score", {}).get("value")
        expected = case.get("score_range")
        if not isinstance(expected, dict) or type(expected.get("minimum")) is not int or type(expected.get("maximum")) is not int or not expected["minimum"] <= score <= expected["maximum"]:
            raise ValidationError(f"calibration score outside approved range: {case.get('case_id')}")
        expected_codes = sorted(_required_strings(case, "counted_codes"))
        actual_codes = sorted(
            event.get("code") for event in events
            if event.get("level") in {"must_fix", "should_fix"}
        )
        if actual_codes != expected_codes:
            raise ValidationError(f"calibration code classification drift: {case.get('case_id')}")
        required_reasons = case.get("required_feedback_markers")
        if not isinstance(required_reasons, dict) or set(required_reasons) != {
            "why_this_level", "why_not_next"
        }:
            raise ValidationError(f"calibration rubric-reason contract is invalid: {case.get('case_id')}")
        for section, heading in (("why_this_level", "Why this level"), ("why_not_next", "Why not the next level")):
            markers = required_reasons[section]
            if not isinstance(markers, list) or not markers or any(
                not isinstance(marker, str) or not marker.strip() for marker in markers
            ):
                raise ValidationError(f"calibration rubric-reason markers are invalid: {case.get('case_id')}")
            feedback_section = _feedback_section(feedback, heading).lower()
            if any(marker.lower() not in feedback_section for marker in markers):
                raise ValidationError(f"calibration rubric-reason drift: {case.get('case_id')}")
        for event in events:
            if event.get("level") in {"must_fix", "should_fix"} and event.get("source_excerpt", "").strip() not in response:
                raise ValidationError(f"calibration excerpt does not match response: {event.get('event_id')}")
        if "section band" in feedback.lower():
            raise ValidationError("calibration feedback must not claim a section band")
        seen_routes.add(task_type)
        results.append({
            "case_id": case.get("case_id"),
            "task_type": task_type,
            "result_label": "simulated_task_score",
            "score": score,
            "rubric_version": attempt["rubric_version"],
            "counted_codes": actual_codes,
        })
    if seen_routes != {"email", "academic_discussion"}:
        raise ValidationError("calibration suite must cover both Writing routes")
    return results
