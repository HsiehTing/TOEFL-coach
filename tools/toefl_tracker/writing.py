import re
from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path
from re import Match

from toefl_tracker.models import (
    ValidatedPracticeRegistration,
    ValidatedReevaluationRegistration,
    ValidationError,
)
from toefl_tracker.canonical import write_aggregate_events
from toefl_tracker.register import (
    _registration_lock,
    publish_registration,
    validate_practice_events,
)
from toefl_tracker.validation import validate_attempt, validate_reevaluation_metadata


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


def build_reevaluation_registration(
    root: Path,
    manifest: dict,
    attempt: dict,
    feedback: str,
) -> ValidatedReevaluationRegistration:
    """Build a source-free, schema-v2 re-evaluation bundle."""
    validate_attempt(attempt, manifest)
    validate_reevaluation_metadata(attempt)
    validate_writing_assessment(attempt, [], feedback)
    registration = ValidatedReevaluationRegistration(attempt=attempt, feedback=feedback)
    # Validate the parent relationship now for API callers. The publisher repeats
    # it under its transaction lock before it writes anything.
    with _registration_lock(root):
        attempts = root / "tracker" / attempt["modality"] / "attempts"
        from toefl_tracker.register import _validate_existing_attempts

        _validate_existing_attempts(root, attempt, attempts)
    return registration


def build_writing_registration(
    root: Path,
    manifest: dict,
    attempt: dict,
    prompt: str,
    response: str,
    feedback: str,
    events: Sequence[dict],
) -> ValidatedPracticeRegistration | ValidatedReevaluationRegistration:
    """Apply the Writing gate before handing a typed bundle to the publisher."""
    validate_attempt(attempt, manifest)
    if attempt["record_type"] == "re_evaluation":
        return build_reevaluation_registration(root, manifest, attempt, feedback)
    event_rows = tuple(events)
    validate_writing_assessment(attempt, list(event_rows), feedback)
    # This preflight gives direct builder callers the same error they would see
    # during publication. publish_registration repeats it while locked.
    with _registration_lock(root):
        validate_practice_events(root, attempt, response, event_rows)
    return ValidatedPracticeRegistration(
        attempt=attempt,
        prompt=prompt,
        response=response,
        feedback=feedback,
        events=event_rows,
        require_contextual_validation=True,
    )


def register_writing_attempt(
    root: Path,
    manifest: dict,
    attempt: dict,
    prompt: str,
    response: str,
    feedback: str,
    events: Sequence[dict],
) -> Path:
    registration = build_writing_registration(
        root, manifest, attempt, prompt, response, feedback, events
    )
    destination = publish_registration(root, manifest, registration)
    with _registration_lock(root):
        write_aggregate_events(root, attempt["modality"])
    return destination
