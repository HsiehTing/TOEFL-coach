"""Build a compact, privacy-safe derived index of captured bugs."""

import argparse
from pathlib import Path

from toefl_tracker.bug_capture import write_bug_index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--roadmap", type=Path)
    args = parser.parse_args()
    print(write_bug_index(args.root, roadmap=args.roadmap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
