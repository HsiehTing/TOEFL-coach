#!/usr/bin/env python3
"""Prepare one Speaking recording and combine text with acoustic proxies."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from toefl_tracker.acoustic_evidence import build_acoustic_evidence, fuse_speaking_evidence
from toefl_tracker.audio import AudioInspectionError
from toefl_tracker.speaking_audio import prepare_speaking_session
from toefl_tracker.transcription import DEFAULT_MODEL, TranscriptionError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--task-type", choices=("listen_and_repeat", "take_an_interview"), required=True)
    parser.add_argument("--model", default=os.environ.get("TOEFL_WHISPER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--language", default="en")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        prepared = prepare_speaking_session(
            args.audio,
            args.task_type,
            model=args.model,
            language=args.language,
            include_segment_quality=True,
        )
        acoustic = build_acoustic_evidence(
            args.audio,
            prepared["mapping"],
            prepared["transcript"],
        )
        prepared["acoustic_evidence"] = acoustic
        prepared["combined_evidence"] = fuse_speaking_evidence(
            args.task_type,
            prepared["mapping"],
            prepared["segment_quality"],
            acoustic,
        )
    except (TranscriptionError, AudioInspectionError, ValueError) as error:
        print(f"speaking analysis error: {error}")
        return 2
    payload = json.dumps(prepared, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
