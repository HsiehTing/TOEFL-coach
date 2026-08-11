"""Build an executable, non-scored Writing practice queue from current evidence."""

from collections import defaultdict
from pathlib import Path

import yaml

from toefl_tracker.canonical import load_canonical_events
from toefl_tracker.drill_generation import supports_writing_drill
from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.legacy_migration import load_legacy_compatibility, synthetic_sort_key
from toefl_tracker.progress import build_progress_overview


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
    if (
        type(item_count) is not int
        or item_count <= 0
        or type(correct_count) is not int
        or not 0 <= correct_count <= item_count
    ):
        return "blocked_by_incomplete_assessment", "The drill result lacks valid item-level accuracy metadata."
    accuracy = correct_count / item_count
    if accuracy < 0.8:
        return "blocked_by_accuracy", f"Accuracy is {accuracy:.0%}; reach 80% before transfer."
    return "completed", f"Accuracy is {accuracy:.0%}; the drill threshold is met."


def _transfer_status(drill: dict) -> tuple[str, str]:
    status, reason = _drill_status(drill)
    if status == "completed":
        return "ready", "The drill threshold is met; a new prompt can be used for transfer."
    if status in {"blocked_by_accuracy", "blocked_by_pack_drift"}:
        return status, reason
    return "blocked_by_incomplete_assessment", reason


def build_practice_queue(root: Path) -> dict:
    """Sequence at most two evidence-backed drill targets and fresh transfers."""
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
        if not supports_writing_drill(root, task_type, code):
            deferred.append({
                "action_id": f"PQ-{len(deferred) + 1:02d}-DEFERRED",
                "kind": "unsupported_target",
                "task_type": task_type,
                "source_attempt_id": source_id,
                "target_codes": [code],
                "status": "blocked_by_template",
                "status_reason": "No evidence-linked drill template supports this target code yet.",
            })
            continue
        key = (source_id, task_type)
        groups[key].append(code)
        sources[key] = source_id

    actions: list[dict] = []
    for source_id, task_type in sorted(groups, key=lambda key: order[key[0]], reverse=True):
        target_codes = groups[(source_id, task_type)]
        drill_id = f"PQ-{len(actions) + 1:02d}-DRILL"
        matching_drill = _latest_matching_drill(root, source_id, task_type, target_codes)
        drill_status, drill_reason = _drill_status(matching_drill)
        actions.append({
            "action_id": drill_id,
            "kind": "targeted_drill",
            "task_type": task_type,
            "source_attempt_id": sources[(source_id, task_type)],
            "target_codes": target_codes,
            "item_count": 8,
            "minimum_accuracy": 0.8,
            "status": drill_status,
            "status_reason": drill_reason,
            "instruction": "Generate an evidence-linked drill, complete it without viewing the answer key, then record the result as a targeted drill.",
        })
        transfer_status = "blocked_by_drill"
        transfer_reason = "Complete the targeted drill before starting transfer."
        if matching_drill is not None:
            transfer_status, transfer_reason = _transfer_status(matching_drill)
        actions.append({
            "action_id": f"PQ-{len(actions) + 1:02d}-TRANSFER",
            "kind": "fresh_transfer_check",
            "task_type": task_type,
            "source_action_id": drill_id,
            "target_codes": target_codes,
            "status": transfer_status,
            "status_reason": transfer_reason,
            "instruction": "After meeting the drill threshold, complete one new formal prompt on this route. Confirm relevant opportunities; do not reuse the source prompt.",
        })
    return {
        "version": 1,
        "result_label": "diagnostic_practice_queue",
        "source_records_modified": False,
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
