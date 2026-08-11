"""Register a reviewed transcript-supported Speaking drill as result-only evidence."""

import argparse
from pathlib import Path

from toefl_tracker.io import read_yaml
from toefl_tracker.speaking_practice import register_transcript_drill


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--drill", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    args = parser.parse_args()

    destination = register_transcript_drill(
        args.root,
        read_yaml(args.root / "standards/ets-2026/manifest.yaml"),
        read_yaml(args.attempt),
        read_yaml(args.drill),
        args.feedback.read_text(encoding="utf-8"),
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
