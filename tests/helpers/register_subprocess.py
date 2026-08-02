import os
import sys
from pathlib import Path

from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidatedPracticeRegistration
from toefl_tracker.register import publish_registration


ATTEMPT_ID = "W-AD-KILL-001"


def _registration() -> ValidatedPracticeRegistration:
    prompt = "Crash recovery prompt"
    response = "Crash recovery response"
    attempt = {
        "schema_version": 1,
        "attempt_id": ATTEMPT_ID,
        "modality": "writing",
        "task_type": "academic_discussion",
        "record_type": "formal_original",
        "submitted_at": "2026-08-02T10:00:00+08:00",
        "practiced_at": "2026-08-02",
        "timed": True,
        "duration_seconds": 600,
        "assistance": {"spellcheck": False, "translation": False, "other": None},
        "rubric_version": "ets-writing-discussion-2025-applicable-2026",
        "standard_verified_at": "2026-07-31",
        "task_metrics": {},
        "source_hash": canonical_source_hash(prompt, response),
        "opportunities": {"GRAM-ARTICLE": 1},
        "parent_attempt_id": None,
        "revision_outcomes": None,
        "word_count": 100,
        "task_score": {"scale": "0-5", "value": 3, "confidence": "medium"},
    }
    event = {
        "event_id": "ERR-KILL-001",
        "attempt_id": ATTEMPT_ID,
        "taxonomy_version": 1,
        "code": "GRAM-ARTICLE",
        "source_excerpt": "a crash recovery test",
        "audio_timestamp": None,
        "suggested_revision": "the crash recovery test",
        "reason": "Uses an article fixture.",
        "level": "must_fix",
        "severity": "minor",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }
    return ValidatedPracticeRegistration(
        attempt=attempt,
        prompt=prompt,
        response=response,
        feedback="Crash recovery feedback",
        events=(event,),
    )


def _manifest() -> dict:
    return {
        "rubrics": {
            "ets-writing-discussion-2025-applicable-2026": {
                "task_type": "academic_discussion"
            }
        }
    }


def main(root: Path, point: str) -> None:
    def kill_at_failpoint(name: str) -> None:
        if name == point:
            os._exit(91)

    publish_registration(root, _manifest(), _registration(), failpoint=kill_at_failpoint)


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
