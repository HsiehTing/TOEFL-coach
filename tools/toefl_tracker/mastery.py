"""Derived mastery states for targeted Writing drills."""

from collections import defaultdict
from pathlib import Path

import yaml

from toefl_tracker.canonical import load_canonical_events
from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.models import ValidationError


MASTERY_STATES = {"identified", "practised", "provisional", "transferred", "controlled", "relapsed"}
_COUNTED = {"must_fix", "should_fix"}


def _attempts(root: Path) -> list[dict]:
    base = root / "tracker/writing/attempts"
    rows = [read_yaml(path) for path in base.glob("*/attempt.yaml")] if base.exists() else []
    return sorted(rows, key=lambda row: (row.get("submitted_at", ""), row.get("attempt_id", "")))


def _per_code_drill_counts(drill: dict, code: str) -> tuple[int, int, int]:
    """Use code-specific results when available; retain legacy aggregate compatibility."""
    metadata = drill["drill"]
    for result in metadata.get("code_results", []):
        if isinstance(result, dict) and result.get("code") == code:
            return result["item_count"], result["correct_count"], result["partial_count"]
    partial_count = sum(
        item.get("status") == "partially_meets_target"
        for item in metadata.get("item_results", [])
        if isinstance(item, dict)
    )
    return metadata["item_count"], metadata["correct_count"], partial_count


def _status(drill_count: int, accuracy: float, formal_opportunities: int, formal_errors: int, recent_opportunities: list[int], recent_errors: list[int]) -> str:
    if drill_count == 0 and formal_errors == 0:
        return "identified" if formal_opportunities else "identified"
    prior_opportunities = recent_opportunities[:-1]
    prior_errors = recent_errors[:-1]
    was_controlled = (
        len(prior_opportunities) >= 5
        and all(value > 0 for value in prior_opportunities[-2:])
        and all(value == 0 for value in prior_errors[-2:])
    )
    if recent_opportunities and recent_opportunities[-1] > 0 and recent_errors[-1] > 0 and was_controlled:
        return "relapsed"
    if drill_count < 1:
        return "identified"
    if drill_count < 2 or accuracy < 0.8:
        return "practised"
    if formal_opportunities < 3 or formal_errors > 0:
        return "provisional"
    if formal_opportunities >= 5 and len(recent_opportunities) >= 2 and all(value > 0 for value in recent_opportunities[-2:]) and all(value == 0 for value in recent_errors[-2:]):
        return "controlled"
    return "transferred"


def derive_mastery(root: Path, task_type: str | None = None) -> dict[str, dict]:
    attempts = _attempts(root)
    if task_type is not None:
        attempts = [row for row in attempts if row.get("task_type") == task_type]
    drills = [row for row in attempts if row.get("record_type") == "targeted_drill"]
    formals = [row for row in attempts if row.get("record_type") == "formal_original"]
    events = [event for event in load_canonical_events(root, "writing") if event.get("level") in _COUNTED]
    by_code: dict[str, dict] = defaultdict(lambda: {"drills": [], "formal_ids": [], "formal_errors": [], "evidence": []})
    for drill in drills:
        metadata = drill.get("drill", {})
        for code in metadata.get("target_codes", []):
            by_code[code]["drills"].append(drill)
            by_code[code]["evidence"].append(drill["attempt_id"])
    events_by_attempt: dict[str, set[str]] = defaultdict(set)
    for event in events:
        events_by_attempt[event["attempt_id"]].add(event["code"])
        if event["code"] not in by_code:
            by_code[event["code"]]["evidence"].append(event["attempt_id"])
    result: dict[str, dict] = {}
    for code, data in sorted(by_code.items()):
        drill_rows = data["drills"]
        counts = [_per_code_drill_counts(row, code) for row in drill_rows]
        item_count = sum(item_count for item_count, _, _ in counts)
        correct_count = sum(correct_count for _, correct_count, _ in counts)
        partial_count = sum(partial_count for _, _, partial_count in counts)
        accuracy = correct_count / item_count if item_count else 0.0
        transfer_formals = [
            row for row in formals
            if isinstance(row.get("transfer"), dict) and code in row["transfer"].get("target_codes", [])
        ]
        opportunities = [1 if row.get("opportunities", {}).get(code, 0) > 0 else 0 for row in transfer_formals]
        errors = [1 if code in events_by_attempt.get(row["attempt_id"], set()) else 0 for row in transfer_formals]
        formal_opportunities = sum(opportunities)
        formal_errors = sum(error for opportunity, error in zip(opportunities, errors) if opportunity)
        status = _status(len(drill_rows), accuracy, formal_opportunities, formal_errors, opportunities, errors)
        drill_attempt_ids = [row["attempt_id"] for row in drill_rows]
        transfer_attempt_ids = [row["attempt_id"] for row in transfer_formals]
        result[code] = {
            "status": status,
            "drill_sets": len(drill_rows),
            "drill_accuracy": round(accuracy, 4),
            "drill_partial_items": partial_count,
            "formal_opportunities": formal_opportunities,
            "formal_errors": formal_errors,
            "drill_attempt_ids": list(dict.fromkeys(drill_attempt_ids)),
            "transfer_attempt_ids": list(dict.fromkeys(transfer_attempt_ids)),
            "evidence_attempt_ids": list(dict.fromkeys([*data["evidence"], *transfer_attempt_ids])),
        }
    return result


def write_mastery(root: Path, task_type: str | None = None) -> Path:
    data = derive_mastery(root, task_type)
    path = root / "tracker/writing/mastery.md"
    lines = ["# Writing Mastery", "", "Derived state; historical event statuses remain unchanged.", ""]
    if not data:
        lines.append("- No mastery signals yet")
    for code, summary in data.items():
        lines.append(
            f"- `{code}`: {summary['status']} | drills {summary['drill_sets']} | "
            f"accuracy {summary['drill_accuracy']:.1%} | partial items {summary['drill_partial_items']} | transfer opportunities {summary['formal_opportunities']} | "
            f"transfer errors {summary['formal_errors']}"
        )
        lines.append(f"  - Evidence: {', '.join(summary['evidence_attempt_ids'])}")
    atomic_write_text(path, "\n".join(lines) + "\n")
    atomic_write_text(root / "tracker/writing/mastery.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return path
