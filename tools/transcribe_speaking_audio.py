#!/usr/bin/env python3
"""Transcribe a TOEFL Speaking audio file locally and emit path-free JSON."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from toefl_tracker.transcription import DEFAULT_MODEL, TranscriptionError, dump_transcription, transcribe_audio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="local audio file (for example .m4a or .wav)")
    parser.add_argument(
        "--model",
        default=os.environ.get("TOEFL_WHISPER_MODEL", DEFAULT_MODEL),
        help="local model path or Hugging Face model identifier",
    )
    parser.add_argument("--language", default="en", help="language code passed to the local ASR backend")
    parser.add_argument("--output", type=Path, help="optional JSON output path; stdout is used by default")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        artifact = transcribe_audio(args.audio, model=args.model, language=args.language)
        dump_transcription(artifact, args.output)
    except TranscriptionError as error:
        print(f"transcription error: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
