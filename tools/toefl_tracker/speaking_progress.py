"""Rebuildable, transcript-bounded Speaking progress overview."""

import json
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from toefl_tracker.canonical import load_canonical_events
from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.legacy_migration import load_legacy_compatibility, synthetic_sort_key
from toefl_tracker.status import classify_code
from toefl_tracker.taxonomy import load_taxonomy


_COUNTED = {"must_fix", "should_fix"}


def _attempts(root: Path) -> list[dict]:
    base = root / "tracker/speaking/attempts"
    rows = [read_yaml(path) for path in base.glob("*/attempt.yaml")] if base.exists() else []
    return sorted(rows, key=lambda row: synthetic_sort_key(load_legacy_compatibility(root, "speaking"), row))


def _reliable_dimensions(root: Path, attempt_id: str) -> list[str]:
    path = root / "tracker/speaking/attempts" / attempt_id / "audio-inspection.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    dimensions = data.get("reliable_dimensions") if isinstance(data, dict) else None
    return sorted(dimensions) if isinstance(dimensions, list) and all(isinstance(value, str) for value in dimensions) else []


def _mapping_confirmed(root: Path, attempt_id: str) -> bool | None:
    path = root / "tracker/speaking/attempts" / attempt_id / "segments.yaml"
    try:
        rows = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(rows, list):
        return None
    return all(
        row.get("confidence") == "high" or row.get("confirmed_by_user") is True
        for row in rows if isinstance(row, dict)
    )


def _practice_lifecycle(rows: list[dict]) -> list[dict]:
    """Summarize retained drill/transfer lineage without inferring a score."""
    by_code: dict[str, dict] = {}
    for row in rows:
        if row.get("record_type") == "targeted_drill":
            drill = row.get("drill")
            if not isinstance(drill, dict):
                continue
            threshold = drill.get("minimum_accuracy")
            results = drill.get("code_results")
            if type(threshold) not in {int, float} or not isinstance(results, list):
                continue
            for result in results:
                if not isinstance(result, dict):
                    continue
                code = result.get("code")
                count = result.get("item_count")
                correct = result.get("correct_count")
                if not isinstance(code, str) or type(count) is not int or count <= 0 or type(correct) is not int:
                    continue
                summary = by_code.setdefault(code, {
                    "code": code, "drill_attempt_ids": [], "transfer_attempt_ids": [],
                })
                summary["drill_attempt_ids"].append(row["attempt_id"])
                summary["latest_drill_accuracy"] = round(correct / count, 4)
                summary["latest_minimum_accuracy"] = threshold
        elif row.get("record_type") == "formal_original":
            transfer = row.get("transfer")
            if not isinstance(transfer, dict) or not isinstance(transfer.get("target_codes"), list):
                continue
            outcomes = {
                outcome.get("code"): outcome.get("status")
                for outcome in transfer.get("outcomes", [])
                if isinstance(outcome, dict)
                and isinstance(outcome.get("code"), str)
                and isinstance(outcome.get("status"), str)
            }
            for code in transfer["target_codes"]:
                if not isinstance(code, str):
                    continue
                summary = by_code.setdefault(code, {
                    "code": code, "drill_attempt_ids": [], "transfer_attempt_ids": [],
                })
                summary["transfer_attempt_ids"].append(row["attempt_id"])
                if code in outcomes:
                    summary["latest_transfer_outcome"] = outcomes[code]
    lifecycle = []
    for code, summary in sorted(by_code.items()):
        if summary["transfer_attempt_ids"]:
            outcome = summary.get("latest_transfer_outcome")
            state = f"transfer_outcome_{outcome}" if outcome else "awaiting_coach_outcome"
        elif summary.get("latest_drill_accuracy", 0) >= summary.get("latest_minimum_accuracy", 1):
            state = "ready_for_transfer"
        else:
            state = "needs_drill_revision"
        lifecycle.append({**summary, "state": state})
    return lifecycle


def _rerecordings(rows: list[dict]) -> list[dict]:
    """Expose revision lineage without counting it as a formal session."""
    results = []
    for row in rows:
        if row.get("record_type") != "revision":
            continue
        revision = row.get("speaking_revision")
        if not isinstance(revision, dict):
            continue
        outcomes = revision.get("outcomes")
        if not isinstance(outcomes, list):
            continue
        results.append({
            "attempt_id": row["attempt_id"],
            "parent_attempt_id": revision.get("parent_attempt_id"),
            "scope": revision.get("scope"),
            "outcomes": [
                {"code": outcome.get("code"), "status": outcome.get("status"), "item_ids": outcome.get("item_ids")}
                for outcome in outcomes if isinstance(outcome, dict)
            ],
        })
    return results


def build_speaking_progress_overview(root: Path) -> dict:
    attempts = _attempts(root)
    formals = [row for row in attempts if row.get("record_type") == "formal_original"]
    events = load_canonical_events(root, "speaking") if attempts else []
    taxonomy = load_taxonomy(root) if events else {}
    recent = formals[-3:]
    recent_ids = {row["attempt_id"] for row in recent}
    counted = [
        event for event in events
        if event.get("attempt_id") in recent_ids and event.get("level") in _COUNTED
    ]
    errors = Counter(event["attempt_id"] for event in counted)
    routes: dict[str, dict] = {}
    for task_type in ("listen_and_repeat", "take_an_interview"):
        rows = [row for row in formals if row.get("task_type") == task_type]
        route_attempts = [row for row in attempts if row.get("task_type") == task_type]
        ids = {row["attempt_id"] for row in rows}
        route_events = [event for event in events if event.get("attempt_id") in ids and event.get("level") in _COUNTED]
        code_counts = Counter(event["code"] for event in route_events if event.get("code") in taxonomy)
        dimensions: dict[str, int] = defaultdict(int)
        for event in route_events:
            entry = taxonomy.get(event.get("code"))
            if entry is not None and entry.modality == "speaking":
                dimensions[entry.dimension] += 1
        routes[task_type] = {
            "formal_session_count": len(rows),
            "atomic_codes": {
                code: {
                    "events": count,
                    "formal_records": len({event["attempt_id"] for event in route_events if event["code"] == code}),
                    "historical_status": classify_code(code, rows, route_events) or "not_established",
                }
                for code, count in sorted(code_counts.items())
            },
            "dimensions": dict(sorted(dimensions.items())),
            "practice_lifecycle": _practice_lifecycle(route_attempts),
            "rerecordings": _rerecordings(route_attempts),
        }
    ranked = sorted(
        (
            {"code": code, "events": count}
            for code, count in Counter(event["code"] for event in counted).items()
        ),
        key=lambda row: (-row["events"], row["code"]),
    )
    return {
        "version": 2,
        "result_label": "diagnostic_only_speaking_progress",
        "formal_session_count": len(formals),
        "recent_sessions": [
            {
                "attempt_id": row["attempt_id"],
                "task_type": row["task_type"],
                "duration_seconds": row.get("duration_seconds"),
                "counted_events": errors[row["attempt_id"]],
                "reliable_dimensions": _reliable_dimensions(root, row["attempt_id"]),
                "role_mapping_confirmed": _mapping_confirmed(root, row["attempt_id"]),
            }
            for row in recent
        ],
        "routes": routes,
        "next_focuses": ranked[:2] if len(formals) >= 3 else [],
        "boundaries": [
            "Diagnostic only; not a TOEFL Speaking section band.",
            "Transcript evidence never establishes pronunciation, prosody, fluency, or intelligibility unless the persisted audio inspection marks that dimension reliable.",
            "Speaking drill and transfer lifecycle is result lineage only; it does not establish a TOEFL task score, section band, or audio-performance claim.",
            "Speaking re-recordings are revisions, not formal sessions; their transcript-supported outcomes do not establish audio-performance results.",
        ],
    }


def write_speaking_progress_overview(root: Path) -> Path:
    overview = build_speaking_progress_overview(root)
    path = root / "tracker/speaking/progress-overview.md"
    lines = [
        "# Speaking Progress Overview", "",
        "Diagnostic progress view only; not a TOEFL Speaking section band.", "",
        f"Formal sessions: {overview['formal_session_count']}", "",
        "## Recent formal sessions",
        "| Attempt | Task | Duration | Counted events | Reliable dimensions | Role mapping |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in overview["recent_sessions"]:
        lines.append(
            f"| `{row['attempt_id']}` | `{row['task_type']}` | {row['duration_seconds'] or 'unknown'} | "
            f"{row['counted_events']} | {', '.join(row['reliable_dimensions']) or 'text-only / unknown'} | "
            f"{'confirmed' if row['role_mapping_confirmed'] is True else 'unknown'} |"
        )
    if not overview["recent_sessions"]:
        lines.append("| — | — | — | — | — | — |")
    lines.extend(["", "## Route signals"])
    for route, summary in overview["routes"].items():
        lines.append(f"### `{route}` — {summary['formal_session_count']} formal sessions")
        lines.extend(
            f"- `{code}`: {row['events']} counted events across {row['formal_records']} sessions; trend signal: {row['historical_status']}."
            for code, row in summary["atomic_codes"].items()
        ) or lines.append("- No counted transcript signals")
        lines.append(
            "- Dimensions: " + ", ".join(f"`{name}` ({count})" for name, count in summary["dimensions"].items())
            if summary["dimensions"] else "- No diagnostic dimensions recorded"
        )
        lifecycle = summary["practice_lifecycle"]
        if lifecycle:
            lines.append("- Practice lifecycle:")
            lines.extend(
                f"  - `{row['code']}`: `{row['state']}` | drills {', '.join(row['drill_attempt_ids']) or '—'} | "
                f"transfers {', '.join(row['transfer_attempt_ids']) or '—'}"
                + (
                    f" | latest drill {row['latest_drill_accuracy']:.0%} / {row['latest_minimum_accuracy']:.0%}"
                    if "latest_drill_accuracy" in row else ""
                )
                + (f" | transcript outcome `{row['latest_transfer_outcome']}`" if "latest_transfer_outcome" in row else "")
                for row in lifecycle
            )
        rerecordings = summary["rerecordings"]
        if rerecordings:
            lines.append("- Re-recordings (excluded from formal-session count):")
            lines.extend(
                f"  - `{row['attempt_id']}` from `{row['parent_attempt_id']}` | `{row['scope']}` | "
                + ", ".join(
                    f"`{outcome['code']}`: `{outcome['status']}` (items {', '.join(map(str, outcome['item_ids']))})"
                    for outcome in row["outcomes"]
                )
                for row in rerecordings
            )
    lines.extend(["", "## Next two focuses"])
    lines.extend(
        f"- `{row['code']}`: {row['events']} counted events in the recent three formal sessions."
        for row in overview["next_focuses"]
    ) or lines.append("- Need three formal sessions before selecting progress focuses.")
    lines.extend(["", "## Evidence boundaries"])
    lines.extend(f"- {boundary}" for boundary in overview["boundaries"])
    atomic_write_text(path, "\n".join(lines) + "\n")
    atomic_write_text(root / "tracker/speaking/progress-overview.yaml", yaml.safe_dump(overview, allow_unicode=True, sort_keys=False))
    return path
