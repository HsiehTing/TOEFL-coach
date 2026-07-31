import argparse
import json
from pathlib import Path

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.register import register_attempt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    args = parser.parse_args()
    manifest = read_yaml(args.root / "standards/ets-2026/manifest.yaml")
    events = [json.loads(line) for line in args.events.read_text().splitlines() if line.strip()]
    attempt = read_yaml(args.attempt)
    prompt = args.prompt.read_text()
    response = args.response.read_text()
    attempt["source_hash"] = canonical_source_hash(prompt, response)
    destination = register_attempt(
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
