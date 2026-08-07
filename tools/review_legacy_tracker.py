import argparse
import sys
from pathlib import Path

import yaml

from toefl_tracker.legacy_review import build_legacy_review, write_legacy_review


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review legacy tracker incompatibilities without modifying source records."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--modality", choices=("writing", "speaking"), default="writing")
    parser.add_argument("--output", type=Path, help="optional explicit YAML destination")
    args = parser.parse_args()
    review = build_legacy_review(args.root, args.modality)
    if args.output is not None:
        print(write_legacy_review(args.output, review))
    else:
        yaml.safe_dump(review, sys.stdout, allow_unicode=True, sort_keys=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
