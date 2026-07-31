import argparse
from pathlib import Path

from toefl_tracker.reports import rebuild_modality


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--modality",
        choices=["writing", "speaking", "all"],
        default="all",
    )
    args = parser.parse_args()
    modalities = (
        ["writing", "speaking"]
        if args.modality == "all"
        else [args.modality]
    )
    for modality in modalities:
        for path in rebuild_modality(args.root, modality):
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
