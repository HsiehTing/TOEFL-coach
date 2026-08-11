"""Validate a Speaking re-recording before any immutable registration."""

import argparse
from pathlib import Path

from toefl_tracker.io import read_yaml
from toefl_tracker.speaking_revision import validate_transcript_rerecording


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--task-type", required=True, choices=("listen_and_repeat", "take_an_interview"))
    parser.add_argument("--revision", type=Path, required=True)
    args = parser.parse_args()
    validate_transcript_rerecording(args.root, args.task_type, read_yaml(args.revision))
    print("PASS transcript-supported Speaking re-recording contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
