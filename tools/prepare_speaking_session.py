"""Create private, review-only TOEFL speaking intake artifacts."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

import yaml

from toefl_tracker.audio import AudioInspectionError, inspect_audio, inspect_segment_quality
from toefl_tracker.models import ValidationError
from toefl_tracker.role_mapping import infer_toefl_role_map
from toefl_tracker.transcription import preflight_audio_tools, transcribe_audio
from toefl_tracker.quality import quality_decision


def _dimensions(task_type: str, dimension_set: str) -> list[str]:
    text = {"content", "grammar", "vocabulary"}
    if task_type == "listen_and_repeat":
        text.add("reconstruction")
    if dimension_set == "text_only":
        return sorted(text)
    if dimension_set == "all":
        dimensions = {
            "content", "intelligibility", "pronunciation", "prosody", "fluency",
            "grammar", "vocabulary",
        }
        if task_type == "listen_and_repeat":
            dimensions.add("reconstruction")
        else:
            dimensions.update({"directness", "relevance", "elaboration", "coherence"})
        return sorted(dimensions)
    return []


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
        learner_rows = [row.artifact() for row in mapping.rows if row.role == "learner"]
        measured = inspect_segment_quality(
            args.audio,
            learner_rows,
            ffmpeg=dependencies.ffmpeg,
        )
    except (AudioInspectionError, ValidationError) as error:
        parser.error(str(error))

    segment_quality = []
    for learner, metrics in zip(learner_rows, measured):
        decision = quality_decision({
            "mean_dbfs": metrics["mean_dbfs"],
            "peak_dbfs": metrics["peak_dbfs"],
            "decodable": True,
        })
        segment_quality.append({
            "segment_id": learner["segment_id"],
            "start": learner["start"],
            "end": learner["end"],
            **metrics,
            "decodable": True,
            "quality": {
                "policy_version": decision.policy_version,
                "standard_basis": decision.standard_basis,
                "usable": decision.usable,
                "dimension_set": decision.dimension_set,
            },
            "reliable_dimensions": _dimensions(args.task_type, decision.dimension_set),
        })
    inspection["segment_quality"] = segment_quality

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    artifact = mapping.artifact()
    artifact["transcript_rows"] = [
        {"segment_id": f"asr-{index:03d}", **row}
        for index, row in enumerate(transcript_rows, start=1)
    ]
    review_inspection = dict(inspection)
    # Keep the review artifact path-free; registration receives the private
    # audio path explicitly and persists only the opaque source reference.
    review_inspection.pop("path", None)
    (output / "audio-inspection.json").write_text(
        json.dumps(review_inspection, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
