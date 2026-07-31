import re

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


def validate_writing_assessment(
    attempt: dict,
    events: list[dict],
    feedback: str,
) -> None:
    if attempt.get("modality") != "writing":
        raise ValidationError("writing assessment requires writing modality")

    expected = RUBRICS.get(attempt.get("task_type"))
    if expected is None or attempt.get("rubric_version") != expected:
        raise ValidationError("writing task and rubric do not match")

    score = attempt.get("task_score")
    if not isinstance(score, dict):
        raise ValidationError("writing task score must be an integer from 0 to 5")
    value = score.get("value")
    if (
        score.get("scale") != "0-5"
        or type(value) is not int
        or not 0 <= value <= 5
    ):
        raise ValidationError("writing task score must be an integer from 0 to 5")

    if not isinstance(feedback, str) or any(
        heading not in feedback for heading in REQUIRED_HEADINGS
    ):
        raise ValidationError("first-round feedback is missing required headings")

    priority_block = feedback.split("# Priorities", 1)[1].split(
        "# Rewrite task", 1
    )[0]
    if len(re.findall(r"(?m)^\d+\.\s", priority_block)) > 3:
        raise ValidationError("first-round feedback exceeds three priorities")

    for event in events:
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
