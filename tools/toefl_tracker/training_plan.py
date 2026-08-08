"""Build bounded next-step Writing recommendations from revision lineages."""

from collections import Counter
from pathlib import Path

from toefl_tracker.canonical import load_canonical_events
from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.legacy_migration import load_legacy_compatibility, synthetic_sort_key
from toefl_tracker.lineage import lineage_summary


_COUNTED = {"must_fix", "should_fix"}


def _attempts(root: Path) -> list[dict]:
    base = root / "tracker/writing/attempts"
    rows = [read_yaml(path) for path in base.glob("*/attempt.yaml")] if base.exists() else []
    compatibility = load_legacy_compatibility(root, "writing")
    return sorted(rows, key=lambda row: synthetic_sort_key(compatibility, row))


def _full(outcome: dict | None) -> bool:
    return bool(
        isinstance(outcome, dict)
        and outcome.get("assigned", 0) > 0
        and outcome.get("resolved") == outcome.get("assigned")
        and outcome.get("partly_resolved") == 0
        and outcome.get("unresolved") == 0
    )


def build_training_plan(root: Path) -> dict:
    attempts = _attempts(root)
    compatibility = load_legacy_compatibility(root, "writing")
    formals = [row for row in attempts if row.get("record_type") == "formal_original"]
    revisions = [row for row in attempts if row.get("record_type") == "revision"]
    events = [row for row in load_canonical_events(root, "writing") if row.get("level") in _COUNTED]
    recommendations: list[dict] = []
    for formal in formals:
        summary = lineage_summary(
            formal["attempt_id"], [*formals, *revisions], compatibility=compatibility
        )
        if summary["round_count"] < 2 or _full(summary["latest_outcome"]):
            continue
        chain_ids = {formal["attempt_id"], *summary["revision_ids"]}
        counts = Counter(event["code"] for event in events if event["attempt_id"] in chain_ids)
        target_codes = sorted(counts)
        if not target_codes:
            continue
        task_type = formal["task_type"]
        if task_type == "academic_discussion":
            instruction = "Write 8 causal-chain items: claim → mechanism → concrete outcome/example → link back to your position."
        else:
            instruction = "Write 8 concise email sentences that complete the requested action and add one concrete supporting detail."
        recommendations.append(
            {
                "recommendation_id": f"PLAN-{formal['attempt_id']}",
                "source_attempt_id": formal["attempt_id"],
                "task_type": task_type,
                "target_codes": target_codes,
                "reason": f"Latest revision round remains unresolved after {summary['round_count']} rounds.",
                "drill": {
                    "item_count": 8,
                    "minimum_accuracy": 0.8,
                    "instruction": instruction,
                },
                "transfer_check": {
                    "new_prompt": True,
                    "target": "Use the same control in a fresh prompt before another revision round.",
                },
            }
        )
    return {"version": 1, "recommendations": recommendations}


def write_training_plan(root: Path) -> Path:
    plan = build_training_plan(root)
    path = root / "tracker/writing/training-plan.md"
    lines = ["# Writing Training Plan", "", "Derived from revision lineages; not a TOEFL score.", ""]
    if not plan["recommendations"]:
        lines.append("- No bounded recommendation currently due.")
    for recommendation in plan["recommendations"]:
        lines.extend(
            [
                f"## `{recommendation['recommendation_id']}`",
                f"- Route: `{recommendation['task_type']}`",
                f"- Source: `{recommendation['source_attempt_id']}`",
                f"- Targets: {', '.join(f'`{code}`' for code in recommendation['target_codes'])}",
                f"- Why: {recommendation['reason']}",
                f"- Drill: {recommendation['drill']['instruction']}",
                f"- Transfer: {recommendation['transfer_check']['target']}",
                "",
            ]
        )
    atomic_write_text(path, "\n".join(lines))
    return path
