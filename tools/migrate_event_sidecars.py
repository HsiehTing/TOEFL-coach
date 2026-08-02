import argparse
from pathlib import Path

from toefl_tracker.canonical import migrate_event_sidecars


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = migrate_event_sidecars(args.root, apply=args.apply)
    print(f"created={len(result.created)} unchanged={len(result.unchanged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
