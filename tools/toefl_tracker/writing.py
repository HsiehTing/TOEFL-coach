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
from toefl_tracker.training_plan import write_training_plan
from toefl_tracker.progress import write_progress_overview
from toefl_tracker.practice_queue import write_practice_queue
from toefl_tracker.reports import rebuild_modality
from toefl_tracker.revision_learning import write_revision_learning


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
FOLLOW_UP_HEADING = "# Naturalness and precision follow-up"


def _ordered_heading_matches(
    feedback: str, *, require_revision_follow_up: bool = False
) -> list[Match[str]]:
    matches = list(
        re.finditer(r"(?m)^(# [^\r\n]+?)[ \t]*\r?$", feedback)
    )
    headings = tuple(match.group(1) for match in matches)
    expected = REQUIRED_HEADINGS + (FOLLOW_UP_HEADING,)
    if require_revision_follow_up and headings == REQUIRED_HEADINGS:
        raise ValidationError("revision feedback requires naturalness follow-up")
    allowed = expected if require_revision_follow_up else REQUIRED_HEADINGS
    if headings != allowed:
        raise ValidationError(
            "first-round feedback headings are missing, duplicated, or out of order"
        )
    return matches


def _validate_revision_follow_up(
    feedback: str, response: str, parent_feedback: str | None = None
) -> None:
    """Validate the required non-scoring coaching artifact on a revision.

    The coach writes this prose, but the registration gate protects its key
    boundaries: it must remain after the ordinary assessment, cite the learner's
    actual revision, stay bounded, and not leak a mini-practice answer on first
    display.  It deliberately does not create events or alter any tracker state.
    """
    if FOLLOW_UP_HEADING not in feedback:
        raise ValidationError("revision feedback requires naturalness follow-up")
    follow_up = feedback.split(FOLLOW_UP_HEADING, 1)[1].strip()
    if not follow_up:
        raise ValidationError("revision naturalness follow-up is empty")
    if "No naturalness or precision issue to flag." in follow_up:
        return

    suggestions = re.findall(r"(?m)^\d+\.\s+Excerpt:\s*`([^`]+)`", follow_up)
    if not 1 <= len(suggestions) <= 3:
        raise ValidationError("revision naturalness follow-up requires one to three excerpt suggestions")
    if len(set(suggestions)) != len(suggestions) or any(excerpt not in response for excerpt in suggestions):
        raise ValidationError("revision naturalness follow-up excerpts must be distinct learner text")
    heading_matches = _ordered_heading_matches(
        feedback, require_revision_follow_up=True
    )
    evidence_block = feedback[heading_matches[3].end():heading_matches[4].start()]
    if any(excerpt in evidence_block for excerpt in suggestions):
        raise ValidationError(
            "revision naturalness follow-up must not repeat scored evidence"
        )
    if parent_feedback is not None and any(
        excerpt in parent_feedback for excerpt in suggestions
    ):
        raise ValidationError(
            "revision naturalness follow-up must not repeat parent feedback"
        )
    # The suggestion rows are numbered too.  Mini-practice is explicitly
    # scoped under this heading so the count cannot accidentally include prose.
    practice_match = re.search(r"(?ms)^## Mini-practice\s*$\n(.*?)(?=^## |\Z)", follow_up)
    if practice_match is None:
        raise ValidationError("revision naturalness follow-up requires mini-practice")
    practice_rows = re.findall(r"(?m)^\d+\.\s+(.+)$", practice_match.group(1))
    if not 2 <= len(practice_rows) <= 4:
        raise ValidationError("revision naturalness mini-practice requires two to four items")
    if re.search(r"(?im)^\s*(answer|sample answer|suggested answer)\s*[:：]", practice_match.group(1)):
        raise ValidationError("revision naturalness mini-practice must not reveal answers")


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

    if attempt.get("record_type") == "targeted_drill":
        if not isinstance(feedback, str) or not feedback.strip():
            raise ValidationError("targeted drill feedback is missing")
        if not isinstance(events, list):
            raise ValidationError("writing events must be a list of mappings")
        return

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

    heading_matches = _ordered_heading_matches(
        feedback, require_revision_follow_up=attempt.get("record_type") == "revision"
    )
    if attempt.get("record_type") != "re_evaluation":
        result_block = feedback[heading_matches[0].end():heading_matches[1].start()]
        if (
            "simulated" not in result_block.lower()
            or re.search(rf"(?<!\d){re.escape(str(value))}\s*/\s*5\b", result_block) is None
        ):
            raise ValidationError("first-round feedback result must state the matching simulated task score")
    if attempt.get("record_type") == "revision":
        # ``response`` is intentionally unavailable at this layer. The
        # contextual builder calls the fuller validator before publishing.
        if not feedback.split(FOLLOW_UP_HEADING, 1)[1].strip():
            raise ValidationError("revision naturalness follow-up is empty")
    for heading, start, end in (
        ("why this level", heading_matches[1].end(), heading_matches[2].start()),
        ("why not the next level", heading_matches[2].end(), heading_matches[3].start()),
    ):
        if not feedback[start:end].strip():
            raise ValidationError(f"first-round feedback {heading} is empty")
    evidence_block = feedback[heading_matches[3].end():heading_matches[4].start()]
    priority_block = feedback[
        heading_matches[4].end():heading_matches[5].start()
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
            or excerpt.strip() not in evidence_block
        ):
            raise ValidationError(
                f"evidence section omits counted evidence: {event.get('event_id')}"
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
    if attempt["record_type"] == "revision":
        parent_feedback_path = (
            root
            / "tracker"
            / attempt["modality"]
            / "attempts"
            / attempt["parent_attempt_id"]
            / "feedback-round-1.md"
        )
        parent_feedback = (
            parent_feedback_path.read_text(encoding="utf-8")
            if parent_feedback_path.exists()
            else None
        )
        _validate_revision_follow_up(feedback, response, parent_feedback)
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
        rebuild_modality(root, attempt["modality"])
        write_training_plan(root)
        write_progress_overview(root)
        write_practice_queue(root)
        write_revision_learning(root)
    return destination
