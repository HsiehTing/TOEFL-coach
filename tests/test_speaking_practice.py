from pathlib import Path

import pytest
import yaml

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.speaking_practice import (
    finalize_transcript_drill,
    register_transcript_drill,
    validate_persisted_transcript_drill,
    validate_transcript_drill,
)


ROOT = Path(__file__).parents[1]


def test_transcript_drill_accepts_interview_content_but_rejects_audio_claims() -> None:
    drill = {
        "source_attempt_id": "S-INT-001",
        "target_codes": ["INTERVIEW-ELABORATION"],
        "minimum_accuracy": 0.8,
        "item_results": [{
            "item_id": "I01", "code": "INTERVIEW-ELABORATION",
            "status": "partially_meets_target", "reason": "A reason is present but needs a concrete example.",
        }],
    }
    validate_transcript_drill(ROOT, "take_an_interview", drill)

    drill["target_codes"] = ["SPK-PRONUNCIATION"]
    drill["item_results"][0]["code"] = "SPK-PRONUNCIATION"
    with pytest.raises(ValidationError, match="unsupported"):
        validate_transcript_drill(ROOT, "take_an_interview", drill)


def test_transcript_drill_requires_a_result_for_every_target_code() -> None:
    drill = {
        "source_attempt_id": "S-LR-001",
        "target_codes": ["LR-OMISSION", "SPK-GRAMMAR"],
        "minimum_accuracy": 0.8,
        "item_results": [{
            "item_id": "I01", "code": "LR-OMISSION",
            "status": "meets_target", "reason": "The missing word is restored.",
        }],
    }
    with pytest.raises(ValidationError, match="every target"):
        validate_transcript_drill(ROOT, "listen_and_repeat", drill)


def test_speaking_drill_registration_keeps_results_but_no_prompt_or_transcript(tmp_path: Path) -> None:
    source_id = "S-INT-001"
    source = {
        "schema_version": 1,
        "attempt_id": source_id,
        "modality": "speaking",
        "task_type": "take_an_interview",
        "record_type": "formal_original",
        "submitted_at": "2026-08-11T10:00:00+08:00",
        "practiced_at": "2026-08-11",
        "timed": True,
        "duration_seconds": 90,
        "assistance": {"spellcheck": None, "translation": None, "other": None},
        "rubric_version": "ets-speaking-blueprint-2026-diagnostic",
        "standard_verified_at": "2026-08-08",
        "result_type": "diagnostic_only",
        "audio_quality": {"decodable": True, "clipping": False},
        "task_metrics": {},
        "source_hash": canonical_source_hash("source", "source transcript"),
        "opportunities": {"INTERVIEW-ELABORATION": 1},
        "parent_attempt_id": None,
        "revision_outcomes": None,
    }
    source_path = tmp_path / "tracker/speaking/attempts" / source_id
    source_path.mkdir(parents=True)
    (source_path / "attempt.yaml").write_text(yaml.safe_dump(source), encoding="utf-8")
    (source_path / "events.jsonl").write_text("", encoding="utf-8")
    standards = tmp_path / "standards/ets-2026"
    standards.mkdir(parents=True)
    (standards / "manifest.yaml").write_text(
        (ROOT / "standards/ets-2026/manifest.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (standards / "taxonomy.yaml").write_text(
        (ROOT / "standards/ets-2026/taxonomy.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    raw_drill = {
        "source_attempt_id": source_id,
        "target_codes": ["INTERVIEW-ELABORATION"],
        "minimum_accuracy": 0.8,
        "item_results": [{
            "item_id": "I01", "code": "INTERVIEW-ELABORATION",
            "status": "meets_target", "reason": "The answer gives a reason and a concrete example.",
        }],
    }
    attempt = {
        **source,
        "attempt_id": "S-DRILL-001",
        "record_type": "targeted_drill",
        "submitted_at": "2026-08-11T11:00:00+08:00",
        "timed": False,
        "duration_seconds": None,
        "source_hash": "sha256:" + "0" * 64,
        "opportunities": {"INTERVIEW-ELABORATION": 1},
    }

    destination = register_transcript_drill(
        tmp_path,
        read_yaml(standards / "manifest.yaml"),
        attempt,
        raw_drill,
        "Transcript-supported targeted-practice result.",
    )

    persisted = read_yaml(destination / "attempt.yaml")
    assert persisted["drill"] == finalize_transcript_drill(
        tmp_path, "take_an_interview", raw_drill
    )
    validate_persisted_transcript_drill(tmp_path, "take_an_interview", persisted["drill"])
    assert not (destination / "prompt.md").exists()
    assert not (destination / "transcript-original.md").exists()
    assert (destination / "feedback-round-1.md").exists()
    assert (destination / "events.jsonl").read_text(encoding="utf-8") == ""
