import argparse
from pathlib import Path

from toefl_tracker.legacy_migration import apply_approved_legacy_review
from toefl_tracker.legacy_review import build_legacy_review


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Append reviewed legacy exceptions without modifying source attempts or events."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--modality", choices=("writing", "speaking"), default="writing")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--apply", action="store_true", help="write legacy-compat.yaml after reviewing findings")
    args = parser.parse_args()
    review = build_legacy_review(args.root, args.modality)
    if not args.apply:
        print("Dry run only. Re-run with --apply to append the reviewed exceptions.")
        print(review["summary"])
        return 0
    print(apply_approved_legacy_review(args.root, review, reason=args.reason))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
