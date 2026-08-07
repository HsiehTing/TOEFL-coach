from copy import deepcopy
from pathlib import Path

import pytest

from toefl_tracker.event_validation import SpeakingEvidenceContext, validate_event_context
from toefl_tracker.models import ValidationError


ROOT = Path(__file__).parents[1]


class EventContext:
    def __init__(self) -> None:
        self.attempt = {
            "attempt_id": "W-AD-20260802-001",
            "modality": "writing",
            "task_type": "academic_discussion",
            "record_type": "formal_original",
            "opportunities": {"GRAM-ARTICLE": 1, "EMAIL-REGISTER": 1},
        }
        self.response = "I wrote an answer with a grammar issue."
        self.historical_attempts: list[dict] = []
        self.historical_events: list[dict] = []

    def event(self, **overrides: object) -> dict:
        event = {
            "event_id": "ERR-20260802-001",
            "attempt_id": self.attempt["attempt_id"],
            "taxonomy_version": 1,
            "code": "GRAM-ARTICLE",
            "source_excerpt": "an answer",
            "audio_timestamp": None,
            "suggested_revision": "I wrote a response with a grammar issue.",
            "reason": "Article choice is not idiomatic here.",
            "level": "should_fix",
            "severity": "clarity_reducing",
            "task_specific": False,
            "opportunity_present": True,
            "historical_status": "new",
        }
        event.update(overrides)
        return event

    def args(self, event: dict, **overrides: object) -> dict:
        values = {
            "root": ROOT,
            "attempt": self.attempt,
            "response": self.response,
            "event": event,
            "current_events": [event],
            "historical_attempts": self.historical_attempts,
            "historical_events": self.historical_events,
        }
        values.update(overrides)
        return values


@pytest.fixture
def context() -> EventContext:
    return EventContext()


def test_writing_excerpt_must_occur_in_immutable_response(context: EventContext) -> None:
    event = context.event(source_excerpt="fabricated evidence")
    with pytest.raises(ValidationError, match="excerpt is not present"):
        validate_event_context(**context.args(event))


def test_event_requires_positive_code_opportunity(context: EventContext) -> None:
    context.attempt["opportunities"]["GRAM-ARTICLE"] = 0
    event = context.event()
    with pytest.raises(ValidationError, match="positive opportunity"):
        validate_event_context(**context.args(event))


def test_route_specific_code_cannot_cross_routes(context: EventContext) -> None:
    event = context.event(code="EMAIL-REGISTER", task_specific=True)
    with pytest.raises(ValidationError, match="does not apply to academic_discussion"):
        validate_event_context(**context.args(event))


def test_duplicate_event_id_is_rejected(context: EventContext) -> None:
    event = context.event(event_id="EXISTING")
    existing = deepcopy(event)
    with pytest.raises(ValidationError, match="event_id already exists"):
        validate_event_context(**context.args(event, current_events=[existing]))


def test_stored_status_must_equal_recomputed_status(context: EventContext) -> None:
    event = context.event(historical_status="controlled")
    with pytest.raises(ValidationError, match="historical_status"):
        validate_event_context(**context.args(event))


def test_event_must_bind_to_current_attempt(context: EventContext) -> None:
    event = context.event(attempt_id="W-AD-20260801-999")
    with pytest.raises(ValidationError, match="attempt_id does not match"):
        validate_event_context(**context.args(event))


@pytest.mark.parametrize("field", ["suggested_revision", "reason"])
def test_event_correction_and_reason_must_not_be_blank(
    context: EventContext, field: str
) -> None:
    event = context.event(**{field: "  "})
    with pytest.raises(ValidationError, match=field):
        validate_event_context(**context.args(event))


def speaking_args(context: EventContext, event: dict, evidence: SpeakingEvidenceContext) -> dict:
    context.attempt.update({
        "attempt_id": "S-LR-20260802-001",
        "modality": "speaking",
        "task_type": "listen_and_repeat",
        "opportunities": {"LR-OMISSION": 1},
    })
    event["attempt_id"] = context.attempt["attempt_id"]
    event["code"] = "LR-OMISSION"
    event["task_specific"] = True
    event["source_excerpt"] = ""
    event["audio_timestamp"] = "00:10–00:11"
    return context.args(event, speaking_context=evidence)


def test_counted_speaking_event_requires_timestamp(context: EventContext) -> None:
    event = context.event()
    args = speaking_args(
        context,
        event,
        SpeakingEvidenceContext(
            learner_segments=({"start": 0, "end": 30},),
            duration_seconds=60,
            reliable_dimensions={"reconstruction"},
        ),
    )
    event["audio_timestamp"] = None
    event["source_excerpt"] = "listener transcript evidence"
    with pytest.raises(ValidationError, match="requires a timestamp"):
        validate_event_context(**args)


def test_counted_speaking_event_must_fit_learner_segment(context: EventContext) -> None:
    event = context.event()
    args = speaking_args(
        context,
        event,
        SpeakingEvidenceContext(
            learner_segments=({"start": 0, "end": 10},),
            duration_seconds=60,
            reliable_dimensions={"reconstruction"},
        ),
    )
    with pytest.raises(ValidationError, match="learner segment"):
        validate_event_context(**args)


def test_counted_speaking_event_must_fit_duration(context: EventContext) -> None:
    event = context.event()
    args = speaking_args(
        context,
        event,
        SpeakingEvidenceContext(
            learner_segments=({"start": 0, "end": 60},),
            duration_seconds=10,
            reliable_dimensions={"reconstruction"},
        ),
    )
    with pytest.raises(ValidationError, match="exceeds duration"):
        validate_event_context(**args)


def test_counted_speaking_event_requires_reliable_dimension(context: EventContext) -> None:
    event = context.event()
    args = speaking_args(
        context,
        event,
        SpeakingEvidenceContext(
            learner_segments=({"start": 0, "end": 60},),
            duration_seconds=60,
            reliable_dimensions=set(),
        ),
    )
    with pytest.raises(ValidationError, match="reliable dimension"):
        validate_event_context(**args)


def test_counted_speaking_event_rejects_empty_timestamp_range(context: EventContext) -> None:
    event = context.event()
    args = speaking_args(
        context,
        event,
        SpeakingEvidenceContext(
            learner_segments=({"start": 0, "end": 60},),
            duration_seconds=60,
            reliable_dimensions={"reconstruction"},
        ),
    )
    event["audio_timestamp"] = "00:10–00:10"
    with pytest.raises(ValidationError, match="invalid timestamp range"):
        validate_event_context(**args)


def test_unclassified_still_requires_positive_opportunity(context: EventContext) -> None:
    event = context.event(
        code="UNCLASSIFIED",
        level="polish",
        historical_status=None,
        taxonomy_review_required=True,
    )
    with pytest.raises(ValidationError, match="positive opportunity"):
        validate_event_context(**context.args(event))


def test_valid_context_is_accepted(context: EventContext) -> None:
    event = context.event()
    validate_event_context(**context.args(event))
