import csv
import json
import re
from collections import Counter, defaultdict
from io import StringIO
from pathlib import Path

from toefl_tracker.canonical import load_canonical_events, write_aggregate_events
from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.models import TASK_TYPES
from toefl_tracker.status import classify_code
from toefl_tracker.taxonomy import TaxonomyEntry, load_taxonomy


_COUNTED_LEVELS = {"must_fix", "should_fix"}


def _load_attempts(root: Path, modality: str) -> list[dict]:
    base = root / "tracker" / modality / "attempts"
    rows = [read_yaml(path) for path in base.glob("*/attempt.yaml")] if base.exists() else []
    return sorted(rows, key=lambda row: (row["submitted_at"], row["attempt_id"]))


def _events_for_attempts(events: list[dict], attempts: list[dict]) -> list[dict]:
    attempt_ids = {attempt["attempt_id"] for attempt in attempts}
    return [event for event in events if event["attempt_id"] in attempt_ids]


def _dashboard(formals: list[dict], events: list[dict]) -> str:
    buffer = StringIO()
    fields = [
        "attempt_id", "submitted_at", "task_type", "timed", "score", "word_count",
        "duration_seconds", "counted_errors", "errors_per_100_words",
        "meaning_changing_per_100_words", "task_metrics",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    counts = Counter(event["attempt_id"] for event in events if event["level"] in _COUNTED_LEVELS)
    severe = Counter(
        event["attempt_id"]
        for event in events
        if event["level"] in _COUNTED_LEVELS and event["severity"] == "meaning_changing"
    )
    for attempt in formals:
        words = attempt.get("word_count")
        writer.writerow({
            "attempt_id": attempt["attempt_id"],
            "submitted_at": attempt["submitted_at"],
            "task_type": attempt["task_type"],
            "timed": attempt.get("timed", ""),
            "score": attempt.get("task_score", {}).get("value", ""),
            "word_count": words or "",
            "duration_seconds": attempt.get("duration_seconds", ""),
            "counted_errors": counts[attempt["attempt_id"]],
            "errors_per_100_words": f"{counts[attempt['attempt_id']] * 100 / words:.2f}" if words else "",
            "meaning_changing_per_100_words": f"{severe[attempt['attempt_id']] * 100 / words:.2f}" if words else "",
            "task_metrics": json.dumps(attempt.get("task_metrics", {}), ensure_ascii=False, sort_keys=True),
        })
    return buffer.getvalue()


def _timing_label(attempt: dict) -> str:
    return "timed" if attempt.get("timed") is True else "untimed" if attempt.get("timed") is False else "unknown"


def _result_label(attempt: dict) -> str:
    return "simulated_task_score" if attempt.get("modality") == "writing" else "diagnostic_only"


def _result_value(attempt: dict) -> str:
    if attempt.get("modality") == "writing":
        return str(attempt.get("task_score", {}).get("value", "diagnostic"))
    return "diagnostic"


def _visible_events(
    events: list[dict], entries: dict[str, TaxonomyEntry], task_type: str | None
) -> list[dict]:
    visible: list[dict] = []
    for event in events:
        entry = entries.get(event["code"])
        if entry is None:
            continue
        if entry.scope == "common" or (task_type is not None and task_type in entry.task_types):
            visible.append(event)
    return visible


def _recurring_lines(formals: list[dict], events: list[dict]) -> tuple[str, list[tuple[str, str, int]]]:
    counted = [event for event in events if event["level"] in _COUNTED_LEVELS and event["code"] != "UNCLASSIFIED"]
    code_counts = Counter(event["code"] for event in counted)
    rows: list[tuple[str, str, int]] = []
    for code in sorted(code_counts):
        status = classify_code(code, formals, counted) or "not established"
        records = len({event["attempt_id"] for event in counted if event["code"] == code})
        rows.append((code, status, records))
    text = "\n".join(
        f"- `{code}`: {status}, {code_counts[code]} events in {records} records"
        for code, status, records in rows
    ) or "- No counted events"
    return text, rows


def _focuses(formals: list[dict], events: list[dict], rows: list[tuple[str, str, int]]) -> list[str]:
    counted = [event for event in events if event["level"] in _COUNTED_LEVELS]
    recent_ids = {attempt["attempt_id"] for attempt in formals[-3:]}
    recent_counts = Counter(event["code"] for event in counted if event["attempt_id"] in recent_ids)
    ranked = sorted(
        rows,
        key=lambda row: (
            0 if row[1] == "relapsed" else 1 if row[1] == "persistent" else 2,
            -recent_counts[row[0]],
            row[0],
        ),
    )
    return [code for code, _, _ in ranked[:2]]


def _revision_resolution(revisions: list[dict], formal_ids: set[str]) -> str:
    comparable = [row for row in revisions if row.get("parent_attempt_id") in formal_ids]
    assigned = sum(row["revision_outcomes"]["assigned"] for row in comparable)
    resolved = sum(row["revision_outcomes"]["resolved"] for row in comparable)
    return f"{resolved / assigned:.1%}" if assigned else "No comparable revisions"


def _report_markdown(
    title: str,
    boundary: int,
    formals: list[dict],
    revisions: list[dict],
    reevaluations: dict[str, list[dict]],
    events: list[dict],
) -> str:
    counted = [event for event in events if event["level"] in _COUNTED_LEVELS]
    severe_trend = " → ".join(
        str(sum(event["attempt_id"] == formal["attempt_id"] and event["severity"] == "meaning_changing" for event in counted))
        for formal in formals
    ) or "0"
    timeline: list[str] = []
    for formal in formals:
        timeline.append(
            f"- `{formal['attempt_id']}` | {_timing_label(formal)} | {_result_label(formal)} | "
            f"result: {_result_value(formal)} | rubric: `{formal['rubric_version']}` | "
            f"verified: {formal['standard_verified_at']}"
        )
        timeline.append(
            f"  - Original evaluation: result: {_result_value(formal)} | rubric: `{formal['rubric_version']}`"
        )
        for reevaluation in reevaluations.get(formal["attempt_id"], []):
            timeline.append(
                f"  - Re-evaluation: `{reevaluation['attempt_id']}` | {_result_label(reevaluation)} | result: {_result_value(reevaluation)} | "
                f"rubric: `{reevaluation['rubric_version']}` | verified: {reevaluation['standard_verified_at']}"
            )
    recurring, rows = _recurring_lines(formals, events)
    focuses = _focuses(formals, events, rows)
    focus_lines = "\n".join(f"{number}. `{code}`" for number, code in enumerate(focuses, start=1))
    formal_ids = {formal["attempt_id"] for formal in formals}
    rubrics = {
        row["rubric_version"]
        for row in [*formals, *(reevaluation for parent, rows in reevaluations.items() if parent in formal_ids for reevaluation in rows)]
    }
    attempt_ids = ", ".join(f"`{row['attempt_id']}`" for row in formals)
    boundary_text = (
        f"All records use rubric `{next(iter(rubrics))}`."
        if len(rubrics) == 1
        else "Warning: compared records span multiple rubric versions."
    )
    return (
        f"# {title} — boundary {boundary:04d}\n\n"
        f"Formal records: {len(formals)}\n"
        f"Attempt IDs: {attempt_ids}\n\n"
        f"## Record timeline\n"
        + "\n".join(timeline)
        + f"\n\n## Severe-event trend\n{severe_trend}\n\n"
        f"## Recurring patterns\n{recurring}\n\n"
        f"## Revision resolution\n{_revision_resolution(revisions, {row['attempt_id'] for row in formals})}\n\n"
        f"## Version boundary\n{boundary_text}\n\n"
        f"## Next two focuses\n{focus_lines}\n"
    )


def _report_path(base: Path, modality: str, task_type: str | None, boundary: int) -> Path:
    scope = "common" if task_type is None else task_type.replace("_", "-")
    return base / "reports" / f"{modality}-{scope}-{boundary:04d}.md"


def _remove_stale_generated_reports(base: Path, modality: str, expected: set[Path]) -> None:
    reports = base / "reports"
    if not reports.exists():
        return
    scopes = ["common", *(task.replace("_", "-") for task in TASK_TYPES[modality])]
    pattern = re.compile(rf"^{re.escape(modality)}-({'|'.join(map(re.escape, scopes))})-\d{{4}}\.md$")
    for path in reports.glob("*.md"):
        if pattern.fullmatch(path.name) and path not in expected:
            path.unlink()


def rebuild_modality(root: Path, modality: str) -> list[Path]:
    base = root / "tracker" / modality
    attempts = _load_attempts(root, modality)
    formals = [row for row in attempts if row["record_type"] == "formal_original"]
    revisions = [row for row in attempts if row["record_type"] == "revision"]
    reevaluations: dict[str, list[dict]] = defaultdict(list)
    for row in attempts:
        if row["record_type"] == "re_evaluation":
            reevaluations[row["parent_attempt_id"]].append(row)
    for values in reevaluations.values():
        values.sort(key=lambda row: (row.get("evaluated_at", row["submitted_at"]), row["attempt_id"]))

    write_aggregate_events(root, modality)
    events = load_canonical_events(root, modality)
    entries = load_taxonomy(root) if events else {}
    formal_events = _events_for_attempts(events, formals)
    atomic_write_text(base / "dashboard.csv", _dashboard(formals, formal_events))

    _, profile_rows = _recurring_lines(formals, formal_events)
    profile_lines = "\n".join(f"- `{code}`: {status}" for code, status, _ in profile_rows)
    atomic_write_text(
        base / "profile.md",
        "# Current Profile\n\n"
        f"Formal records: {len(formals)}\n"
        + (f"\n{profile_lines}\n" if profile_lines else ""),
    )

    reports: list[Path] = []
    for boundary in range(3, len(formals) + 1, 3):
        window = formals[:boundary]
        path = _report_path(base, modality, None, boundary)
        window_events = _visible_events(_events_for_attempts(events, window), entries, None)
        atomic_write_text(path, _report_markdown(f"{modality.title()} Common Report", boundary, window, revisions, reevaluations, window_events))
        reports.append(path)
    for task_type in sorted({row["task_type"] for row in formals}):
        task_formals = [row for row in formals if row["task_type"] == task_type]
        for boundary in range(3, len(task_formals) + 1, 3):
            window = task_formals[:boundary]
            path = _report_path(base, modality, task_type, boundary)
            window_events = _visible_events(_events_for_attempts(events, window), entries, task_type)
            atomic_write_text(path, _report_markdown(f"{modality.title()} {task_type.replace('_', ' ').title()} Report", boundary, window, revisions, reevaluations, window_events))
            reports.append(path)
    _remove_stale_generated_reports(base, modality, set(reports))
    return reports
