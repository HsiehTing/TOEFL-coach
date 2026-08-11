"""Capture a reproducible coaching-system bug before implementation begins."""

import argparse
import json
from pathlib import Path

from toefl_tracker.bug_capture import bug_capture_receipt, capture_bug_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--roadmap", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--observed", required=True)
    parser.add_argument("--step", action="append", required=True)
    parser.add_argument("--affected-flow")
    parser.add_argument("--timing")
    parser.add_argument("--reproducibility")
    parser.add_argument("--impact")
    parser.add_argument("--attach", type=Path, action="append", default=[])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--include-git-diff",
        action="store_true",
        help="Explicitly retain current unstaged and staged diffs in the snapshot.",
    )
    parser.add_argument(
        "--confirm-safe-git-diff",
        action="store_true",
        help="Confirm that the current diff is necessary and safe to retain.",
    )
    args = parser.parse_args()
    report_dir = capture_bug_report(
            args.root,
            title=args.title,
            purpose=args.purpose,
            expected=args.expected,
            observed=args.observed,
            steps=args.step,
            affected_flow=args.affected_flow,
            timing=args.timing,
            reproducibility=args.reproducibility,
            impact=args.impact,
            attachments=args.attach,
            include_git_diff=args.include_git_diff,
            confirm_safe_git_diff=args.confirm_safe_git_diff,
            roadmap=args.roadmap,
    )
    if args.format == "json":
        print(json.dumps(bug_capture_receipt(args.root, report_dir, roadmap=args.roadmap), ensure_ascii=False, sort_keys=True))
    else:
        print(report_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
