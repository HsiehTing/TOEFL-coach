import argparse
import json
from pathlib import Path

import yaml

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.speaking import register_speaking_session
from toefl_tracker.speaking_transfer import prepare_speaking_transfer_attempt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--audio",
        type=Path,
        help="Private source audio path; required when inspection.json is path-free",
    )
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--inspection", type=Path, required=True)
    parser.add_argument(
        "--transcript-segments",
        type=Path,
        required=True,
        help="Explicit prompt/learner segment map supplied with the transcript",
    )
    parser.add_argument("--transfer-drill", help="Completed speaking drill attempt ID")
    parser.add_argument(
        "--confirmed-opportunities",
        type=Path,
        help="YAML mapping of target code to confirmed opportunity count",
    )
    parser.add_argument(
        "--transfer-outcomes",
        type=Path,
        help="YAML list of transcript-supported outcomes, one for each target code",
    )
    args = parser.parse_args()
    prompt = args.prompt.read_text(encoding="utf-8")
    transcript = args.transcript.read_text(encoding="utf-8")
    attempt = read_yaml(args.attempt)
    transfer_args = (args.transfer_drill, args.confirmed_opportunities, args.transfer_outcomes)
    if any(value is None for value in transfer_args) and any(value is not None for value in transfer_args):
        parser.error("--transfer-drill, --confirmed-opportunities, and --transfer-outcomes must be used together")
    if args.transfer_drill is not None:
        attempt = prepare_speaking_transfer_attempt(
            args.root,
            attempt,
            prompt,
            transcript,
            args.transfer_drill,
            yaml.safe_load(args.confirmed_opportunities.read_text(encoding="utf-8")),
            yaml.safe_load(args.transfer_outcomes.read_text(encoding="utf-8")),
        )
    attempt["source_hash"] = canonical_source_hash(prompt, transcript)
    events = [
        json.loads(line)
        for line in args.events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    segments = yaml.safe_load(args.segments.read_text(encoding="utf-8"))
    transcript_segments = yaml.safe_load(args.transcript_segments.read_text(encoding="utf-8"))
    inspection = json.loads(args.inspection.read_text(encoding="utf-8"))
    if args.audio is not None:
        inspection["path"] = str(args.audio.resolve())
    elif "path" not in inspection:
        parser.error("--audio is required when inspection.json is path-free")
    destination = register_speaking_session(
        args.root,
        read_yaml(args.root / "standards/ets-2026/manifest.yaml"),
        attempt,
        prompt,
        transcript,
        args.feedback.read_text(encoding="utf-8"),
        events,
        segments,
        inspection,
        transcript_segments,
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
