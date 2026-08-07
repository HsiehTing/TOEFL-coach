"""Generate a learner-facing targeted Writing drill from a training-plan recommendation."""

import argparse
from pathlib import Path

from toefl_tracker.drill_generation import build_drill_pack, write_drill_pack
from toefl_tracker.models import ValidationError
from toefl_tracker.training_plan import build_training_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--recommendation-id")
    group.add_argument("--source-attempt-id")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    recommendations = build_training_plan(args.root)["recommendations"]
    recommendation = next(
        (
            row for row in recommendations
            if row["recommendation_id"] == args.recommendation_id
            or row["source_attempt_id"] == args.source_attempt_id
        ),
        None,
    )
    if recommendation is None:
        raise ValidationError("no current training-plan recommendation matches the requested identifier")
    pack = build_drill_pack(args.root, recommendation, seed=args.seed)
    destination = write_drill_pack(args.root, pack)
    print(destination / "drill.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
