"""Rebuildable Writing progress overview; never a TOEFL section-band estimator."""

from collections import Counter, defaultdict
from pathlib import Path

import yaml

from toefl_tracker.canonical import load_canonical_events
from toefl_tracker.families import aggregate_family_hits, load_skill_families
from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.legacy_migration import load_legacy_compatibility, synthetic_sort_key
from toefl_tracker.lineage import lineage_summary
from toefl_tracker.mastery import derive_mastery
from toefl_tracker.status import classify_code
from toefl_tracker.taxonomy import load_taxonomy


_COUNTED = {"must_fix", "should_fix"}


def _attempts(root: Path) -> list[dict]:
    base = root / "tracker/writing/attempts"
    rows = [read_yaml(path) for path in base.glob("*/attempt.yaml")] if base.exists() else []
    compatibility = load_legacy_compatibility(root, "writing")
    return sorted(rows, key=lambda row: synthetic_sort_key(compatibility, row))


def _route_summary(task_type: str, formals: list[dict], events: list[dict], taxonomy: dict, families: dict) -> dict:
    rows = [row for row in formals if row.get("task_type") == task_type]
    ids = {row["attempt_id"] for row in rows}
    visible = [
        event for event in events
        if event.get("attempt_id") in ids
        and event.get("code") in taxonomy
        and (taxonomy[event["code"]].scope == "common" or task_type in taxonomy[event["code"]].task_types)
    ]
    counted = [event for event in visible if event.get("level") in _COUNTED]
    counts = Counter(event["code"] for event in counted)
    codes = {
        code: {
            "events": count,
            "formal_records": len({event["attempt_id"] for event in counted if event["code"] == code}),
            "historical_status": classify_code(code, rows, counted) or "not_established",
        }
        for code, count in sorted(counts.items())
    }
    family_summary = aggregate_family_hits(families, rows, visible, task_type=task_type)
    return {
        "formal_record_count": len(rows),
        "atomic_codes": codes,
        "skill_families": {name: summary for name, summary in family_summary.items() if summary["event_count"]},
    }


def build_progress_overview(root: Path) -> dict:
    attempts = _attempts(root)
    formals = [row for row in attempts if row.get("record_type") == "formal_original"]
    revisions = [row for row in attempts if row.get("record_type") == "revision"]
    events = load_canonical_events(root, "writing") if attempts else []
    taxonomy = load_taxonomy(root) if events else {}
    families = load_skill_families(root) if (root / "standards/ets-2026/writing-skill-families.yaml").exists() else {}
    recent = formals[-3:]
    recent_ids = {row["attempt_id"] for row in recent}
    counted = [event for event in events if event.get("level") in _COUNTED and event.get("attempt_id") in recent_ids]
    counts = Counter(event["code"] for event in counted)
    focus_codes = [code for code, _ in counts.most_common(2)] if len(formals) >= 3 else []
    revision_summaries = [lineage_summary(row["attempt_id"], [*formals, *revisions]) for row in formals]
    result_label = "diagnostic_only_progress_view" if len(formals) >= 3 else "diagnostic_only_early_view"
    return {
        "version": 1,
        "result_label": result_label,
        "formal_record_count": len(formals),
        "recent_formals": [
            {
                "attempt_id": row["attempt_id"], "task_type": row["task_type"], "simulated_task_score": row.get("task_score", {}).get("value"),
                "word_count": row.get("word_count"), "timed": row.get("timed"),
            }
            for row in recent
        ],
        "routes": {task: _route_summary(task, formals, events, taxonomy, families) for task in ("email", "academic_discussion")},
        "revision_chains": revision_summaries,
        "mastery": derive_mastery(root),
        "next_focuses": [
            {"code": code, "reason": f"{counts[code]} counted events in the latest three formal records."}
            for code in focus_codes
        ],
    }


def write_progress_overview(root: Path) -> Path:
    overview = build_progress_overview(root)
    path = root / "tracker/writing/progress-overview.md"
    lines = ["# Writing Progress Overview", "", "Diagnostic progress view only; not a TOEFL Writing section band.", "", f"Formal records: {overview['formal_record_count']}", ""]
    lines.append("## Recent formal records")
    if not overview["recent_formals"]:
        lines.append("- No formal records")
    for row in overview["recent_formals"]:
        lines.append(f"- `{row['attempt_id']}` | `{row['task_type']}` | simulated task score: {row['simulated_task_score']} | timed: {row['timed']}")
    lines.extend(["", "## Next two focuses"])
    lines.extend([f"- `{row['code']}`: {row['reason']}" for row in overview["next_focuses"]] or ["- Need three formal records before trend focuses."])
    lines.extend(["", "## Mastery"])
    lines.extend([f"- `{code}`: {summary['status']}" for code, summary in overview["mastery"].items()] or ["- No drill/mastery signals yet"])
    atomic_write_text(path, "\n".join(lines) + "\n")
    atomic_write_text(root / "tracker/writing/progress-overview.yaml", yaml.safe_dump(overview, allow_unicode=True, sort_keys=False))
    return path
