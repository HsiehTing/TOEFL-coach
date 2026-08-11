from pathlib import Path
import json

import pytest
import yaml

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.speaking_revision import (
    register_transcript_rerecording,
    validate_transcript_rerecording,
)


ROOT = Path(__file__).parents[1]


def _revision() -> dict:
    return {
        "parent_attempt_id": "S-LR-001",
        "scope": "partial",
        "target_codes": ["LR-OMISSION"],
        "source_event_ids": ["ERR-S-LR-001-01"],
        "items": [{
            "item_id": 2,
            "prompt_excerpt": "The library opens at eight.",
            "learner_transcript": "The library opens at eight every weekday.",
        }],
        "outcomes": [{
            "code": "LR-OMISSION",
            "item_ids": [2],
            "status": "meets_target",
            "reason": "The omitted time expression is now present.",
            "evidence_excerpt": "opens at eight",
        }],
    }


def test_transcript_rerecording_requires_parent_item_pairing_and_evidence() -> None:
    revision = _revision()
    validate_transcript_rerecording(ROOT, "listen_and_repeat", revision)

    revision["outcomes"][0]["evidence_excerpt"] = "not supplied"
    with pytest.raises(ValidationError, match="lacks transcript evidence"):
        validate_transcript_rerecording(ROOT, "listen_and_repeat", revision)


def test_transcript_rerecording_rejects_audio_claims_and_incomplete_complete_scope() -> None:
    revision = _revision()
    revision["target_codes"] = ["SPK-PRONUNCIATION"]
    revision["outcomes"][0]["code"] = "SPK-PRONUNCIATION"
    with pytest.raises(ValidationError, match="unsupported"):
        validate_transcript_rerecording(ROOT, "listen_and_repeat", revision)

    revision = _revision()
    revision["scope"] = "complete"
    with pytest.raises(ValidationError, match="every item"):
        validate_transcript_rerecording(ROOT, "listen_and_repeat", revision)


def test_rerecording_registration_persists_a_revision_without_formal_session_artifacts(tmp_path: Path) -> None:
    standards = tmp_path / "standards/ets-2026"
    standards.mkdir(parents=True)
    for name in ("manifest.yaml", "taxonomy.yaml"):
        (standards / name).write_text((ROOT / "standards/ets-2026" / name).read_text(encoding="utf-8"), encoding="utf-8")
    parent_id = "S-LR-001"
    parent = {
        "schema_version": 1, "attempt_id": parent_id, "modality": "speaking",
        "task_type": "listen_and_repeat", "record_type": "formal_original",
        "submitted_at": "2026-08-11T10:00:00+08:00", "practiced_at": "2026-08-11",
        "timed": True, "duration_seconds": 120,
        "assistance": {"spellcheck": None, "translation": None, "other": None},
        "rubric_version": "ets-speaking-blueprint-2026-diagnostic", "standard_verified_at": "2026-08-08",
        "result_type": "diagnostic_only", "audio_quality": {"decodable": True, "clipping": False},
        "task_metrics": {}, "source_hash": canonical_source_hash("source", "source transcript"),
        "opportunities": {"LR-OMISSION": 1}, "parent_attempt_id": None, "revision_outcomes": None,
    }
    parent_dir = tmp_path / "tracker/speaking/attempts" / parent_id
    parent_dir.mkdir(parents=True)
    (parent_dir / "attempt.yaml").write_text(yaml.safe_dump(parent), encoding="utf-8")
    parent_event = {
        "event_id": "ERR-S-LR-001-01", "attempt_id": parent_id, "taxonomy_version": 1,
        "code": "LR-OMISSION", "source_excerpt": None, "audio_timestamp": "00:10",
        "suggested_revision": "Restore the omitted word.", "reason": "A word is missing.",
        "level": "should_fix", "severity": "clarity_reducing", "task_specific": True,
        "opportunity_present": True, "historical_status": "new",
    }
    (parent_dir / "events.jsonl").write_text(json.dumps(parent_event) + "\n", encoding="utf-8")
    attempt = {
        **parent,
        "attempt_id": "S-LR-001-R1", "record_type": "revision",
        "submitted_at": "2026-08-11T11:00:00+08:00", "parent_attempt_id": parent_id,
        "source_hash": "sha256:" + "0" * 64, "revision_outcomes": None,
    }
    path = register_transcript_rerecording(
        tmp_path,
        read_yaml(standards / "manifest.yaml"),
        attempt,
        _revision(),
        "Transcript-supported re-recording result.",
    )

    persisted = read_yaml(path / "attempt.yaml")
    assert persisted["record_type"] == "revision"
    assert persisted["revision_outcomes"] is None
    assert (path / "re-recording.yaml").exists()
    assert (path / "transcript-revision.md").exists()
    assert not (path / "audio-inspection.json").exists()
