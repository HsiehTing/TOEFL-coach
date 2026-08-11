"""Create disposable coach-review aids for a completed Writing drill."""

import argparse
from pathlib import Path

from toefl_tracker.drill_generation import write_assessment_hints, write_assessment_review


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    args = parser.parse_args()
    print(write_assessment_hints(args.pack))
    print(write_assessment_review(args.pack))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
