import argparse
import json
from pathlib import Path

from toefl_tracker.audio import AudioInspectionError, inspect_audio
from toefl_tracker.transcription import preflight_audio_tools


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if not args.preflight and args.audio is None:
        parser.error("audio is required unless --preflight is used")
    try:
        dependencies = preflight_audio_tools()
        if args.preflight:
            print(json.dumps(dependencies.provenance, ensure_ascii=False, sort_keys=True))
            return 0
        inspection = inspect_audio(
            args.audio,
            ffmpeg=dependencies.ffmpeg,
            ffprobe=dependencies.ffprobe,
            provenance=dependencies.provenance,
        )
        result = json.dumps(inspection, ensure_ascii=False, indent=2) + "\n"
    except AudioInspectionError as error:
        parser.error(str(error))
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
