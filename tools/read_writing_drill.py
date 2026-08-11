"""Read completed learner responses from a generated Writing drill pack."""

import argparse
from pathlib import Path

from toefl_tracker.drill_generation import read_completed_drill


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pack",
        type=Path,
        required=True,
        help="Generated drill-pack directory containing drill.md",
    )
    args = parser.parse_args()
    completed = read_completed_drill(args.pack)
    pack = completed["pack"]
    responses = completed["responses"]
    print(f"Pack: {pack.get('drill_id', args.pack.name)}")
    print(f"Completed items: {len(responses)}/{len(pack['items'])}")
    for item in pack["items"]:
        item_id = item["item_id"]
        for field in item["response_fields"]:
            print(f"{item_id}.{field}: {responses[item_id][field]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
