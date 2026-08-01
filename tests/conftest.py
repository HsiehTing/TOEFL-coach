import shutil
from pathlib import Path

import pytest

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.register import register_attempt
from toefl_tracker.speaking import register_speaking_session


ROOT = Path(__file__).parents[1]


def make_attempt(
    modality: str,
    task_type: str,
    attempt_id: str,
    day: int,
    record_type: str = "formal_original",
    parent_attempt_id: str | None = None,
) -> tuple[dict, str, str]:
    prompt = f"Fixture prompt {attempt_id}"
    response = f"Fixture response {attempt_id}"
    rubric = (
        "ets-writing-discussion-2025-applicable-2026"
        if modality == "writing"
        else "ets-speaking-blueprint-2026-diagnostic"
    )
    attempt = {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "modality": modality,
        "task_type": task_type,
        "record_type": record_type,
        "submitted_at": f"2026-01-{day:02d}T10:00:00+08:00",
        "practiced_at": f"2026-01-{day:02d}",
        "timed": True,
        "duration_seconds": 600 if modality == "writing" else 120,
        "assistance": {"spellcheck": False, "translation": False, "other": None},
        "rubric_version": rubric,
        "standard_verified_at": "2026-07-31",
        "task_metrics": {},
        "source_hash": canonical_source_hash(prompt, response),
        "opportunities": (
            {"GRAM-ARTICLE": 1}
            if modality == "writing"
            else {"SPK-FLUENCY": 1}
        ),
        "parent_attempt_id": parent_attempt_id,
        "revision_outcomes": (
            {
                "assigned": 2,
                "resolved": 1,
                "partly_resolved": 1,
                "unresolved": 0,
                "new_errors": 0,
                "resolution_rate": 0.5,
            }
            if record_type == "revision"
            else None
        ),
    }
    if modality == "writing":
        attempt["word_count"] = 100
        attempt["task_score"] = {"scale": "0-5", "value": 3, "confidence": "medium"}
    else:
        attempt["result_type"] = "diagnostic_only"
        attempt["audio_quality"] = {"decodable": True, "clipping": False}
    return attempt, prompt, response


def fluency_event(attempt_id: str, event_id: str, status: str) -> dict:
    return {
        "event_id": event_id,
        "attempt_id": attempt_id,
        "taxonomy_version": 1,
        "code": "SPK-FLUENCY",
        "source_excerpt": "",
        "audio_timestamp": "00:13–00:14",
        "suggested_revision": "Repeat the answer with one planned pause.",
        "reason": "Repeated repairs interrupt connected speech.",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": status,
    }


def speaking_segments(task_type: str) -> list[dict]:
    count = 7 if task_type == "listen_and_repeat" else 4
    rows = []
    for item in range(1, count + 1):
        rows.extend([
            {
                "item": item,
                "role": "examiner",
                "start": item * 10.0,
                "end": item * 10.0 + 2.0,
                "confidence": "high",
            },
            {
                "item": item,
                "role": "learner",
                "start": item * 10.0 + 2.2,
                "end": item * 10.0 + 7.0,
                "confidence": "high",
            },
        ])
    return rows


SPEAKING_FEEDBACK = """# Result
Diagnostic only.
# Why this level
Fixture evidence.
# Why not the next level
Fixture evidence.
# Timestamp evidence
00:13–00:14 repeated repair.
# Priorities
1. Reduce repeated repair.
# Re-record task
Re-record the affected item.
"""


def inspection(attempt_id: str) -> dict:
    return {
        "path": f"/private/source/{attempt_id}.m4a",
        "duration_seconds": 120.0,
        "codec": "aac",
        "sample_rate_hz": 48000,
        "channels": 1,
        "mean_dbfs": -30.0,
        "peak_dbfs": -5.4,
        "clipping": False,
        "decodable": True,
    }


@pytest.fixture
def populated_workspace(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "standards", tmp_path / "standards")
    manifest = read_yaml(tmp_path / "standards/ets-2026/manifest.yaml")

    writing_rows = [
        make_attempt("writing", "academic_discussion", "W-AD-20260101-001", 1),
        make_attempt("writing", "academic_discussion", "W-AD-20260102-002", 2),
        make_attempt(
            "writing",
            "academic_discussion",
            "W-AD-20260102-002-R1",
            3,
            record_type="revision",
            parent_attempt_id="W-AD-20260102-002",
        ),
        make_attempt("writing", "academic_discussion", "W-AD-20260104-003", 4),
    ]
    for attempt, prompt, response in writing_rows:
        register_attempt(tmp_path, manifest, attempt, prompt, response, "Fixture feedback", [])

    speaking_rows = [
        make_attempt("speaking", "listen_and_repeat", "S-LR-20260105-001", 5),
        make_attempt("speaking", "listen_and_repeat", "S-LR-20260106-002", 6),
        make_attempt("speaking", "listen_and_repeat", "S-LR-20260107-003", 7),
        make_attempt("speaking", "take_an_interview", "S-INT-20260108-001", 8),
        make_attempt("speaking", "take_an_interview", "S-INT-20260109-002", 9),
        make_attempt("speaking", "take_an_interview", "S-INT-20260110-003", 10),
    ]
    for index, (attempt, prompt, response) in enumerate(speaking_rows):
        events = []
        if index == 0:
            events = [fluency_event(attempt["attempt_id"], "S-E-001", "new")]
        if index == 4:
            events = [fluency_event(attempt["attempt_id"], "S-E-002", "relapsed")]
        register_speaking_session(
            tmp_path,
            manifest,
            attempt,
            prompt,
            response,
            SPEAKING_FEEDBACK,
            events,
            speaking_segments(attempt["task_type"]),
            inspection(attempt["attempt_id"]),
        )

    duplicate, prompt, response = speaking_rows[0]
    with pytest.raises(ValidationError, match="attempt_id already exists"):
        register_speaking_session(
            tmp_path,
            manifest,
            duplicate,
            prompt,
            response,
            SPEAKING_FEEDBACK,
            [],
            speaking_segments(duplicate["task_type"]),
            inspection(duplicate["attempt_id"]),
        )

    return tmp_path
