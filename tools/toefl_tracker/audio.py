import json
import re
import subprocess
from collections.abc import Callable, Mapping
from math import isfinite
from pathlib import Path


class AudioInspectionError(RuntimeError):
    pass


def _run(runner: Callable, command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        result = runner(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise AudioInspectionError(f"{command[0]} unavailable: {error}") from error
    if result.returncode != 0:
        raise AudioInspectionError(result.stderr.strip() or f"{command[0]} failed")
    return result


def _finite_float(value: object) -> float:
    parsed = float(value)
    if not isfinite(parsed):
        raise ValueError
    return parsed


def _quality_artifact(metrics: Mapping[str, object]) -> dict:
    # Import lazily because quality shares AudioInspectionError with this module.
    from toefl_tracker.quality import quality_decision

    decision = quality_decision(metrics)
    return {
        "policy_version": decision.policy_version,
        "standard_basis": decision.standard_basis,
        "usable": decision.usable,
        "dimension_set": decision.dimension_set,
    }


def inspect_audio(
    path: Path,
    runner: Callable = subprocess.run,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    provenance: Mapping[str, object] | None = None,
) -> dict:
    if not path.is_file():
        raise AudioInspectionError(f"audio file not found: {path}")
    probe = _run(runner, [
        ffprobe, "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,sample_rate,channels",
        "-of", "json", str(path),
    ])
    try:
        payload = json.loads(probe.stdout)
        if not isinstance(payload, dict):
            raise ValueError
        streams = payload.get("streams", [])
        if not isinstance(streams, list):
            raise ValueError
        stream = next(
            (row for row in streams if isinstance(row, dict) and row.get("codec_type") == "audio"),
            None,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise AudioInspectionError("invalid ffprobe JSON") from error
    if stream is None:
        raise AudioInspectionError("no decodable audio stream")
    try:
        duration = _finite_float(payload["format"]["duration"])
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        codec = stream["codec_name"]
        if duration < 0 or sample_rate <= 0 or channels <= 0 or not isinstance(codec, str) or not codec:
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise AudioInspectionError("invalid audio metadata") from error

    volume = _run(runner, [
        ffmpeg, "-nostdin", "-hide_banner", "-i", str(path),
        "-af", "volumedetect", "-f", "null", "-",
    ])
    diagnostics = volume.stderr + "\n" + volume.stdout
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", diagnostics)
    peak_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", diagnostics)
    if not mean_match or not peak_match:
        raise AudioInspectionError("ffmpeg did not return volume metrics")
    try:
        mean = _finite_float(mean_match.group(1))
        peak = _finite_float(peak_match.group(1))
    except ValueError as error:
        raise AudioInspectionError("invalid volume metrics") from error
    result = {
        "path": str(path.resolve()),
        "duration_seconds": duration,
        "codec": codec,
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "mean_dbfs": mean,
        "peak_dbfs": peak,
        "clipping": peak >= -0.1,
        "decodable": True,
    }
    result["quality"] = _quality_artifact(result)
    if provenance is not None:
        result["provenance"] = dict(provenance)
    return result


def inspect_segment_quality(
    path: Path, segments: list[dict], runner: Callable = subprocess.run, *, ffmpeg: str = "ffmpeg"
) -> list[dict]:
    """Measure only caller-supplied time ranges without retaining the source path."""
    if not path.is_file():
        raise AudioInspectionError(f"audio file not found: {path}")
    if not isinstance(segments, list):
        raise AudioInspectionError("segments must be a list")
    rows: list[dict] = []
    for segment in segments:
        try:
            start = _finite_float(segment["start"])
            end = _finite_float(segment["end"])
            if start < 0 or end <= start:
                raise ValueError
        except (KeyError, TypeError, ValueError) as error:
            raise AudioInspectionError("invalid segment boundaries") from error
        volume = _run(runner, [
            ffmpeg, "-nostdin", "-hide_banner", "-ss", str(start), "-t", str(end - start),
            "-i", str(path), "-af", "volumedetect", "-f", "null", "-",
        ])
        diagnostics = volume.stderr + "\n" + volume.stdout
        mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", diagnostics)
        peak_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", diagnostics)
        if not mean_match or not peak_match:
            raise AudioInspectionError("ffmpeg did not return volume metrics")
        try:
            mean = _finite_float(mean_match.group(1))
            peak = _finite_float(peak_match.group(1))
        except ValueError as error:
            raise AudioInspectionError("invalid volume metrics") from error
        rows.append({
            "start": start,
            "end": end,
            "mean_dbfs": mean,
            "peak_dbfs": peak,
            "clipping": peak >= -0.1,
        })
    return rows
