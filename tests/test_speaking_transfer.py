from pathlib import Path

import pytest
import yaml

from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.speaking_practice import finalize_transcript_drill
from toefl_tracker.speaking_transfer import prepare_speaking_transfer_attempt


ROOT = Path(__file__).parents[1]


def _attempt(attempt_id: str, record_type: str) -> dict:
    return {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "modality": "speaking",
        "task_type": "take_an_interview",
        "record_type": record_type,
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
        "source_hash": canonical_source_hash("placeholder prompt", attempt_id),
        "opportunities": {"INTERVIEW-ELABORATION": 1},
        "parent_attempt_id": None,
        "revision_outcomes": None,
    }


def _setup_transfer_lineage(tmp_path: Path, status: str = "meets_target") -> tuple[dict, str]:
    standards = tmp_path / "standards/ets-2026"
    standards.mkdir(parents=True)
    (standards / "taxonomy.yaml").write_text(
        (ROOT / "standards/ets-2026/taxonomy.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    source_id = "S-INT-001"
    source_dir = tmp_path / "tracker/speaking/attempts" / source_id
    source_dir.mkdir(parents=True)
    (source_dir / "attempt.yaml").write_text(
        yaml.safe_dump(_attempt(source_id, "formal_original")), encoding="utf-8"
    )
    source_prompt = "Describe a memorable challenge and how you handled it."
    (source_dir / "prompt.md").write_text(source_prompt, encoding="utf-8")
    raw_drill = {
        "source_attempt_id": source_id,
        "target_codes": ["INTERVIEW-ELABORATION"],
        "minimum_accuracy": 0.8,
        "item_results": [{
            "item_id": "I01", "code": "INTERVIEW-ELABORATION", "status": status,
            "reason": "The response is reviewed against the elaboration target.",
        }],
    }
    drill_attempt = _attempt("S-DRILL-001", "targeted_drill")
    drill_attempt["drill"] = finalize_transcript_drill(
        tmp_path, "take_an_interview", raw_drill
    )
    drill_attempt["source_hash"] = drill_attempt["drill"]["result_hash"]
    drill_dir = tmp_path / "tracker/speaking/attempts/S-DRILL-001"
    drill_dir.mkdir()
    (drill_dir / "attempt.yaml").write_text(yaml.safe_dump(drill_attempt), encoding="utf-8")
    return _attempt("S-INT-TRANSFER-001", "formal_original"), source_prompt


def test_speaking_transfer_requires_passed_drill_new_prompt_and_opportunities(tmp_path: Path) -> None:
    attempt, source_prompt = _setup_transfer_lineage(tmp_path)
    transcript = "I helped my teammate by creating a clear plan and checking in every day."
    outcomes = [{
        "code": "INTERVIEW-ELABORATION", "status": "meets_target",
        "reason": "The response gives both a reason and a specific action.",
        "evidence_excerpt": "creating a clear plan",
    }]
    prepared = prepare_speaking_transfer_attempt(
        tmp_path,
        attempt,
        "Tell me about a time you helped a teammate succeed.",
        transcript,
        "S-DRILL-001",
        {"INTERVIEW-ELABORATION": 1},
        outcomes,
    )

    assert prepared["transfer"]["source_attempt_id"] == "S-INT-001"
    assert prepared["transfer"]["target_codes"] == ["INTERVIEW-ELABORATION"]
    with pytest.raises(ValidationError, match="new prompt"):
        prepare_speaking_transfer_attempt(
            tmp_path, attempt, source_prompt, transcript, "S-DRILL-001",
            {"INTERVIEW-ELABORATION": 1}, outcomes,
        )
    with pytest.raises(ValidationError, match="opportunity confirmation"):
        prepare_speaking_transfer_attempt(
            tmp_path, attempt, "A different prompt.", transcript, "S-DRILL-001",
            {"INTERVIEW-ELABORATION": 0}, outcomes,
        )
    with pytest.raises(ValidationError, match="lacks transcript evidence"):
        prepare_speaking_transfer_attempt(
            tmp_path, attempt, "A different prompt.", transcript, "S-DRILL-001",
            {"INTERVIEW-ELABORATION": 1}, [{**outcomes[0], "evidence_excerpt": "not in transcript"}],
        )


def test_speaking_transfer_rejects_drill_below_its_per_code_threshold(tmp_path: Path) -> None:
    attempt, _ = _setup_transfer_lineage(tmp_path, status="needs_revision")

    with pytest.raises(ValidationError, match="drill accuracy"):
        prepare_speaking_transfer_attempt(
            tmp_path,
            attempt,
            "Tell me about a time you helped a teammate succeed.",
            "I helped my teammate by creating a clear plan.",
            "S-DRILL-001",
            {"INTERVIEW-ELABORATION": 1},
            [{
                "code": "INTERVIEW-ELABORATION", "status": "needs_revision",
                "reason": "The response needs more detail.",
                "evidence_excerpt": "creating a clear plan",
            }],
        )
