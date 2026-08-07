import argparse
from pathlib import Path

from toefl_tracker.calibration import validate_writing_calibration


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    for row in validate_writing_calibration(args.root):
        print(f"PASS {row['case_id']} | {row['task_type']} | simulated task score {row['score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
