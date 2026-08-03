import json
from hashlib import sha256
import sys
import subprocess
from pathlib import Path

import pytest
import yaml

import toefl_tracker.register as register_module
from register_speaking_session import main as register_speaking_main
from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.audio import inspect_audio
from toefl_tracker.speaking import (
    build_speaking_registration,
    register_speaking_session,
    validate_persisted_inspection,
    validate_speaking_assessment,
)


ROOT = Path(__file__).parents[1]
MANIFEST = yaml.safe_load(
    (ROOT / "standards/ets-2026/manifest.yaml").read_text()
)


def session(task_type: str) -> dict:
    return {
        "modality": "speaking",
        "task_type": task_type,
        "record_type": "formal_original",
        "rubric_version": "ets-speaking-blueprint-2026-diagnostic",
        "result_type": "diagnostic_only",
        "audio_quality": {"decodable": True, "clipping": False},
    }


def segments(count: int, confidence: str = "high") -> list[dict]:
    rows = []
    for item in range(1, count + 1):
        rows.extend(
            [
                {
                    "item": item,
                    "role": "examiner",
                    "start": item * 10.0,
                    "end": item * 10.0 + 2.0,
                    "confidence": confidence,
                },
                {
                    "item": item,
                    "role": "learner",
                    "start": item * 10.0 + 2.2,
                    "end": item * 10.0 + 7.0,
                    "confidence": confidence,
                },
            ]
        )
    return rows


FEEDBACK = """# Result
Diagnostic only.
# Why this level
Evidence.
# Why not the next level
Evidence.
# Timestamp evidence
00:13–00:14 omission.
# Priorities
1. Preserve function words.
# Re-record task
Re-record items 2 and 4.
"""


def registration_attempt(
    prompt: str,
    transcript: str,
    attempt_id: str = "S-LR-20260731-001",
) -> dict:
    return {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "modality": "speaking",
        "task_type": "listen_and_repeat",
        "record_type": "formal_original",
        "submitted_at": "2026-07-31T10:00:00+08:00",
        "practiced_at": "2026-07-31",
        "timed": True,
        "duration_seconds": 120,
        "assistance": {
            "spellcheck": None,
            "translation": None,
            "other": None,
        },
        "rubric_version": "ets-speaking-blueprint-2026-diagnostic",
        "standard_verified_at": "2026-07-31",
        "result_type": "diagnostic_only",
        "audio_quality": {"decodable": True, "clipping": False},
        "task_metrics": {
            "reconstruction": "partial",
            "intelligibility": "adequate",
        },
        "source_hash": canonical_source_hash(prompt, transcript),
        "opportunities": {"LR-OMISSION": 7},
        "parent_attempt_id": None,
        "revision_outcomes": None,
    }


def inspection(path: str) -> dict:
    return {
        "path": path,
        "duration_seconds": 120.0,
        "codec": "aac",
        "sample_rate_hz": 48000,
        "channels": 1,
        "mean_dbfs": -30.0,
        "peak_dbfs": -5.4,
        "clipping": False,
        "decodable": True,
        "quality": {
            "policy_version": 1,
            "standard_basis": "diagnostic_internal",
            "usable": True,
            "dimension_set": "all",
        },
        "provenance": {
            "executables": {"ffmpeg": "ffmpeg 8.1", "ffprobe": "ffprobe 8.1", "whisper-cli": "whisper 1.9"},
            "model_identifier": "ggml-small.en.bin",
            "model_sha256": "0" * 64,
        },
        "reliable_dimensions": [
            "intelligibility", "pronunciation", "prosody", "fluency", "grammar",
            "vocabulary", "reconstruction", "directness", "relevance", "elaboration", "coherence",
        ],
    }


def counted_event(attempt_id: str = "S-LR-20260731-001") -> dict:
    return {
        "event_id": "ERR-20260731-0001",
        "attempt_id": attempt_id,
        "taxonomy_version": 1,
        "code": "LR-OMISSION",
        "source_excerpt": None,
        "audio_timestamp": "00:13–00:14",
        "suggested_revision": "Repeat the omitted function word.",
        "reason": "The source word is absent.",
        "level": "must_fix",
        "severity": "clarity_reducing",
        "task_specific": True,
        "opportunity_present": True,
        "historical_status": "new",
    }


def test_seven_repeat_items_form_one_session() -> None:
    validate_speaking_assessment(
        session("listen_and_repeat"),
        segments(7),
        [],
        FEEDBACK,
    )


def test_four_interview_questions_form_one_session() -> None:
    validate_speaking_assessment(
        session("take_an_interview"),
        segments(4),
        [],
        FEEDBACK,
    )


def test_incomplete_or_ambiguous_mapping_blocks_formal_assessment() -> None:
    with pytest.raises(ValidationError, match="mapping"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            segments(6),
            [],
            FEEDBACK,
        )
    with pytest.raises(ValidationError, match="confirmation"):
        validate_speaking_assessment(
            session("take_an_interview"),
            segments(4, "low"),
            [],
            FEEDBACK,
        )


def test_ambiguous_mapping_can_be_explicitly_confirmed() -> None:
    rows = segments(4, "low")
    for row in rows:
        row["confirmed_by_user"] = True
    validate_speaking_assessment(
        session("take_an_interview"),
        rows,
        [],
        FEEDBACK,
    )


@pytest.mark.parametrize("attempt", [None, [], "session"])
def test_attempt_must_be_a_mapping(attempt: object) -> None:
    with pytest.raises(ValidationError, match="attempt"):
        validate_speaking_assessment(attempt, segments(7), [], FEEDBACK)


def test_task_type_must_be_a_string() -> None:
    attempt = session("listen_and_repeat")
    attempt["task_type"] = []
    with pytest.raises(ValidationError, match="task"):
        validate_speaking_assessment(attempt, segments(7), [], FEEDBACK)


def test_segments_and_events_must_be_lists_of_mappings() -> None:
    with pytest.raises(ValidationError, match="segments"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            {},
            [],
            FEEDBACK,
        )
    rows = segments(7)
    rows[0] = None
    with pytest.raises(ValidationError, match="segment"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            rows,
            [],
            FEEDBACK,
        )
    with pytest.raises(ValidationError, match="events"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            segments(7),
            {},
            FEEDBACK,
        )
    with pytest.raises(ValidationError, match="event"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            segments(7),
            [None],
            FEEDBACK,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("item", True, "item"),
        ("item", 8, "item"),
        ("role", "coach", "role"),
        ("role", [], "role"),
        ("start", True, "time"),
        ("start", -1.0, "time"),
        ("start", float("nan"), "time"),
        ("end", 10.0, "time"),
        ("confidence", "certain", "confidence"),
        ("confidence", [], "confidence"),
    ],
)
def test_segment_fields_have_strict_types_and_ranges(
    field: str,
    value: object,
    message: str,
) -> None:
    rows = segments(7)
    rows[0][field] = value
    with pytest.raises(ValidationError, match=message):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            rows,
            [],
            FEEDBACK,
        )


def test_duplicate_role_does_not_satisfy_item_mapping() -> None:
    rows = segments(7)
    rows[1]["role"] = "examiner"
    with pytest.raises(ValidationError, match="mapping"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            rows,
            [],
            FEEDBACK,
        )


def test_segment_list_must_follow_item_and_role_order() -> None:
    rows = segments(7)
    rows[0]["role"], rows[1]["role"] = (
        rows[1]["role"],
        rows[0]["role"],
    )
    with pytest.raises(ValidationError, match="order"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            rows,
            [],
            FEEDBACK,
        )


def test_segment_time_ranges_must_not_overlap() -> None:
    rows = segments(7)
    rows[1]["start"] = rows[0]["end"] - 0.1
    with pytest.raises(ValidationError, match="overlap|chronological"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            rows,
            [],
            FEEDBACK,
        )


def test_segment_time_cannot_exceed_session_duration() -> None:
    attempt = session("listen_and_repeat")
    attempt["duration_seconds"] = 120
    rows = segments(7)
    rows[0]["end"] = 120.1
    with pytest.raises(ValidationError, match="duration"):
        validate_speaking_assessment(attempt, rows, [], FEEDBACK)


def test_audio_quality_requires_a_decodable_boolean_mapping() -> None:
    attempt = session("listen_and_repeat")
    attempt["audio_quality"] = []
    with pytest.raises(ValidationError, match="audio_quality"):
        validate_speaking_assessment(attempt, segments(7), [], FEEDBACK)

    attempt["audio_quality"] = {"decodable": 1, "clipping": "no"}
    with pytest.raises(ValidationError, match="audio_quality"):
        validate_speaking_assessment(attempt, segments(7), [], FEEDBACK)

    attempt["audio_quality"] = {"decodable": False, "clipping": False}
    with pytest.raises(ValidationError, match="decodable"):
        validate_speaking_assessment(attempt, segments(7), [], FEEDBACK)


def test_speaking_result_is_diagnostic_only() -> None:
    attempt = session("listen_and_repeat")
    attempt["result_type"] = "official_task_score"
    with pytest.raises(ValidationError, match="diagnostic_only"):
        validate_speaking_assessment(attempt, segments(7), [], FEEDBACK)


@pytest.mark.parametrize(
    "feedback",
    [
        FEEDBACK.replace("# Timestamp evidence\n", ""),
        FEEDBACK.replace(
            "# Timestamp evidence\n",
            "# Timestamp evidence\n# Timestamp evidence\n",
            1,
        ),
        FEEDBACK.replace("# Why this level", "# TEMPORARY")
        .replace("# Why not the next level", "# Why this level")
        .replace("# TEMPORARY", "# Why not the next level"),
        FEEDBACK.replace("# Result", "Embedded prose: # Result"),
    ],
    ids=["missing", "duplicate", "wrong-order", "embedded-prose"],
)
def test_feedback_requires_unique_ordered_markdown_headings(
    feedback: str,
) -> None:
    with pytest.raises(ValidationError, match="headings"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            segments(7),
            [],
            feedback,
        )


def test_feedback_allows_at_most_three_priorities() -> None:
    feedback = FEEDBACK.replace(
        "1. Preserve function words.",
        "1. One\n2. Two\n3. Three\n4. Four",
    )
    with pytest.raises(ValidationError, match="three priorities"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            segments(7),
            [],
            feedback,
        )


@pytest.mark.parametrize(
    "timestamp",
    [None, 12, "", "00:70", "00:14–00:12"],
)
def test_counted_event_requires_a_valid_timestamp(timestamp: object) -> None:
    event = {
        "event_id": "S-1",
        "level": "must_fix",
        "audio_timestamp": timestamp,
    }
    with pytest.raises(ValidationError, match="timestamp"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            segments(7),
            [event],
            FEEDBACK,
        )


def test_counted_timestamp_must_appear_in_timestamp_evidence_section() -> None:
    feedback = FEEDBACK.replace(
        "Diagnostic only.",
        "Diagnostic only. 00:22–00:24.",
    )
    event = {
        "event_id": "S-1",
        "level": "must_fix",
        "audio_timestamp": "00:22–00:24",
    }
    with pytest.raises(ValidationError, match="timestamp"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            segments(7),
            [event],
            feedback,
        )


def test_counted_timestamp_cannot_exceed_session_duration() -> None:
    attempt = session("listen_and_repeat")
    attempt["duration_seconds"] = 10
    event = {
        "event_id": "S-1",
        "level": "should_fix",
        "audio_timestamp": "00:13–00:14",
    }
    with pytest.raises(ValidationError, match="duration"):
        validate_speaking_assessment(
            attempt,
            segments(7),
            [event],
            FEEDBACK,
        )


def test_counted_timestamp_exactly_present_is_accepted() -> None:
    event = {
        "event_id": "S-1",
        "level": "must_fix",
        "audio_timestamp": "00:13–00:14",
    }
    validate_speaking_assessment(
        session("listen_and_repeat"),
        segments(7),
        [event],
        FEEDBACK,
    )


def test_polish_event_does_not_require_timestamp_evidence() -> None:
    event = {
        "event_id": "S-OPTIONAL",
        "level": "polish",
        "audio_timestamp": None,
    }
    validate_speaking_assessment(
        session("listen_and_repeat"),
        segments(7),
        [event],
        FEEDBACK,
    )


def test_event_level_must_be_a_string() -> None:
    event = {
        "event_id": "S-1",
        "level": [],
        "audio_timestamp": "00:12–00:14",
    }
    with pytest.raises(ValidationError, match="level"):
        validate_speaking_assessment(
            session("listen_and_repeat"),
            segments(7),
            [event],
            FEEDBACK,
        )


def test_registration_persists_artifacts_without_copying_raw_audio(
    tmp_path: Path,
) -> None:
    source = tmp_path / "private/practice.m4a"
    source.parent.mkdir()
    source.write_bytes(b"private audio")
    root = tmp_path / "workspace"
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"

    path = register_speaking_session(
        root,
        MANIFEST,
        registration_attempt(prompt, transcript),
        prompt,
        transcript,
        FEEDBACK,
        [],
        segments(7),
        inspection(str(source)),
    )

    inspection_data = json.loads((path / "audio-inspection.json").read_text())
    assert "path" not in inspection_data
    assert str(source) not in (path / "audio-inspection.json").read_text()
    assert (path / "segments.yaml").exists()
    assert (path / "source-reference.txt").read_text() == (
        f"source:{sha256(str(source).encode('utf-8')).hexdigest()}\n"
    )
    assert not list(path.glob("*.m4a"))
    assert source.read_bytes() == b"private audio"


def test_audio_inspection_artifact_is_accepted_by_speaking_gate(tmp_path: Path) -> None:
    source = tmp_path / "private/practice.m4a"
    source.parent.mkdir()
    source.write_bytes(b"private audio")
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    provenance = {
        "executables": {"ffmpeg": "ffmpeg 8.1", "ffprobe": "ffprobe 8.1", "whisper-cli": "whisper 1.9"},
        "model_identifier": "ggml-small.en.bin",
        "model_sha256": "0" * 64,
    }

    def runner(command: list[str], **kwargs: object):
        if command[0] == "/resolved/ffprobe":
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({
                    "format": {"duration": "120"},
                    "streams": [{"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 1}],
                }),
                "",
            )
        return subprocess.CompletedProcess(command, 0, "", "mean_volume: -30.0 dB\nmax_volume: -5.4 dB\n")

    artifact = inspect_audio(
        source,
        runner=runner,
        ffmpeg="/resolved/ffmpeg",
        ffprobe="/resolved/ffprobe",
        provenance=provenance,
    )
    destination = register_speaking_session(
        tmp_path / "workspace",
        MANIFEST,
        registration_attempt(prompt, transcript),
        prompt,
        transcript,
        FEEDBACK,
        [],
        segments(7),
        artifact,
    )

    persisted = json.loads((destination / "audio-inspection.json").read_text())
    assert persisted["quality"]["usable"] is True
    assert persisted["provenance"] == provenance


def test_registration_rejects_private_provenance_and_quality_mutation(tmp_path: Path) -> None:
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    private_provenance = inspection("/private/source/practice.m4a")
    private_provenance["provenance"]["model_path"] = "/private/model/ggml-small.en.bin"

    with pytest.raises(ValidationError, match="provenance"):
        register_speaking_session(
            tmp_path / "private-provenance",
            MANIFEST,
            registration_attempt(prompt, transcript),
            prompt,
            transcript,
            FEEDBACK,
            [],
            segments(7),
            private_provenance,
        )

    private_executable = inspection("/private/source/practice.m4a")
    private_executable["provenance"]["executables"]["ffmpeg"] = "/private/bin/ffmpeg"

    with pytest.raises(ValidationError, match="provenance"):
        register_speaking_session(
            tmp_path / "private-executable",
            MANIFEST,
            registration_attempt(prompt, transcript),
            prompt,
            transcript,
            FEEDBACK,
            [],
            segments(7),
            private_executable,
        )

    forged_quality = inspection("/private/source/practice.m4a")
    forged_quality["mean_dbfs"] = -36.0

    with pytest.raises(ValidationError, match="quality"):
        register_speaking_session(
            tmp_path / "forged-quality",
            MANIFEST,
            registration_attempt(prompt, transcript),
            prompt,
            transcript,
            FEEDBACK,
            [],
            segments(7),
            forged_quality,
        )


def test_text_only_quality_with_empty_reliability_fails_closed(tmp_path: Path) -> None:
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    text_only = inspection("/private/source/practice.m4a")
    text_only["mean_dbfs"] = -36.0
    text_only["quality"] = {
        "policy_version": 1,
        "standard_basis": "diagnostic_internal",
        "usable": True,
        "dimension_set": "text_only",
    }
    text_only["reliable_dimensions"] = []

    registration = build_speaking_registration(
        tmp_path,
        MANIFEST,
        registration_attempt(prompt, transcript),
        prompt,
        transcript,
        FEEDBACK,
        [],
        segments(7),
        text_only,
    )

    assert registration.speaking_context.reliable_dimensions == {
        "content", "grammar", "vocabulary", "reconstruction"
    }


@pytest.mark.parametrize("reliable_dimensions", [None, []])
def test_missing_or_empty_reliability_normalizes_identically_for_registration_and_audit(
    tmp_path: Path, reliable_dimensions: list[str] | None
) -> None:
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    artifact = inspection("/private/source/practice.m4a")
    if reliable_dimensions is None:
        del artifact["reliable_dimensions"]
    else:
        artifact["reliable_dimensions"] = reliable_dimensions

    registration = build_speaking_registration(
        tmp_path,
        MANIFEST,
        registration_attempt(prompt, transcript),
        prompt,
        transcript,
        FEEDBACK,
        [],
        segments(7),
        artifact,
    )
    persisted = json.loads(registration.extra_files["audio-inspection.json"])
    audited = validate_persisted_inspection(persisted, "listen_and_repeat")

    assert audited == persisted
    assert audited["reliable_dimensions"] == ["content", "grammar", "reconstruction", "vocabulary"]


def test_speaking_artifact_failure_rolls_back_attempt_and_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "workspace"
    import shutil

    shutil.copytree(ROOT / "standards", root / "standards")
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    first_attempt = registration_attempt(prompt, transcript)
    register_speaking_session(
        root,
        MANIFEST,
        first_attempt,
        prompt,
        transcript,
        FEEDBACK,
        [counted_event()],
        segments(7),
        inspection("/private/source/first.m4a"),
    )
    ledger = root / "tracker/speaking/error-events.jsonl"
    previous_ledger = ledger.read_bytes()

    second_transcript = "A different set of learner repetitions"
    second_attempt = registration_attempt(
        prompt,
        second_transcript,
        "S-LR-20260731-002",
    )
    second_event = counted_event(second_attempt["attempt_id"])
    second_event["event_id"] = "ERR-20260731-0002"
    second_event["historical_status"] = "recurring"
    original_write = register_module.atomic_write_text

    def fail_segments_write(path: Path, content: str) -> None:
        if path.name == "segments.yaml":
            raise OSError("segments unavailable")
        original_write(path, content)

    monkeypatch.setattr(
        register_module,
        "atomic_write_text",
        fail_segments_write,
    )

    with pytest.raises(OSError, match="segments unavailable"):
        register_speaking_session(
            root,
            MANIFEST,
            second_attempt,
            prompt,
            second_transcript,
            FEEDBACK,
            [second_event],
            segments(7),
            inspection("/private/source/second.m4a"),
        )

    attempts = root / "tracker/speaking/attempts"
    assert (attempts / first_attempt["attempt_id"]).exists()
    assert not (attempts / second_attempt["attempt_id"]).exists()
    assert ledger.read_bytes() == previous_ledger
    assert {
        path.name for path in attempts.iterdir() if not path.name.startswith(".")
    } == {first_attempt["attempt_id"]}


def test_registration_requires_mapping_inspection(tmp_path: Path) -> None:
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    with pytest.raises(ValidationError, match="inspection"):
        register_speaking_session(
            tmp_path,
            MANIFEST,
            registration_attempt(prompt, transcript),
            prompt,
            transcript,
            FEEDBACK,
            [],
            segments(7),
            [],
        )


def test_builder_rejects_non_mapping_transcript_segments(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(ROOT / "standards", tmp_path / "standards")
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    with pytest.raises(ValidationError, match="transcript_segments"):
        build_speaking_registration(
            tmp_path,
            MANIFEST,
            registration_attempt(prompt, transcript),
            prompt,
            transcript,
            FEEDBACK,
            [],
            segments(7),
            inspection("/private/source/practice.m4a"),
            ["not a mapping"],
        )


def test_null_attempt_duration_uses_inspection_for_segment_bounds(
    tmp_path: Path,
) -> None:
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    attempt = registration_attempt(prompt, transcript)
    attempt["duration_seconds"] = None
    inspection_data = inspection("/private/source/practice.m4a")
    inspection_data["duration_seconds"] = 75.0

    with pytest.raises(ValidationError, match="duration"):
        register_speaking_session(
            tmp_path,
            MANIFEST,
            attempt,
            prompt,
            transcript,
            FEEDBACK,
            [],
            segments(7),
            inspection_data,
        )

    assert not (tmp_path / "tracker/speaking/attempts").exists()


def test_null_attempt_duration_uses_inspection_for_timestamp_bounds(
    tmp_path: Path,
) -> None:
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    attempt = registration_attempt(prompt, transcript)
    attempt["duration_seconds"] = None
    inspection_data = inspection("/private/source/practice.m4a")
    inspection_data["duration_seconds"] = 78.0
    event = counted_event()
    event["audio_timestamp"] = "01:18–01:19"
    feedback = FEEDBACK.replace("00:12–00:14", "01:18–01:19")

    with pytest.raises(ValidationError, match="duration"):
        register_speaking_session(
            tmp_path,
            MANIFEST,
            attempt,
            prompt,
            transcript,
            feedback,
            [event],
            segments(7),
            inspection_data,
        )

    assert not (tmp_path / "tracker/speaking/attempts").exists()


def test_attempt_duration_matches_inspection_with_precise_tolerance(
    tmp_path: Path,
) -> None:
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    attempt = registration_attempt(prompt, transcript)
    near_inspection = inspection("/private/source/near.m4a")
    near_inspection["duration_seconds"] = 120.0000005

    path = register_speaking_session(
        tmp_path / "near",
        MANIFEST,
        attempt,
        prompt,
        transcript,
        FEEDBACK,
        [],
        segments(7),
        near_inspection,
    )

    assert path.exists()

    far_inspection = inspection("/private/source/far.m4a")
    far_inspection["duration_seconds"] = 120.000002
    with pytest.raises(ValidationError, match="duration"):
        register_speaking_session(
            tmp_path / "far",
            MANIFEST,
            registration_attempt(prompt, transcript),
            prompt,
            transcript,
            FEEDBACK,
            [],
            segments(7),
            far_inspection,
        )

    assert not (tmp_path / "far/tracker").exists()


def test_persisted_inspection_contains_only_approved_fields(
    tmp_path: Path,
) -> None:
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    inspection_data = inspection("/private/source/practice.m4a")
    inspection_data["private_note"] = "must not persist"

    path = register_speaking_session(
        tmp_path,
        MANIFEST,
        registration_attempt(prompt, transcript),
        prompt,
        transcript,
        FEEDBACK,
        [],
        segments(7),
        inspection_data,
    )

    persisted = json.loads((path / "audio-inspection.json").read_text())
    assert set(persisted) == {
        "duration_seconds",
        "codec",
        "sample_rate_hz",
        "channels",
        "mean_dbfs",
        "peak_dbfs",
        "clipping",
        "decodable",
        "quality",
        "provenance",
        "reliable_dimensions",
    }


def test_cli_registers_valid_speaking_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "workspace"
    standards = root / "standards/ets-2026"
    standards.mkdir(parents=True)
    (standards / "manifest.yaml").write_text(yaml.safe_dump(MANIFEST))
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    attempt = registration_attempt(prompt, transcript)
    del attempt["source_hash"]
    paths = {
        "attempt": inputs / "attempt.yaml",
        "prompt": inputs / "prompt.md",
        "transcript": inputs / "transcript.md",
        "feedback": inputs / "feedback.md",
        "events": inputs / "events.jsonl",
        "segments": inputs / "segments.yaml",
        "inspection": inputs / "inspection.json",
    }
    paths["attempt"].write_text(yaml.safe_dump(attempt, sort_keys=False))
    paths["prompt"].write_text(prompt)
    paths["transcript"].write_text(transcript)
    paths["feedback"].write_text(FEEDBACK)
    paths["events"].write_text("")
    paths["segments"].write_text(yaml.safe_dump(segments(7), sort_keys=False))
    paths["inspection"].write_text(
        json.dumps(inspection("/private/source/practice.m4a"))
    )
    argv = ["register_speaking_session.py", "--root", str(root)]
    for name, path in paths.items():
        argv.extend([f"--{name}", str(path)])
    monkeypatch.setattr(sys, "argv", argv)

    assert register_speaking_main() == 0

    destination = root / "tracker/speaking/attempts/S-LR-20260731-001"
    assert capsys.readouterr().out.strip() == str(destination)
    assert (destination / "source-reference.txt").read_text() == (
        "source:" + sha256(b"/private/source/practice.m4a").hexdigest() + "\n"
    )
