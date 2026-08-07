import argparse
from pathlib import Path

from toefl_tracker.legacy_migration import (
    build_legacy_migration_plan,
    write_legacy_compatibility,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--modality", choices=["writing", "speaking"], default="writing")
    parser.add_argument("--apply", action="store_true", help="write new compatibility metadata")
    args = parser.parse_args()
    plan = build_legacy_migration_plan(args.root, args.modality)
    if not args.apply:
        print("Dry run only. Re-run with --apply to write legacy-compat.yaml.")
        return 0
    print(write_legacy_compatibility(args.root, plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
