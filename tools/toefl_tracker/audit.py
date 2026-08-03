import csv
import json
import re
import shutil
import tempfile
from io import StringIO
from pathlib import Path

import yaml

from toefl_tracker.event_validation import SpeakingEvidenceContext, validate_event_context
from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.models import TASK_TYPES, ValidationError
from toefl_tracker.register import persisted_attempt_relationship_problems
from toefl_tracker.reports import rebuild_modality
from toefl_tracker.speaking import validate_persisted_inspection, validate_speaking_assessment
from toefl_tracker.validation import validate_attempt, validate_error_event


_PARSE_ERRORS = (UnicodeDecodeError, yaml.YAMLError, json.JSONDecodeError, csv.Error, OSError, ValidationError, TypeError, ValueError)


def _read_utf8(path: Path, problems: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        problems.append(f"{path}: invalid UTF-8")
    except OSError as error:
        problems.append(f"{path}: {error}")
    return None


def _load_yaml(path: Path, problems: list[str]) -> dict | None:
    try:
        return read_yaml(path)
    except _PARSE_ERRORS as error:
        problems.append(f"{path}: {error}")
    return None


def _load_events(path: Path, problems: list[str]) -> list[dict]:
    text = _read_utf8(path, problems)
    if text is None:
        return []
    rows: list[dict] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            problems.append(f"{path}:{number}: blank event row")
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValidationError("event must be a JSON mapping")
            validate_error_event(row)
            rows.append(row)
        except _PARSE_ERRORS as error:
            problems.append(f"{path}:{number}: {error}")
    return rows


def _response_name(attempt: dict) -> str:
    if attempt["modality"] == "writing":
        return "response-revision.md" if attempt["record_type"] == "revision" else "response-original.md"
    return "transcript-revision.md" if attempt["record_type"] == "revision" else "transcript-original.md"


def _audit_speaking_artifacts(
    directory: Path, attempt: dict, events: list[dict], problems: list[str]
) -> SpeakingEvidenceContext | None:
    segments_path = directory / "segments.yaml"
    inspection_path = directory / "audio-inspection.json"
    reference_path = directory / "source-reference.txt"
    feedback_path = directory / "feedback-round-1.md"
    if not all(path.exists() for path in (segments_path, inspection_path, reference_path)):
        problems.append(f"{attempt['attempt_id']}: missing speaking intake artifact")
        return None
    segments_text = _read_utf8(segments_path, problems)
    inspection_text = _read_utf8(inspection_path, problems)
    _read_utf8(reference_path, problems)
    feedback = _read_utf8(feedback_path, problems)
    if None in (segments_text, inspection_text, feedback):
        return None
    try:
        segments = yaml.safe_load(segments_text)
        inspection = json.loads(inspection_text)
        if not isinstance(segments, list):
            raise ValidationError("speaking segments must be a list of mappings")
        if not isinstance(inspection, dict):
            raise ValidationError("speaking inspection must be a mapping")
        inspection = validate_persisted_inspection(inspection)
        validate_speaking_assessment(attempt, segments, events, feedback)
        reliable = {
            "intelligibility", "pronunciation", "prosody", "fluency", "grammar",
            "vocabulary", "reconstruction", "directness", "relevance", "elaboration", "coherence",
        }
        return SpeakingEvidenceContext(
            learner_segments=tuple(row for row in segments if isinstance(row, dict) and row.get("role") == "learner"),
            duration_seconds=inspection["duration_seconds"],
            reliable_dimensions=reliable,
        )
    except _PARSE_ERRORS as error:
        problems.append(f"{directory}: {error}")
    return None


def _audit_derived(root: Path, modality: str, invalid_data: bool, problems: list[str]) -> None:
    if invalid_data:
        return
    base = root / "tracker" / modality
    try:
        with tempfile.TemporaryDirectory() as temporary:
            expected_root = Path(temporary)
            standards = root / "standards"
            if standards.exists():
                shutil.copytree(standards, expected_root / "standards")
            attempts = base / "attempts"
            if attempts.exists():
                shutil.copytree(attempts, expected_root / "tracker" / modality / "attempts")
            rebuild_modality(expected_root, modality)
            expected_base = expected_root / "tracker" / modality
            scopes = ["common", *(task.replace("_", "-") for task in TASK_TYPES[modality])]
            report_name = re.compile(
                rf"^{re.escape(modality)}-({'|'.join(map(re.escape, scopes))})-\d{{4}}\.md$"
            )
            expected_reports = {
                path.relative_to(expected_base)
                for path in (expected_base / "reports").glob("*.md")
                if report_name.fullmatch(path.name)
            }
            actual_reports = {
                path.relative_to(base)
                for path in (base / "reports").glob("*.md")
                if report_name.fullmatch(path.name)
            } if (base / "reports").exists() else set()
            if actual_reports != expected_reports:
                problems.append(f"{modality}: derived report set is stale")
            for relative in [Path("error-events.jsonl"), Path("dashboard.csv"), Path("profile.md"), *sorted(expected_reports)]:
                expected = (expected_base / relative).read_bytes()
                actual = base / relative
                try:
                    stale = not actual.exists() or actual.read_bytes() != expected
                    if actual.exists() and relative.suffix == ".csv":
                        list(csv.reader(StringIO(actual.read_text(encoding="utf-8"))))
                except _PARSE_ERRORS:
                    stale = True
                if stale:
                    problems.append(f"{modality}: stale derived file {relative}")
    except _PARSE_ERRORS as error:
        problems.append(f"{modality}: cannot rebuild derived artifacts: {error}")


def audit_workspace(root: Path) -> list[str]:
    problems: list[str] = []
    manifest_path = root / "standards/ets-2026/manifest.yaml"
    manifest = _load_yaml(manifest_path, problems) or {"rubrics": {}}
    score_policy_path = root / "standards/ets-2026/score-policy.md"
    score_policy = _read_utf8(score_policy_path, problems) if score_policy_path.exists() else None
    if score_policy is None:
        if not score_policy_path.exists():
            problems.append(f"{score_policy_path}: missing")
    elif not all(phrase in score_policy for phrase in {"單題結果不得宣稱為完整 section band", "official_basis", "simulated_task_score", "diagnostic_only"}):
        problems.append(f"{score_policy_path}: invalid score-policy contract")

    for modality in ("writing", "speaking"):
        base = root / "tracker" / modality
        attempts: dict[str, dict] = {}
        directories: dict[str, Path] = {}
        responses: dict[str, str] = {}
        sidecars: dict[str, list[dict]] = {}
        speaking_contexts: dict[str, SpeakingEvidenceContext] = {}
        invalid_data = False
        attempts_root = base / "attempts"
        directories_on_disk = sorted(
            path for path in attempts_root.glob("*")
            if path.is_dir() and not path.name.startswith(".")
        ) if attempts_root.exists() else []
        for directory in directories_on_disk:
            path = directory / "attempt.yaml"
            if not path.exists():
                problems.append(f"{directory}: missing attempt.yaml")
                invalid_data = True
                continue
            attempt = _load_yaml(path, problems)
            if attempt is None:
                invalid_data = True
                continue
            try:
                validate_attempt(attempt, manifest)
                if attempt["attempt_id"] != directory.name or attempt["modality"] != modality:
                    raise ValidationError("attempt directory, modality, or attempt_id mismatch")
                if attempt["attempt_id"] in attempts:
                    raise ValidationError("duplicate attempt_id")
            except _PARSE_ERRORS as error:
                problems.append(f"{path}: {error}")
                invalid_data = True
                continue
            attempts[attempt["attempt_id"]] = attempt
            directories[attempt["attempt_id"]] = directory
            sidecar = directory / "events.jsonl"
            if not sidecar.exists():
                problems.append(f"{attempt['attempt_id']}: missing canonical event sidecar")
                invalid_data = True
                sidecars[attempt["attempt_id"]] = []
            else:
                rows = _load_events(sidecar, problems)
                sidecars[attempt["attempt_id"]] = rows
                if any(row.get("attempt_id") != attempt["attempt_id"] for row in rows):
                    problems.append(f"{sidecar}: canonical event attempt_id mismatch")
                    invalid_data = True
                if attempt["record_type"] == "re_evaluation" and rows:
                    problems.append(f"{sidecar}: re-evaluation event sidecar must be empty")
                    invalid_data = True
            required = [directory / "feedback-round-1.md"]
            if attempt["record_type"] != "re_evaluation":
                required.extend([directory / "prompt.md", directory / _response_name(attempt)])
            if any(not item.exists() for item in required):
                problems.append(f"{attempt['attempt_id']}: missing immutable evidence file")
                invalid_data = True
                continue
            if _read_utf8(directory / "feedback-round-1.md", problems) is None:
                invalid_data = True
            if attempt["record_type"] != "re_evaluation":
                prompt = _read_utf8(directory / "prompt.md", problems)
                response = _read_utf8(directory / _response_name(attempt), problems)
                if prompt is None or response is None:
                    invalid_data = True
                else:
                    responses[attempt["attempt_id"]] = response
                    if canonical_source_hash(prompt, response) != attempt["source_hash"]:
                        problems.append(f"{attempt['attempt_id']}: source_hash mismatch")
                        invalid_data = True
            if modality == "speaking" and attempt["record_type"] != "re_evaluation":
                context = _audit_speaking_artifacts(directory, attempt, sidecars[attempt["attempt_id"]], problems)
                if context is None:
                    invalid_data = True
                else:
                    speaking_contexts[attempt["attempt_id"]] = context

        ledger = base / "error-events.jsonl"
        if ledger.exists():
            aggregate_events = _load_events(ledger, problems)
            for event in aggregate_events:
                if event["attempt_id"] not in attempts:
                    problems.append(f"orphan event {event['event_id']}")

        relationship_problems = persisted_attempt_relationship_problems(
            list(attempts.values())
        )
        if relationship_problems:
            for attempt_id, reason in relationship_problems:
                problems.append(f"{modality}: {attempt_id}: {reason}")
            invalid_data = True

        history_attempts: list[dict] = []
        history_events: list[dict] = []
        for attempt in sorted(attempts.values(), key=lambda row: (row["submitted_at"], row["attempt_id"])):
            attempt_id = attempt["attempt_id"]
            if attempt["record_type"] != "re_evaluation" and attempt_id in responses:
                for event in sidecars.get(attempt_id, []):
                    try:
                        validate_event_context(
                            root, attempt, responses[attempt_id], event, sidecars[attempt_id],
                            history_attempts, history_events, speaking_contexts.get(attempt_id),
                        )
                    except _PARSE_ERRORS as error:
                        problems.append(f"{directories[attempt_id] / 'events.jsonl'}: {error}")
                        invalid_data = True
            history_attempts.append(attempt)
            history_events.extend(sidecars.get(attempt_id, []))

        _audit_derived(root, modality, invalid_data, problems)
    return sorted(problems)
