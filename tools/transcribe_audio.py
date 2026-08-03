import argparse
import json
from pathlib import Path

from toefl_tracker.audio import AudioInspectionError
from toefl_tracker.transcription import preflight_audio_tools, transcribe_audio


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local-only TOEFL audio transcription.")
    parser.add_argument("audio", nargs="?", type=Path)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if not args.preflight and args.audio is None:
        parser.error("audio is required unless --preflight is used")
    try:
        dependencies = preflight_audio_tools()
        if args.preflight:
            print(json.dumps(dependencies.provenance, ensure_ascii=False, sort_keys=True))
            return 0
        print(json.dumps(transcribe_audio(args.audio, dependencies), ensure_ascii=False, indent=2))
        return 0
    except AudioInspectionError as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
