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


def build_practice_queue(root: Path) -> dict:
    """Sequence at most two evidence-backed drill targets and fresh transfers."""
    overview = build_progress_overview(root)
    formals = _formals(root)
    events = load_canonical_events(root, "writing") if formals else []
    order = {attempt["attempt_id"]: index for index, attempt in enumerate(formals)}
    by_id = {attempt["attempt_id"]: attempt for attempt in formals}
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    sources: dict[tuple[str, str], str] = {}
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
            continue
        key = (source_id, task_type)
        groups[key].append(code)
        sources[key] = source_id

    actions: list[dict] = []
    for source_id, task_type in sorted(groups, key=lambda key: order[key[0]], reverse=True):
        target_codes = groups[(source_id, task_type)]
        drill_id = f"PQ-{len(actions) + 1:02d}-DRILL"
        actions.append({
            "action_id": drill_id,
            "kind": "targeted_drill",
            "task_type": task_type,
            "source_attempt_id": sources[(source_id, task_type)],
            "target_codes": target_codes,
            "item_count": 8,
            "minimum_accuracy": 0.8,
            "instruction": "Generate an evidence-linked drill, complete it without viewing the answer key, then record the result as a targeted drill.",
        })
        actions.append({
            "action_id": f"PQ-{len(actions) + 1:02d}-TRANSFER",
            "kind": "fresh_transfer_check",
            "task_type": task_type,
            "source_action_id": drill_id,
            "target_codes": target_codes,
            "instruction": "After meeting the drill threshold, complete one new formal prompt on this route. Confirm relevant opportunities; do not reuse the source prompt.",
        })
    return {
        "version": 1,
        "result_label": "diagnostic_practice_queue",
        "source_records_modified": False,
        "actions": actions,
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
        lines.append("")
    atomic_write_text(path, "\n".join(lines))
    atomic_write_text(
        root / "tracker/writing/practice-queue.yaml",
        yaml.safe_dump(queue, allow_unicode=True, sort_keys=False),
    )
    return path
