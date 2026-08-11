"""Create diagnostic-only assessment hints for a completed Writing drill."""

import argparse
from pathlib import Path

from toefl_tracker.drill_generation import write_assessment_hints


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    args = parser.parse_args()
    print(write_assessment_hints(args.pack))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
