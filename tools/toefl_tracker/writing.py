import re
from collections.abc import Mapping
from re import Match

from toefl_tracker.models import ValidationError


RUBRICS = {
    "email": "ets-writing-email-2025-applicable-2026",
    "academic_discussion": "ets-writing-discussion-2025-applicable-2026",
}
REQUIRED_HEADINGS = (
    "# Result",
    "# Why this level",
    "# Why not the next level",
    "# Evidence",
    "# Priorities",
    "# Rewrite task",
)


def _ordered_heading_matches(feedback: str) -> list[Match[str]]:
    matches = list(
        re.finditer(r"(?m)^(# [^\r\n]+?)[ \t]*\r?$", feedback)
    )
    headings = tuple(match.group(1) for match in matches)
    if headings != REQUIRED_HEADINGS:
        raise ValidationError(
            "first-round feedback headings are missing, duplicated, or out of order"
        )
    return matches


def validate_writing_assessment(
    attempt: dict,
    events: list[dict],
    feedback: str,
) -> None:
    if not isinstance(attempt, Mapping):
        raise ValidationError("writing attempt must be a mapping")
    if attempt.get("modality") != "writing":
        raise ValidationError("writing assessment requires writing modality")

    expected = RUBRICS.get(attempt.get("task_type"))
    if expected is None or attempt.get("rubric_version") != expected:
        raise ValidationError("writing task and rubric do not match")

    score = attempt.get("task_score")
    if not isinstance(score, Mapping):
        raise ValidationError("writing task score must be an integer from 0 to 5")
    value = score.get("value")
    if (
        score.get("scale") != "0-5"
        or type(value) is not int
        or not 0 <= value <= 5
    ):
        raise ValidationError("writing task score must be an integer from 0 to 5")

    if not isinstance(feedback, str):
        raise ValidationError("first-round feedback is missing required headings")

    heading_matches = _ordered_heading_matches(feedback)
    priority_block = feedback[
        heading_matches[-2].end():heading_matches[-1].start()
    ]
    if len(re.findall(r"(?m)^\d+\.\s", priority_block)) > 3:
        raise ValidationError("first-round feedback exceeds three priorities")

    if not isinstance(events, list):
        raise ValidationError("writing events must be a list of mappings")
    for event in events:
        if not isinstance(event, Mapping):
            raise ValidationError("each writing event must be a mapping")
        if event.get("level") not in {"must_fix", "should_fix"}:
            continue
        excerpt = event.get("source_excerpt")
        if (
            not isinstance(excerpt, str)
            or not excerpt.strip()
            or excerpt.strip() not in feedback
        ):
            raise ValidationError(
                f"feedback omits counted evidence: {event.get('event_id')}"
            )
