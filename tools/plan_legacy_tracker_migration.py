import argparse
import sys
from pathlib import Path

import yaml

from toefl_tracker.legacy_migration import build_legacy_migration_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--modality", choices=["writing", "speaking"], default="writing")
    args = parser.parse_args()
    yaml.safe_dump(build_legacy_migration_plan(args.root, args.modality), sys.stdout, allow_unicode=True, sort_keys=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
