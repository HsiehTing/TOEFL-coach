"""Register a non-scored Writing targeted drill and refresh mastery state."""

import argparse
import json
from pathlib import Path

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.drill_generation import read_completed_drill
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
    args = parser.parse_args()

    manifest = read_yaml(args.root / "standards/ets-2026/manifest.yaml")
    attempt = read_yaml(args.attempt)
    if attempt.get("modality") != "writing" or attempt.get("record_type") != "targeted_drill":
        raise ValidationError("register_writing_drill.py requires a writing targeted_drill attempt")
    if args.pack is not None:
        if args.prompt is not None or args.response is not None:
            raise ValidationError("--pack cannot be combined with --prompt or --response")
        completed = read_completed_drill(args.pack)
        prompt = completed["prompt"]
        response = completed["response"]
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
    write_mastery(args.root, attempt.get("task_type"))
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
