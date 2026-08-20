"""Build an executable, non-scored Writing practice queue from current evidence."""

from collections import defaultdict
from pathlib import Path
import re

import yaml

from toefl_tracker.canonical import load_canonical_events
from toefl_tracker.drill_generation import writing_drill_support_status
from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.legacy_migration import load_legacy_compatibility, synthetic_sort_key
from toefl_tracker.lineage import revision_chain
from toefl_tracker.progress import build_progress_overview
from toefl_tracker.training_plan import build_training_plan


_COUNTED = {"must_fix", "should_fix"}


def _formals(root: Path) -> list[dict]:
    attempts_root = root / "tracker/writing/attempts"
    attempts = [read_yaml(path) for path in attempts_root.glob("*/attempt.yaml")] if attempts_root.exists() else []
    compatibility = load_legacy_compatibility(root, "writing")
    return [
        attempt
        for attempt in sorted(attempts, key=lambda row: synthetic_sort_key(compatibility, row))
        if attempt.get("record_type") == "formal_original"
    ]


def _writing_attempts(root: Path) -> list[dict]:
    attempts_root = root / "tracker/writing/attempts"
    rows = [read_yaml(path) for path in attempts_root.glob("*/attempt.yaml")] if attempts_root.exists() else []
    compatibility = load_legacy_compatibility(root, "writing")
    return sorted(rows, key=lambda row: synthetic_sort_key(compatibility, row))


def _is_fully_resolved(outcomes: object) -> bool:
    return bool(
        isinstance(outcomes, dict)
        and outcomes.get("assigned", 0) > 0
        and outcomes.get("resolved") == outcomes.get("assigned")
        and outcomes.get("partly_resolved") == 0
        and outcomes.get("unresolved") == 0
    )


def _learner_drill_choice(root: Path, source_attempt_id: str) -> str | None:
    """Return the recorded R2 decision, without inferring consent from silence.

    A training plan can be derived from older records that predate learner-choice
    tracking.  Those records stay intact, but a queue may only offer generation
    after it finds an explicit opt-in in the latest incomplete second revision.
    """
    attempts = _writing_attempts(root)
    compatibility = load_legacy_compatibility(root, "writing")
    revisions = revision_chain(source_attempt_id, attempts, compatibility=compatibility)
    if len(revisions) < 2 or _is_fully_resolved(revisions[-1].get("revision_outcomes")):
        return None

    feedback_path = (
        root / "tracker/writing/attempts" / revisions[-1]["attempt_id"] / "feedback-round-1.md"
    )
    if not feedback_path.exists():
        return "awaiting"
    feedback = feedback_path.read_text(encoding="utf-8")
    if re.search(r"(?im)^Drill status:\s*`declined`\.\s*$", feedback):
        if re.search(r"(?im)^Decision:\s*learner declined", feedback):
            return "declined"
        return "awaiting"
    if re.search(r"(?im)^Drill status:\s*`required`\.\s*$", feedback):
        if re.search(r"(?im)^Decision:\s*learner opted in", feedback):
            return "opted_in"
        return "awaiting"
    return "awaiting"


def _latest_matching_drill(
    root: Path, source_attempt_id: str, task_type: str, target_codes: list[str]
) -> dict | None:
    attempts_root = root / "tracker/writing/attempts"
    rows = [
        read_yaml(path)
        for path in attempts_root.glob("*/attempt.yaml")
        if attempts_root.exists()
    ] if attempts_root.exists() else []
    matches = []
    source_drills = []
    expected = set(target_codes)
    for row in rows:
        metadata = row.get("drill") if row.get("record_type") == "targeted_drill" else None
        if (
            row.get("task_type") == task_type
            and isinstance(metadata, dict)
        ):
            if metadata.get("source_attempt_ids") == [source_attempt_id]:
                source_drills.append(row)
                if set(metadata.get("target_codes", [])) == expected:
                    matches.append(row)
    if matches:
        return max(matches, key=lambda row: (row.get("submitted_at", ""), row.get("attempt_id", "")))
    if source_drills:
        legacy = max(source_drills, key=lambda row: (row.get("submitted_at", ""), row.get("attempt_id", ""))).copy()
        legacy["_queue_match"] = False
        return legacy
    return None


def _drill_status(drill: dict | None) -> tuple[str, str]:
    if drill is None:
        return "ready", "No completed drill is linked to this target yet."
    if drill.get("_queue_match") is False:
        return "blocked_by_pack_drift", "A prior drill uses a different target-code set; generate the current plan's pack."
    metadata = drill.get("drill", {})
    item_count = metadata.get("item_count")
    correct_count = metadata.get("correct_count")
    minimum_accuracy = metadata.get("minimum_accuracy", 0.8)
    if (
        type(item_count) is not int
        or item_count <= 0
        or type(correct_count) is not int
        or not 0 <= correct_count <= item_count
        or type(minimum_accuracy) not in {int, float}
        or not 0 < minimum_accuracy <= 1
    ):
        return "blocked_by_incomplete_assessment", "The drill result lacks valid item-level accuracy metadata."
    code_results = metadata.get("code_results")
    if code_results is not None:
        target_codes = metadata.get("target_codes")
        if not isinstance(code_results, list) or not isinstance(target_codes, list):
            return "blocked_by_incomplete_assessment", "The drill result lacks valid per-code accuracy metadata."
        by_code = {
            row.get("code"): row
            for row in code_results
            if isinstance(row, dict) and isinstance(row.get("code"), str)
        }
        if set(by_code) != set(target_codes):
            return "blocked_by_incomplete_assessment", "The drill result lacks valid per-code accuracy metadata."
        for code in target_codes:
            result = by_code[code]
            code_items = result.get("item_count")
            code_correct = result.get("correct_count")
            if (
                type(code_items) is not int
                or code_items <= 0
                or type(code_correct) is not int
                or not 0 <= code_correct <= code_items
            ):
                return "blocked_by_incomplete_assessment", "The drill result lacks valid per-code accuracy metadata."
            code_accuracy = code_correct / code_items
            if code_accuracy < minimum_accuracy:
                return (
                    "blocked_by_accuracy",
                    f"{code} accuracy is {code_accuracy:.0%}; reach {minimum_accuracy:.0%} for every target before transfer.",
                )
    accuracy = correct_count / item_count
    if accuracy < minimum_accuracy:
        return "blocked_by_accuracy", f"Accuracy is {accuracy:.0%}; reach {minimum_accuracy:.0%} before transfer."
    return "completed", f"Accuracy is {accuracy:.0%}; every target meets the drill threshold."


def _transfer_status(drill: dict) -> tuple[str, str]:
    status, reason = _drill_status(drill)
    if status == "completed":
        return "ready", "The drill threshold is met; a new prompt can be used for transfer."
    if status in {"blocked_by_accuracy", "blocked_by_pack_drift"}:
        return status, reason
    return "blocked_by_incomplete_assessment", reason


def build_practice_queue(root: Path) -> dict:
    """Show every active training plan, with a fallback for early history."""
    overview = build_progress_overview(root)
    formals = _formals(root)
    events = load_canonical_events(root, "writing") if formals else []
    order = {attempt["attempt_id"]: index for index, attempt in enumerate(formals)}
    by_id = {attempt["attempt_id"]: attempt for attempt in formals}
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    sources: dict[tuple[str, str], str] = {}
    deferred: list[dict] = []
    for focus in overview["next_focuses"]:
        code = focus["code"]
        candidates = [
            event for event in events
            if event.get("code") == code
            and event.get("level") in _COUNTED
            and event.get("attempt_id") in by_id
        ]
        if not candidates:
            continue
        source_id = max(candidates, key=lambda event: order[event["attempt_id"]])["attempt_id"]
        task_type = by_id[source_id]["task_type"]
        supported, reason = writing_drill_support_status(root, task_type, code, source_id)
        if not supported:
            deferred.append({
                "action_id": f"PQ-{len(deferred) + 1:02d}-DEFERRED",
                "kind": "unsupported_target",
                "task_type": task_type,
                "source_attempt_id": source_id,
                "target_codes": [code],
                "status": "blocked_by_template",
                "status_reason": reason,
            })
            continue
        key = (source_id, task_type)
        groups[key].append(code)
        sources[key] = source_id

    recommendations = build_training_plan(root)["recommendations"]
    entries: list[dict] = []
    if recommendations:
        for recommendation in sorted(
            recommendations,
            key=lambda row: order.get(row["source_attempt_id"], -1),
            reverse=True,
        ):
            target_codes = recommendation["target_codes"]
            support_statuses = [
                writing_drill_support_status(
                    root, recommendation["task_type"], code, recommendation["source_attempt_id"]
                )
                for code in target_codes
            ]
            unsupported = [
                code for code, (supported, _) in zip(target_codes, support_statuses) if not supported
            ]
            if unsupported:
                deferred.append({
                    "action_id": f"PQ-{len(deferred) + 1:02d}-DEFERRED",
                    "kind": "unsupported_target",
                    "recommendation_id": recommendation["recommendation_id"],
                    "task_type": recommendation["task_type"],
                    "source_attempt_id": recommendation["source_attempt_id"],
                    "target_codes": unsupported,
                    "status": "blocked_by_template",
                    "status_reason": next(
                        reason for supported, reason in support_statuses if not supported
                    ),
                })
                continue
            entries.append({
                "recommendation_id": recommendation["recommendation_id"],
                "source_attempt_id": recommendation["source_attempt_id"],
                "task_type": recommendation["task_type"],
                "target_codes": target_codes,
                "item_count": recommendation["drill"]["item_count"],
                "minimum_accuracy": recommendation["drill"]["minimum_accuracy"],
            })
    else:
        for source_id, task_type in sorted(groups, key=lambda key: order[key[0]], reverse=True):
            entries.append({
                "recommendation_id": None,
                "source_attempt_id": sources[(source_id, task_type)],
                "task_type": task_type,
                "target_codes": groups[(source_id, task_type)],
                "item_count": 8,
                "minimum_accuracy": 0.8,
            })

    for entry in entries:
        matching_drill = _latest_matching_drill(
            root, entry["source_attempt_id"], entry["task_type"], entry["target_codes"]
        )
        entry["_matching_drill"] = matching_drill
        entry["_learner_drill_choice"] = (
            _learner_drill_choice(root, entry["source_attempt_id"])
            if matching_drill is None
            else None
        )
    priority_entry = next(
        (entry for entry in entries if entry["_learner_drill_choice"] != "declined"),
        None,
    )

    actions: list[dict] = []
    for entry in entries:
        source_id = entry["source_attempt_id"]
        task_type = entry["task_type"]
        target_codes = entry["target_codes"]
        drill_id = f"PQ-{len(actions) + 1:02d}-DRILL"
        matching_drill = entry["_matching_drill"]
        drill_status, drill_reason = _drill_status(matching_drill)
        drill_instruction = (
            "Generate an evidence-linked drill, complete it without viewing the answer key, "
            "then record the result as a targeted drill."
        )
        transfer_status = "blocked_by_drill"
        transfer_reason = "Complete the targeted drill before starting transfer."
        transfer_instruction = (
            "After meeting the drill threshold, complete one new formal prompt on this route. "
            "Confirm relevant opportunities; do not reuse the source prompt."
        )
        choice = entry["_learner_drill_choice"]
        if choice == "awaiting":
            drill_status = "awaiting_learner_choice"
            drill_reason = (
                "The latest incomplete second revision has no recorded learner opt-in. "
                "Ask whether the learner wants this targeted drill before generating it."
            )
            drill_instruction = (
                "Give the learner the exact-excerpt guidance and bounded rewrite direction, "
                "then ask whether they want this targeted drill."
            )
            transfer_status = "blocked_by_learner_choice"
            transfer_reason = "Transfer is unavailable until the learner opts in to the drill or declines it."
        elif choice == "declined":
            drill_status = "closed_by_learner_choice"
            drill_reason = "The learner declined the targeted drill after the incomplete second revision."
            drill_instruction = "Do not generate a drill; complete the required naturalness and precision follow-up."
            transfer_status = "not_available_after_decline"
            transfer_reason = "The declined-drill path concludes this revision chain without a transfer."
            transfer_instruction = "Do not offer a transfer from a revision chain closed by the learner's drill decision."
        if recommendations and entry is not priority_entry and choice != "declined":
            drill_status = "deferred_by_priority"
            drill_reason = f"Finish or resolve the higher-priority plan `{priority_entry['recommendation_id']}` first."
        actions.append({
            "action_id": drill_id,
            "kind": "targeted_drill",
            "recommendation_id": entry["recommendation_id"],
            "task_type": task_type,
            "source_attempt_id": source_id,
            "target_codes": target_codes,
            "item_count": entry["item_count"],
            "minimum_accuracy": entry["minimum_accuracy"],
            "status": drill_status,
            "status_reason": drill_reason,
            "instruction": drill_instruction,
        })
        if matching_drill is not None:
            transfer_status, transfer_reason = _transfer_status(matching_drill)
        if recommendations and entry is not priority_entry and choice != "declined":
            transfer_status = "deferred_by_priority"
            transfer_reason = f"Finish or resolve the higher-priority plan `{priority_entry['recommendation_id']}` first."
        actions.append({
            "action_id": f"PQ-{len(actions) + 1:02d}-TRANSFER",
            "kind": "fresh_transfer_check",
            "recommendation_id": entry["recommendation_id"],
            "task_type": task_type,
            "source_action_id": drill_id,
            "target_codes": target_codes,
            "status": transfer_status,
            "status_reason": transfer_reason,
            "instruction": transfer_instruction,
        })
    return {
        "version": 1,
        "result_label": "diagnostic_practice_queue",
        "source_records_modified": False,
        "active_training_plan_count": len(recommendations),
        "actions": actions,
        "deferred_actions": deferred,
    }


def write_practice_queue(root: Path) -> Path:
    queue = build_practice_queue(root)
    path = root / "tracker/writing/practice-queue.md"
    lines = [
        "# Writing Practice Queue",
        "",
        "Diagnostic planning artifact; drills and transfers are not TOEFL section-band estimates.",
        "",
    ]
    if not queue["actions"]:
        lines.append("- No supported evidence-linked action is due yet.")
    for action in queue["actions"]:
        lines.extend([
            f"## `{action['action_id']}` — `{action['kind']}`",
            *([f"- Plan: `{action['recommendation_id']}`"] if action.get("recommendation_id") else []),
            f"- Route: `{action['task_type']}`",
            f"- Targets: {', '.join(f'`{code}`' for code in action['target_codes'])}",
            f"- {action['instruction']}",
        ])
        if action["kind"] == "targeted_drill":
            lines.append(f"- Source: `{action['source_attempt_id']}`; {action['item_count']} items; threshold: {action['minimum_accuracy']:.0%}")
        else:
            lines.append(f"- Depends on: `{action['source_action_id']}`")
        lines.append(f"- Status: `{action['status']}` — {action['status_reason']}")
        lines.append("")
    for action in queue.get("deferred_actions", []):
        lines.extend([
            f"## `{action['action_id']}` — `{action['kind']}`",
            *([f"- Plan: `{action['recommendation_id']}`"] if action.get("recommendation_id") else []),
            f"- Route: `{action['task_type']}`",
            f"- Targets: {', '.join(f'`{code}`' for code in action['target_codes'])}",
            f"- Status: `{action['status']}` — {action['status_reason']}",
            "",
        ])
    atomic_write_text(path, "\n".join(lines))
    atomic_write_text(
        root / "tracker/writing/practice-queue.yaml",
        yaml.safe_dump(queue, allow_unicode=True, sort_keys=False),
    )
    return path
