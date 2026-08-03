"""Create private, review-only TOEFL speaking intake artifacts."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

import yaml

from toefl_tracker.audio import AudioInspectionError, inspect_audio
from toefl_tracker.models import ValidationError
from toefl_tracker.role_mapping import infer_toefl_role_map
from toefl_tracker.transcription import preflight_audio_tools, transcribe_audio


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a local TOEFL speaking transcript for coach review.")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--task-type", required=True, choices=("listen_and_repeat", "take_an_interview"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        dependencies = preflight_audio_tools()
        inspection = inspect_audio(
            args.audio,
            ffmpeg=dependencies.ffmpeg,
            ffprobe=dependencies.ffprobe,
            provenance=dependencies.provenance,
        )
        transcript_rows = transcribe_audio(args.audio, dependencies)
        mapping = infer_toefl_role_map(args.task_type, transcript_rows)
    except (AudioInspectionError, ValidationError) as error:
        parser.error(str(error))

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    artifact = mapping.artifact()
    artifact["transcript_rows"] = [
        {"segment_id": f"asr-{index:03d}", **row}
        for index, row in enumerate(transcript_rows, start=1)
    ]
    (output / "audio-inspection.json").write_text(
        json.dumps(inspection, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "transcript-segments.yaml").write_text(
        yaml.safe_dump(artifact, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (output / "segments.yaml").write_text(
        yaml.safe_dump([row.artifact() for row in mapping.rows], allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (output / "source-reference.txt").write_text(
        "source:" + sha256(str(args.audio.resolve()).encode("utf-8")).hexdigest() + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
