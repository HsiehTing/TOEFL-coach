#!/usr/bin/env python3
"""Render the fixed diagnostic block for a prepared Speaking session."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from toefl_tracker.speaking_feedback import render_segment_usability_feedback


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared_session", type=Path)
    args = parser.parse_args(argv)
    artifact = json.loads(args.prepared_session.read_text(encoding="utf-8"))
    if not isinstance(artifact, dict):
        parser.error("prepared session must be a JSON object")
    mapping = artifact.get("mapping")
    quality = artifact.get("segment_quality")
    if not isinstance(mapping, dict) or not isinstance(quality, list):
        parser.error("prepared session must contain mapping and segment_quality")
    print(render_segment_usability_feedback(
        artifact.get("task_type"), quality, mapping.get("rows")
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
