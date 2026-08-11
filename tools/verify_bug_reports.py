"""Verify Bug Capture artifact and roadmap-link integrity without changing data."""

import argparse
import json
from pathlib import Path

from toefl_tracker.bug_capture import verify_bug_reports


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--roadmap", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    problems = verify_bug_reports(args.root, roadmap=args.roadmap)
    if problems:
        print(json.dumps({"passed": False, "problems": problems}, ensure_ascii=False) if args.format == "json" else "\n".join(problems))
        return 1
    print(json.dumps({"passed": True, "problems": []}, ensure_ascii=False) if args.format == "json" else "PASS Bug Capture artifact and roadmap integrity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
