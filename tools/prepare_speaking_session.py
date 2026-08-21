#!/usr/bin/env python3
"""Prepare a local TOEFL Speaking audio session for route-specific diagnosis."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from toefl_tracker.speaking_audio import prepare_speaking_session
from toefl_tracker.transcription import DEFAULT_MODEL, TranscriptionError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="local audio file")
    parser.add_argument(
        "--task-type",
        choices=("listen_and_repeat", "take_an_interview"),
        required=True,
        help="TOEFL Speaking route for the recording",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("TOEFL_WHISPER_MODEL", DEFAULT_MODEL),
        help="local model path or Hugging Face model identifier",
    )
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--include-segment-quality",
        action="store_true",
        help="measure learner-turn recording quality with local ffmpeg",
    )
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        artifact = prepare_speaking_session(
            args.audio,
            args.task_type,
            model=args.model,
            language=args.language,
            include_segment_quality=args.include_segment_quality,
        )
    except (TranscriptionError, ValueError) as error:
        print(f"speaking preparation error: {error}")
        return 2
    payload = json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
