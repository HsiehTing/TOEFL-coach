import argparse
import json
from pathlib import Path

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.writing import register_writing_attempt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--response", type=Path)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--events", type=Path)
    args = parser.parse_args()
    manifest = read_yaml(args.root / "standards/ets-2026/manifest.yaml")
    attempt = read_yaml(args.attempt)
    if attempt.get("modality") == "speaking":
        parser.error("Speaking registration requires register_speaking_session.py")
    if attempt.get("modality") != "writing":
        parser.error("register_attempt.py accepts Writing attempts only")
    is_schema_two_reevaluation = (
        attempt.get("schema_version") == 2
        and attempt.get("record_type") == "re_evaluation"
    )
    if is_schema_two_reevaluation:
        prompt = response = ""
        events = []
    else:
        if args.prompt is None or args.response is None or args.events is None:
            parser.error("--prompt, --response, and --events are required for practice attempts")
        prompt = args.prompt.read_text()
        response = args.response.read_text()
        attempt["source_hash"] = canonical_source_hash(prompt, response)
        events = [
            json.loads(line) for line in args.events.read_text().splitlines() if line.strip()
        ]
    destination = register_writing_attempt(
        args.root,
        manifest,
        attempt,
        prompt,
        response,
        args.feedback.read_text(),
        events,
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
