"""Code-level revision comparisons for persistent Writing correction coaching."""

from collections import defaultdict
from pathlib import Path

import yaml

from toefl_tracker.canonical import load_canonical_events
from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.legacy_migration import load_legacy_compatibility, synthetic_sort_key


_COUNTED = {"must_fix", "should_fix"}


def build_revision_learning(root: Path) -> dict:
    attempts_root = root / "tracker/writing/attempts"
    attempts = [read_yaml(path) for path in attempts_root.glob("*/attempt.yaml")] if attempts_root.exists() else []
    compatibility = load_legacy_compatibility(root, "writing")
    attempts = sorted(attempts, key=lambda row: synthetic_sort_key(compatibility, row))
    by_id = {attempt["attempt_id"]: attempt for attempt in attempts}
    events_by_attempt: dict[str, list[dict]] = defaultdict(list)
    for event in load_canonical_events(root, "writing") if attempts else []:
        if event.get("level") in _COUNTED:
            events_by_attempt[event["attempt_id"]].append(event)
    comparisons: list[dict] = []
    for revision in attempts:
        if revision.get("record_type") != "revision":
            continue
        parent_id = revision.get("parent_attempt_id")
        if parent_id not in by_id:
            continue
        parent_codes = {event["code"] for event in events_by_attempt[parent_id]}
        revision_codes = {event["code"] for event in events_by_attempt[revision["attempt_id"]]}
        comparisons.append({
            "revision_attempt_id": revision["attempt_id"],
            "parent_attempt_id": parent_id,
            "retained_codes": sorted(parent_codes & revision_codes),
            "no_longer_observed_codes": sorted(parent_codes - revision_codes),
            "new_codes": sorted(revision_codes - parent_codes),
            "parent_evidence": [
                {"event_id": event["event_id"], "code": event["code"], "source_excerpt": event.get("source_excerpt", "")}
                for event in events_by_attempt[parent_id]
            ],
            "revision_evidence": [
                {"event_id": event["event_id"], "code": event["code"], "source_excerpt": event.get("source_excerpt", "")}
                for event in events_by_attempt[revision["attempt_id"]]
            ],
            "note": "No-longer-observed codes are comparison signals, not proof of mastery; opportunity confirmation is required on a fresh formal prompt.",
        })
    return {"version": 1, "source_records_modified": False, "comparisons": comparisons}


def write_revision_learning(root: Path) -> Path:
    learning = build_revision_learning(root)
    path = root / "tracker/writing/revision-learning.md"
    lines = ["# Writing Revision Learning", "", "Derived code-level comparison; not proof of mastery or a TOEFL score.", ""]
    if not learning["comparisons"]:
        lines.append("- No revision comparisons yet.")
    for row in learning["comparisons"]:
        lines.extend([
            f"## `{row['revision_attempt_id']}` from `{row['parent_attempt_id']}`",
            f"- Retained codes: {', '.join(f'`{code}`' for code in row['retained_codes']) or 'none'}",
            f"- No longer observed: {', '.join(f'`{code}`' for code in row['no_longer_observed_codes']) or 'none'}",
            f"- New codes: {', '.join(f'`{code}`' for code in row['new_codes']) or 'none'}",
            f"- {row['note']}",
            "",
        ])
    atomic_write_text(path, "\n".join(lines))
    atomic_write_text(root / "tracker/writing/revision-learning.yaml", yaml.safe_dump(learning, allow_unicode=True, sort_keys=False))
    return path
