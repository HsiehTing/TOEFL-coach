import csv
import json
from collections import Counter
from io import StringIO
from pathlib import Path

from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.status import classify_code


def _load_attempts(root: Path, modality: str) -> list[dict]:
    base = root / "tracker" / modality / "attempts"
    rows = (
        [read_yaml(path) for path in base.glob("*/attempt.yaml")]
        if base.exists()
        else []
    )
    return sorted(rows, key=lambda row: (row["submitted_at"], row["attempt_id"]))


def _load_events(root: Path, modality: str) -> list[dict]:
    path = root / "tracker" / modality / "error-events.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _events_for_attempts(events: list[dict], attempts: list[dict]) -> list[dict]:
    attempt_ids = {attempt["attempt_id"] for attempt in attempts}
    return [event for event in events if event["attempt_id"] in attempt_ids]


def _dashboard(formals: list[dict], events: list[dict]) -> str:
    buffer = StringIO()
    fields = [
        "attempt_id",
        "submitted_at",
        "task_type",
        "timed",
        "score",
        "word_count",
        "duration_seconds",
        "counted_errors",
        "errors_per_100_words",
        "meaning_changing_per_100_words",
        "task_metrics",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    counts = Counter(
        event["attempt_id"]
        for event in events
        if event["level"] in {"must_fix", "should_fix"}
    )
    severe = Counter(
        event["attempt_id"]
        for event in events
        if event["level"] in {"must_fix", "should_fix"}
        and event["severity"] == "meaning_changing"
    )
    for attempt in formals:
        words = attempt.get("word_count")
        writer.writerow(
            {
                "attempt_id": attempt["attempt_id"],
                "submitted_at": attempt["submitted_at"],
                "task_type": attempt["task_type"],
                "timed": attempt.get("timed", ""),
                "score": attempt.get("task_score", {}).get("value", ""),
                "word_count": words or "",
                "duration_seconds": attempt.get("duration_seconds", ""),
                "counted_errors": counts[attempt["attempt_id"]],
                "errors_per_100_words": (
                    f"{counts[attempt['attempt_id']] * 100 / words:.2f}"
                    if words
                    else ""
                ),
                "meaning_changing_per_100_words": (
                    f"{severe[attempt['attempt_id']] * 100 / words:.2f}"
                    if words
                    else ""
                ),
                "task_metrics": json.dumps(
                    attempt.get("task_metrics", {}),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    return buffer.getvalue()


def _ranked_codes(events: list[dict]) -> list[tuple[str, int]]:
    counts = Counter(event["code"] for event in events)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _report_markdown(
    title: str,
    formals: list[dict],
    revisions: list[dict],
    events: list[dict],
) -> str:
    window_events = _events_for_attempts(events, formals)
    counted = [
        event
        for event in window_events
        if event["level"] in {"must_fix", "should_fix"}
    ]
    ranking = _ranked_codes(counted)
    codes = [code for code, _ in ranking]
    states = [
        (code, classify_code(code, formals, counted))
        for code in codes
    ]
    scores = [
        str(row.get("task_score", {}).get("value", "diagnostic"))
        for row in formals
    ]
    assigned = sum(row["revision_outcomes"]["assigned"] for row in revisions)
    resolved = sum(row["revision_outcomes"]["resolved"] for row in revisions)
    resolution = f"{resolved / assigned:.1%}" if assigned else "no revisions"
    severe = sum(
        event["severity"] == "meaning_changing" for event in counted
    )
    ranking_lines = "\n".join(
        f"- `{code}`: {count}" for code, count in ranking
    ) or "- No counted errors"
    state_lines = "\n".join(
        f"- `{code}`: {state}" for code, state in states if state is not None
    ) or "- No established status"
    bottleneck = f"`{codes[0]}`" if codes else "No counted bottleneck"
    focus_lines = "\n".join(
        f"- `{code}`" for code in codes[:2]
    ) or "- Maintain current control"
    metric_lines = "\n".join(
        (
            f"- {row['attempt_id']}: "
            f"{json.dumps(row.get('task_metrics', {}), ensure_ascii=False, sort_keys=True)}"
        )
        for row in formals
    )
    return (
        f"# {title}\n\n"
        f"## Comparable range\n\n"
        f"{formals[0]['attempt_id']} through {formals[-1]['attempt_id']}\n\n"
        f"## Result trend\n\n{' → '.join(scores)}\n\n"
        f"## Task metric snapshots\n\n{metric_lines}\n\n"
        f"## Severe-error trend\n\nMeaning-changing events: {severe}\n\n"
        f"## Recurring-error ranking\n\n{ranking_lines}\n\n"
        f"## Historical states\n\n{state_lines}\n\n"
        f"## Revision success\n\nRevision resolution rate: {resolution}\n\n"
        f"## Main next-level bottleneck\n\n{bottleneck}\n\n"
        f"## Next two focuses\n\n{focus_lines}\n"
    )


def _write_report(
    path: Path,
    title: str,
    formals: list[dict],
    revisions: list[dict],
    events: list[dict],
) -> None:
    formal_ids = {row["attempt_id"] for row in formals}
    window_revisions = [
        row for row in revisions if row["parent_attempt_id"] in formal_ids
    ]
    atomic_write_text(
        path,
        _report_markdown(title, formals, window_revisions, events),
    )


def rebuild_modality(root: Path, modality: str) -> list[Path]:
    attempts = _load_attempts(root, modality)
    formals = [
        row for row in attempts if row["record_type"] == "formal_original"
    ]
    revisions = [row for row in attempts if row["record_type"] == "revision"]
    events = _load_events(root, modality)
    formal_events = _events_for_attempts(events, formals)
    base = root / "tracker" / modality
    atomic_write_text(base / "dashboard.csv", _dashboard(formals, formal_events))

    codes = sorted({event["code"] for event in formal_events})
    states = [
        (code, classify_code(code, formals, formal_events))
        for code in codes
    ]
    profile_lines = "".join(
        f"- `{code}`: {state}\n"
        for code, state in states
        if state is not None
    )
    profile = "# Current Profile\n" + (
        f"\n{profile_lines}" if profile_lines else ""
    )
    atomic_write_text(base / "profile.md", profile)

    reports = []
    for boundary in range(3, len(formals) + 1, 3):
        window = formals[:boundary]
        common = (
            base
            / "reports"
            / f"{modality}-common-{boundary:04d}.md"
        )
        _write_report(
            common,
            f"{modality.title()} Common Report",
            window,
            revisions,
            events,
        )
        reports.append(common)

    for task_type in sorted({row["task_type"] for row in formals}):
        rows = [row for row in formals if row["task_type"] == task_type]
        for boundary in range(3, len(rows) + 1, 3):
            window = rows[:boundary]
            slug = task_type.replace("_", "-")
            report = (
                base
                / "reports"
                / f"{modality}-{slug}-{boundary:04d}.md"
            )
            _write_report(
                report,
                task_type,
                window,
                revisions,
                events,
            )
            reports.append(report)
    return reports
