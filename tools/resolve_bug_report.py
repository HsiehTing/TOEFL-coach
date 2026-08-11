"""Append immutable investigation/closure evidence for a captured Bug ID."""

import argparse
from pathlib import Path

from toefl_tracker.bug_capture import append_bug_resolution


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--roadmap", type=Path)
    parser.add_argument("--bug-id", required=True)
    parser.add_argument("--outcome", required=True, choices=("fixed_verified", "duplicate", "cannot_reproduce", "wont_fix"))
    parser.add_argument("--diagnosis", required=True)
    parser.add_argument("--fix-reference")
    parser.add_argument("--validation-command", required=True)
    parser.add_argument("--validation-result", required=True)
    args = parser.parse_args()
    print(append_bug_resolution(args.root, bug_id=args.bug_id, outcome=args.outcome, diagnosis=args.diagnosis, fix_reference=args.fix_reference, validation_command=args.validation_command, validation_result=args.validation_result, roadmap=args.roadmap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
