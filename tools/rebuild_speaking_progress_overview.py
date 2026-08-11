"""Rebuild the transcript-bounded Speaking progress overview."""

import argparse
from pathlib import Path

from toefl_tracker.speaking_progress import write_speaking_progress_overview


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(write_speaking_progress_overview(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
