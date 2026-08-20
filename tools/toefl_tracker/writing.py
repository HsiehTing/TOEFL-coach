import re
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import datetime
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
    validate_practice_context,
)
from toefl_tracker.io import read_yaml
from toefl_tracker.lineage import revision_chain, root_formal_attempt
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
DRILL_HEADING = "# Targeted drill"
NO_ISSUE_MESSAGE = "No naturalness or precision issue to flag."
DRILL_STATUSES = {"not_required_yet", "skipped", "required", "declined", "completed"}


def _ordered_heading_matches(
    feedback: str, *, revision: bool = False
) -> list[Match[str]]:
    matches = list(
        re.finditer(r"(?m)^(# [^\r\n]+?)[ \t]*\r?$", feedback)
    )
    headings = tuple(match.group(1) for match in matches)
    allowed = (
        (
            REQUIRED_HEADINGS + (DRILL_HEADING,),
            REQUIRED_HEADINGS + (DRILL_HEADING, FOLLOW_UP_HEADING),
        )
        if revision
        else (REQUIRED_HEADINGS,)
    )
    if headings not in allowed:
        raise ValidationError(
            "first-round feedback headings are missing, duplicated, or out of order"
        )
    return matches


def _full_resolution(outcomes: object) -> bool:
    return bool(
        isinstance(outcomes, Mapping)
        and outcomes.get("assigned", 0) > 0
        and outcomes.get("resolved") == outcomes.get("assigned")
        and outcomes.get("partly_resolved") == 0
        and outcomes.get("unresolved") == 0
    )


def _section(feedback: str, heading: str) -> str:
    matches = list(re.finditer(r"(?m)^(# [^\r\n]+?)[ \t]*\r?$", feedback))
    for index, match in enumerate(matches):
        if match.group(1) != heading:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(feedback)
        return feedback[match.end():end].strip()
    return ""


def _drill_status(feedback: str) -> str:
    block = _section(feedback, DRILL_HEADING)
    match = re.search(r"(?m)^Drill status:\s*`([^`]+)`\.\s*$", block)
    if match is None or match.group(1) not in DRILL_STATUSES:
        raise ValidationError("revision feedback requires a valid targeted drill status")
    return match.group(1)


def _validate_drill_invitation(drill_block: str) -> None:
    """Require a durable record that choice followed learner-specific guidance."""
    invitation = re.search(
        r"(?im)^Invitation:\s*After reviewing the exact-excerpt feedback and bounded rewrite direction, "
        r"learner was asked whether to start this targeted drill\.\s*$",
        drill_block,
    )
    if invitation is None:
        raise ValidationError(
            "learner-directed targeted drill must record the invitation after exact-excerpt feedback and rewrite direction"
        )


def _validate_no_issue_audit(follow_up: str, response: str) -> None:
    audit = re.search(
        r"(?ms)^## Naturalness audit\s*$\n(.*?)(?=^## |\Z)", follow_up
    )
    transfer = re.search(
        r"(?ms)^## Transfer suggestion\s*$\n(.*?)(?=^## |\Z)", follow_up
    )
    if audit is None or transfer is None or not transfer.group(1).strip():
        raise ValidationError(
            "no-issue follow-up requires a naturalness audit and transfer suggestion"
        )
    candidates = re.findall(
        r"(?m)^\d+\.\s+Candidate:\s*`([^`]+)`\s*[—-]\s*(.+)$",
        audit.group(1),
    )
    if not 1 <= len(candidates) <= 3:
        raise ValidationError("no-issue follow-up requires one to three audited candidates")
    excerpts = [excerpt for excerpt, _ in candidates]
    if len(set(excerpts)) != len(excerpts) or any(
        excerpt not in response for excerpt in excerpts
    ):
        raise ValidationError("no-issue audit candidates must be distinct learner text")


def _validate_material_issue_audit(evidence_block: str) -> None:
    audit = re.search(r"(?ms)^## Material issue audit\s*$\n(.*?)(?=^## |\Z)", evidence_block)
    if audit is None:
        raise ValidationError(
            "first-round evidence requires a complete material-issue audit"
        )
    body = audit.group(1)
    if re.search(r"(?im)^Status:\s*complete\s*$", body) is None:
        raise ValidationError("material-issue audit must state Status: complete")
    if re.search(
        r"(?im)^Scope:\s*all material issues in the submitted response are disclosed",
        body,
    ) is None:
        raise ValidationError(
            "material-issue audit must disclose the full submitted-response scope"
        )


def _validate_concrete_transfer_suggestion(follow_up: str) -> None:
    transfer = re.search(
        r"(?ms)^## Transfer suggestion\s*$\n(.*?)(?=^## |\Z)",
        follow_up,
    )
    if transfer is None or not transfer.group(1).strip():
        raise ValidationError(
            "naturalness follow-up requires a concrete transfer suggestion"
        )
    activity = re.search(r"(?im)^Activity:\s*(.+)$", transfer.group(1))
    if activity is None or not activity.group(1).strip():
        raise ValidationError("transfer suggestion must include a concrete Activity")
    activity_text = activity.group(1).lower()
    if not re.search(r"\bnew\b.*\bprompt\b", activity_text) or not re.search(
        r"\b(write|respond|answer)\b", activity_text
    ):
        raise ValidationError(
            "transfer Activity must name a new prompt and learner action"
        )


def _validate_revision_follow_up(
    feedback: str, response: str, parent_feedback: str | None = None
) -> None:
    """Validate the required non-scoring coaching artifact on a revision.

    The coach writes this prose, but the registration gate protects its key
    boundaries: it must remain after the ordinary assessment, cite the learner's
    actual revision, and stay bounded. It deliberately does not create events,
    learner exercises, or any tracker state.
    """
    if FOLLOW_UP_HEADING not in feedback:
        raise ValidationError("revision feedback requires naturalness follow-up")
    follow_up = feedback.split(FOLLOW_UP_HEADING, 1)[1].strip()
    if not follow_up:
        raise ValidationError("revision naturalness follow-up is empty")
    if re.search(r"(?m)^## Mini-practice\s*$", follow_up):
        raise ValidationError(
            "revision naturalness follow-up must not contain mini-practice; "
            "learner exercises belong to targeted drills"
        )
    if re.search(rf"(?m)^{re.escape(NO_ISSUE_MESSAGE)}\s*$", follow_up):
        _validate_no_issue_audit(follow_up, response)
        _validate_concrete_transfer_suggestion(follow_up)
        return

    suggestions = re.findall(r"(?m)^\d+\.\s+Excerpt:\s*`([^`]+)`", follow_up)
    if not 1 <= len(suggestions) <= 3:
        raise ValidationError("revision naturalness follow-up requires one to three excerpt suggestions")
    if len(set(suggestions)) != len(suggestions) or any(excerpt not in response for excerpt in suggestions):
        raise ValidationError("revision naturalness follow-up excerpts must be distinct learner text")
    evidence_block = _section(feedback, "# Evidence")
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
    _validate_concrete_transfer_suggestion(follow_up)
def _historical_attempts(root: Path) -> list[dict]:
    base = root / "tracker" / "writing" / "attempts"
    rows = [
        read_yaml(path / "attempt.yaml")
        for path in base.glob("*")
        if path.is_dir() and not path.name.startswith(".")
    ] if base.exists() else []
    rows.sort(key=lambda row: (str(row.get("submitted_at", "")), str(row.get("attempt_id", ""))))
    return rows


def _completed_drill_after_second_revision(
    root_attempt_id: str, prior_revisions: Sequence[dict], attempts: Sequence[dict]
) -> dict | None:
    if len(prior_revisions) < 2:
        return None
    second_submitted = datetime.fromisoformat(prior_revisions[1]["submitted_at"])
    candidates = []
    for row in attempts:
        drill = row.get("drill")
        if (
            row.get("record_type") != "targeted_drill"
            or not isinstance(drill, Mapping)
            or root_attempt_id not in drill.get("source_attempt_ids", [])
            or type(drill.get("item_count")) is not int
            or type(drill.get("correct_count")) is not int
        ):
            continue
        submitted = datetime.fromisoformat(row["submitted_at"])
        if submitted > second_submitted:
            candidates.append(row)
    return max(candidates, key=lambda row: row["submitted_at"], default=None)


def validate_writing_revision_context(
    root: Path, registration: ValidatedPracticeRegistration
) -> None:
    """Validate revision → conditional drill → follow-up while state is locked."""
    attempt = registration.attempt
    if attempt.get("record_type") != "revision":
        return

    historical = _historical_attempts(root)
    lineage_rows = [*historical, attempt]
    root_attempt = root_formal_attempt(attempt["attempt_id"], lineage_rows)
    root_id = root_attempt["attempt_id"]
    prior_revisions = revision_chain(root_id, historical)
    round_number = len(prior_revisions) + 1
    completed = _full_resolution(attempt.get("revision_outcomes"))
    completed_drill = _completed_drill_after_second_revision(
        root_id, prior_revisions, historical
    )

    if round_number >= 3 and completed_drill is None:
        raise ValidationError(
            "third revision requires a completed targeted drill after revision round 2"
        )

    expected_status = (
        "completed"
        if round_number >= 3
        else "skipped"
        if completed
        else "required"
        if round_number == 2
        else "not_required_yet"
    )
    actual_status = _drill_status(registration.feedback)
    allowed_statuses = (
        {"required", "declined"}
        if expected_status == "required"
        else {expected_status}
    )
    if actual_status not in allowed_statuses:
        raise ValidationError(
            f"targeted drill status must be one of {sorted(allowed_statuses)} for revision round {round_number}"
        )

    drill_block = _section(registration.feedback, DRILL_HEADING)
    if actual_status == "required":
        _validate_drill_invitation(drill_block)
        if re.search(r"(?im)^Decision:\s*learner opted in", drill_block) is None:
            raise ValidationError("required targeted drill must record the learner opt-in")
        source = re.search(r"(?m)^Source:\s*`([^`]+)`\s*$", drill_block)
        targets = re.search(r"(?m)^Targets:\s*(.+)$", drill_block)
        items = re.search(r"(?m)^Items:\s*([1-9][0-9]*)\s*$", drill_block)
        completion = re.search(r"(?m)^Completion:\s*(.+)$", drill_block)
        target_codes = re.findall(r"`([^`]+)`", targets.group(1)) if targets else []
        chain_opportunities = {
            code
            for row in [root_attempt, *prior_revisions, attempt]
            for code, count in row.get("opportunities", {}).items()
            if type(count) is int and count > 0
        }
        if (
            source is None
            or source.group(1) != root_id
            or not 1 <= len(target_codes) <= 2
            or len(set(target_codes)) != len(target_codes)
            or any(code not in chain_opportunities for code in target_codes)
            or items is None
            or not 1 <= int(items.group(1)) <= 8
            or completion is None
        ):
            raise ValidationError(
                "required targeted drill must list a valid source, one or two lineage targets, one to eight items, and completion"
            )
    elif actual_status == "declined":
        _validate_drill_invitation(drill_block)
        if re.search(r"(?im)^Decision:\s*learner declined", drill_block) is None:
            raise ValidationError("declined targeted drill must record the learner decision")
    elif actual_status in {"skipped", "not_required_yet"}:
        if re.search(r"(?im)^Reason:.*third revision", drill_block) is None:
            raise ValidationError("non-required targeted drill must explain the third-revision gate")
    else:
        drill_attempt = re.search(r"(?m)^Drill attempt:\s*`([^`]+)`\s*$", drill_block)
        if drill_attempt is None or drill_attempt.group(1) != completed_drill["attempt_id"]:
            raise ValidationError("completed targeted drill must cite the persisted drill attempt")

    has_follow_up = bool(_section(registration.feedback, FOLLOW_UP_HEADING))
    follow_up_required = completed or actual_status == "declined"
    if follow_up_required and not has_follow_up:
        raise ValidationError("completed revision requires naturalness follow-up")
    if not follow_up_required and FOLLOW_UP_HEADING in registration.feedback:
        raise ValidationError("incomplete revision must not enter naturalness follow-up")
    if follow_up_required:
        parent_path = (
            root
            / "tracker"
            / "writing"
            / "attempts"
            / attempt["parent_attempt_id"]
            / "feedback-round-1.md"
        )
        parent_feedback = parent_path.read_text(encoding="utf-8") if parent_path.exists() else None
        _validate_revision_follow_up(
            registration.feedback, registration.response, parent_feedback
        )


def validate_writing_assessment(
    attempt: dict,
    events: list[dict],
    feedback: str,
    *,
    require_material_issue_audit: bool = False,
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

    is_revision = attempt.get("record_type") == "revision"
    heading_matches = _ordered_heading_matches(feedback, revision=is_revision)
    if attempt.get("record_type") != "re_evaluation":
        result_block = feedback[heading_matches[0].end():heading_matches[1].start()]
        if (
            "simulated" not in result_block.lower()
            or re.search(rf"(?<!\d){re.escape(str(value))}\s*/\s*5\b", result_block) is None
        ):
            raise ValidationError("first-round feedback result must state the matching simulated task score")
    if is_revision:
        _drill_status(feedback)
        completed = _full_resolution(attempt.get("revision_outcomes"))
        actual_status = _drill_status(feedback)
        has_follow_up = FOLLOW_UP_HEADING in feedback
        follow_up_required = completed or actual_status == "declined"
        if follow_up_required and not has_follow_up:
            raise ValidationError("completed revision requires naturalness follow-up")
        if not follow_up_required and has_follow_up:
            raise ValidationError("incomplete revision must not enter naturalness follow-up")
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
    if (
        require_material_issue_audit
        and attempt.get("record_type") == "formal_original"
    ):
        _validate_material_issue_audit(evidence_block)


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
    validate_writing_assessment(
        attempt,
        list(event_rows),
        feedback,
        require_material_issue_audit=True,
    )
    # This preflight gives direct builder callers the same error they would see
    # during publication. publish_registration repeats it while locked.
    registration = ValidatedPracticeRegistration(
        attempt=attempt,
        prompt=prompt,
        response=response,
        feedback=feedback,
        events=event_rows,
        require_contextual_validation=True,
    )
    with _registration_lock(root):
        validate_practice_context(root, registration)
    return registration


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
