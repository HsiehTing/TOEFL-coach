import argparse
from pathlib import Path

from toefl_tracker.revision_learning import write_revision_learning


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(write_revision_learning(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
