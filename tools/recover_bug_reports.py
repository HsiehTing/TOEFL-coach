"""Recover complete Bug Capture reports whose roadmap link was interrupted."""

import argparse
from pathlib import Path

from toefl_tracker.bug_capture import recover_bug_reports


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--roadmap", type=Path)
    args = parser.parse_args()
    for path in recover_bug_reports(args.root, roadmap=args.roadmap):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
