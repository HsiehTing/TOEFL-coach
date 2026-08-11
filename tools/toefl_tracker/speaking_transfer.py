"""Explicit transcript-supported drill-to-new-session transfer for Speaking."""

from hashlib import sha256
from pathlib import Path

from toefl_tracker.io import read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.speaking_practice import validate_persisted_transcript_drill


def _prompt_hash(prompt: str) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValidationError("speaking transfer prompt must be non-empty")
    return "sha256:" + sha256(prompt.encode("utf-8")).hexdigest()


def prepare_speaking_transfer_attempt(
    root: Path,
    attempt: dict,
    prompt: str,
    transcript: str,
    drill_attempt_id: str,
    confirmed_opportunities: object,
    outcomes: object,
) -> dict:
    """Attach auditable transfer lineage without mutating the source drill."""
    if not isinstance(attempt, dict) or attempt.get("modality") != "speaking":
        raise ValidationError("speaking transfer requires a speaking attempt")
    if attempt.get("record_type") != "formal_original":
        raise ValidationError("speaking transfer requires a new formal session")
    if not isinstance(drill_attempt_id, str) or not drill_attempt_id.strip():
        raise ValidationError("speaking transfer requires a drill_attempt_id")
    if not isinstance(confirmed_opportunities, dict):
        raise ValidationError("speaking transfer opportunity confirmation is invalid")
    if not isinstance(transcript, str) or not transcript.strip():
        raise ValidationError("speaking transfer transcript must be non-empty")
    drill_path = root / "tracker/speaking/attempts" / drill_attempt_id / "attempt.yaml"
    if not drill_path.exists():
        raise ValidationError("speaking transfer drill does not exist")
    drill_attempt = read_yaml(drill_path)
    if (
        drill_attempt.get("modality") != "speaking"
        or drill_attempt.get("record_type") != "targeted_drill"
        or drill_attempt.get("task_type") != attempt.get("task_type")
    ):
        raise ValidationError("speaking transfer route or drill lineage does not match")
    drill = drill_attempt.get("drill")
    validate_persisted_transcript_drill(root, attempt["task_type"], drill)
    assert isinstance(drill, dict)
    target_codes = drill["target_codes"]
    if confirmed_opportunities != attempt.get("opportunities"):
        raise ValidationError("speaking transfer opportunity confirmation must match attempt opportunities")
    if set(confirmed_opportunities) != set(target_codes) or any(
        type(value) is not int or value <= 0 for value in confirmed_opportunities.values()
    ):
        raise ValidationError("speaking transfer requires a confirmed opportunity for every target code")
    if not isinstance(outcomes, list) or len(outcomes) != len(target_codes):
        raise ValidationError("speaking transfer requires an outcome for every target code")
    seen_codes = set()
    for outcome in outcomes:
        if (
            not isinstance(outcome, dict)
            or set(outcome) != {"code", "status", "reason", "evidence_excerpt"}
            or outcome.get("code") not in target_codes
            or outcome["code"] in seen_codes
            or outcome.get("status") not in {"meets_target", "partially_meets_target", "needs_revision"}
            or not isinstance(outcome.get("reason"), str) or not outcome["reason"].strip()
            or not isinstance(outcome.get("evidence_excerpt"), str) or not outcome["evidence_excerpt"].strip()
            or outcome["evidence_excerpt"] not in transcript
        ):
            raise ValidationError("speaking transfer outcome is invalid or lacks transcript evidence")
        seen_codes.add(outcome["code"])
    for result in drill["code_results"]:
        if result["correct_count"] / result["item_count"] < drill["minimum_accuracy"]:
            raise ValidationError(
                f"speaking transfer requires drill accuracy of at least {drill['minimum_accuracy']:.0%} for {result['code']}"
            )
    source_id = drill["source_attempt_id"]
    source_dir = root / "tracker/speaking/attempts" / source_id
    source_path = source_dir / "attempt.yaml"
    source_prompt_path = source_dir / "prompt.md"
    if not source_path.exists() or not source_prompt_path.exists():
        raise ValidationError("speaking transfer source session lineage is incomplete")
    source = read_yaml(source_path)
    if (
        source.get("record_type") != "formal_original"
        or source.get("modality") != "speaking"
        or source.get("task_type") != attempt.get("task_type")
    ):
        raise ValidationError("speaking transfer source session does not match")
    source_prompt_hash = _prompt_hash(source_prompt_path.read_text(encoding="utf-8"))
    transfer_prompt_hash = _prompt_hash(prompt)
    if source_prompt_hash == transfer_prompt_hash:
        raise ValidationError("speaking transfer must use a new prompt")
    prepared = dict(attempt)
    prepared["transfer"] = {
        "drill_attempt_id": drill_attempt_id,
        "source_attempt_id": source_id,
        "target_codes": target_codes,
        "opportunity_confirmation": confirmed_opportunities,
        "source_prompt_hash": source_prompt_hash,
        "transfer_prompt_hash": transfer_prompt_hash,
        "outcomes": outcomes,
    }
    return prepared
