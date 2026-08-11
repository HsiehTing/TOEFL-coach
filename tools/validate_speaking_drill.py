"""Preflight a transcript-supported Speaking drill before registration."""

import argparse
from pathlib import Path

from toefl_tracker.io import read_yaml
from toefl_tracker.speaking_practice import validate_transcript_drill


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--task-type", choices=("listen_and_repeat", "take_an_interview"), required=True)
    parser.add_argument("--drill", type=Path, required=True)
    args = parser.parse_args()
    validate_transcript_drill(args.root, args.task_type, read_yaml(args.drill))
    print("PASS transcript-supported Speaking drill contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
