import argparse
import json
from pathlib import Path

import yaml

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.speaking import register_speaking_session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--inspection", type=Path, required=True)
    parser.add_argument("--transcript-segments", type=Path)
    args = parser.parse_args()
    prompt = args.prompt.read_text()
    transcript = args.transcript.read_text()
    attempt = read_yaml(args.attempt)
    attempt["source_hash"] = canonical_source_hash(prompt, transcript)
    events = [
        json.loads(line)
        for line in args.events.read_text().splitlines()
        if line.strip()
    ]
    segments = yaml.safe_load(args.segments.read_text())
    transcript_segments = (
        yaml.safe_load(args.transcript_segments.read_text())
        if args.transcript_segments is not None
        else []
    )
    inspection = json.loads(args.inspection.read_text())
    destination = register_speaking_session(
        args.root,
        read_yaml(args.root / "standards/ets-2026/manifest.yaml"),
        attempt,
        prompt,
        transcript,
        args.feedback.read_text(),
        events,
        segments,
        inspection,
        transcript_segments,
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
