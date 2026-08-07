import argparse
from pathlib import Path

from toefl_tracker.training_plan import write_training_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(write_training_plan(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
