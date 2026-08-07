"""Register a scored new-prompt Writing transfer attempt."""

import argparse
import json
from pathlib import Path

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.mastery import write_mastery
from toefl_tracker.transfer import prepare_transfer_attempt
from toefl_tracker.writing import register_writing_attempt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--drill-attempt-id", required=True)
    parser.add_argument("--confirmed-opportunities", type=json.loads, required=True)
    args = parser.parse_args()
    prompt = args.prompt.read_text(encoding="utf-8")
    response = args.response.read_text(encoding="utf-8")
    attempt = prepare_transfer_attempt(args.root, read_yaml(args.attempt), prompt, args.drill_attempt_id, args.confirmed_opportunities)
    attempt["source_hash"] = canonical_source_hash(prompt, response)
    events = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines() if line.strip()]
    destination = register_writing_attempt(args.root, read_yaml(args.root / "standards/ets-2026/manifest.yaml"), attempt, prompt, response, args.feedback.read_text(encoding="utf-8"), events)
    write_mastery(args.root, attempt["task_type"])
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
