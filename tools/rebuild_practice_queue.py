import argparse
from pathlib import Path

from toefl_tracker.practice_queue import write_practice_queue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(write_practice_queue(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
