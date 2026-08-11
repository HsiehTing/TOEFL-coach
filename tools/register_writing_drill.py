"""Register a non-scored Writing targeted drill and refresh mastery state."""

import argparse
import json
from pathlib import Path

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.drill_generation import (
    attach_generated_drill_lineage,
    read_completed_drill,
    retire_registered_drill_attempt_content,
    retire_registered_drill_pack,
)
from toefl_tracker.mastery import write_mastery
from toefl_tracker.models import ValidationError
from toefl_tracker.writing import register_writing_attempt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--pack", type=Path, help="Generated drill-pack directory containing drill.md")
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--response", type=Path)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--events", type=Path)
    parser.add_argument(
        "--item-results",
        type=Path,
        help="JSON list of per-item assessment results; defaults to <pack>/assessment.json",
    )
    args = parser.parse_args()

    manifest = read_yaml(args.root / "standards/ets-2026/manifest.yaml")
    attempt = read_yaml(args.attempt)
    generated_pack: dict | None = None
    if attempt.get("modality") != "writing" or attempt.get("record_type") != "targeted_drill":
        raise ValidationError("register_writing_drill.py requires a writing targeted_drill attempt")
    if args.pack is not None:
        if args.prompt is not None or args.response is not None:
            raise ValidationError("--pack cannot be combined with --prompt or --response")
        if args.events is not None:
            parser.error("--events is not supported for a result-only generated drill")
        completed = read_completed_drill(args.pack)
        prompt = completed["prompt"]
        response = completed["response"]
        generated_pack = completed["pack"]
        expected_pack_path = (
            args.root / "tracker/writing/drill-packs" / generated_pack["drill_id"]
        )
        if args.pack.resolve() != expected_pack_path.resolve():
            raise ValidationError("generated drill pack must be registered from the current tracker")
        attach_generated_drill_lineage(attempt, generated_pack)
        drill = attempt["drill"]
        if completed["pack"].get("version", 0) >= 5:
            item_results_path = args.item_results or args.pack / "assessment.json"
            if not item_results_path.exists():
                parser.error("complete <pack>/assessment.json or pass --item-results for a generated drill pack")
            try:
                item_results = json.loads(item_results_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ValidationError("--item-results must contain JSON") from error
            expected_ids = [item["item_id"] for item in completed["pack"]["items"]]
            if not isinstance(item_results, list) or {row.get("item_id") for row in item_results if isinstance(row, dict)} != set(expected_ids):
                raise ValidationError("--item-results must cover every generated drill item")
            drill["item_results"] = item_results
            drill["correct_count"] = sum(
                row.get("status") == "meets_target" for row in item_results if isinstance(row, dict)
            )
            metrics = attempt.setdefault("task_metrics", {})
            metrics["item_count"] = len(expected_ids)
            metrics["complete_item_count"] = drill["correct_count"]
            metrics["partial_item_count"] = sum(
                row.get("status") == "partially_meets_target" for row in item_results if isinstance(row, dict)
            )
    else:
        if args.prompt is None or args.response is None:
            parser.error("--prompt and --response are required unless --pack is supplied")
        prompt = args.prompt.read_text(encoding="utf-8")
        response = args.response.read_text(encoding="utf-8")
    attempt["source_hash"] = canonical_source_hash(prompt, response)
    events = [
        json.loads(line)
        for line in args.events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if args.events else []
    destination = register_writing_attempt(
        args.root,
        manifest,
        attempt,
        prompt,
        response,
        args.feedback.read_text(encoding="utf-8"),
        events,
    )
    if generated_pack is not None:
        retire_registered_drill_attempt_content(args.root, attempt["attempt_id"])
        retire_registered_drill_pack(args.root, generated_pack)
    write_mastery(args.root, attempt.get("task_type"))
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
