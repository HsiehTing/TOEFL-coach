import json
import shutil
import tempfile
from pathlib import Path

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.reports import rebuild_modality
from toefl_tracker.validation import validate_attempt, validate_error_event


def audit_workspace(root: Path) -> list[str]:
    problems: list[str] = []
    manifest_path = root / "standards/ets-2026/manifest.yaml"
    try:
        manifest = read_yaml(manifest_path)
    except (OSError, TypeError, ValueError) as error:
        problems.append(f"{manifest_path}: {error}")
        manifest = {"rubrics": {}}
    score_policy_path = root / "standards/ets-2026/score-policy.md"
    if not score_policy_path.exists():
        problems.append(f"{score_policy_path}: missing")
    else:
        try:
            score_policy = score_policy_path.read_text(encoding="utf-8")
            required_policy_text = {
                "單題結果不得宣稱為完整 section band",
                "official_basis",
                "simulated_task_score",
                "diagnostic_only",
            }
            if not all(phrase in score_policy for phrase in required_policy_text):
                problems.append(f"{score_policy_path}: invalid score-policy contract")
        except OSError as error:
            problems.append(f"{score_policy_path}: {error}")

    for modality in ("writing", "speaking"):
        base = root / "tracker" / modality
        attempts: dict[str, dict] = {}
        invalid_data = False
        for path in base.glob("attempts/*/attempt.yaml"):
            try:
                attempt = read_yaml(path)
                validate_attempt(attempt, manifest)
                attempts[attempt["attempt_id"]] = attempt
                directory = path.parent
                if attempt["modality"] == "writing":
                    response_name = (
                        "response-revision.md"
                        if attempt["record_type"] == "revision"
                        else "response-original.md"
                    )
                else:
                    response_name = (
                        "transcript-revision.md"
                        if attempt["record_type"] == "revision"
                        else "transcript-original.md"
                    )
                required_files = [
                    directory / "prompt.md",
                    directory / response_name,
                    directory / "feedback-round-1.md",
                ]
                if any(not required.exists() for required in required_files):
                    problems.append(f"{attempt['attempt_id']}: missing immutable evidence file")
                else:
                    expected_hash = canonical_source_hash(
                        (directory / "prompt.md").read_text(encoding="utf-8"),
                        (directory / response_name).read_text(encoding="utf-8"),
                    )
                    if expected_hash != attempt["source_hash"]:
                        problems.append(f"{attempt['attempt_id']}: source_hash mismatch")
                if attempt["modality"] == "speaking":
                    speaking_files = [
                        directory / "audio-inspection.json",
                        directory / "segments.yaml",
                        directory / "source-reference.txt",
                    ]
                    if any(not required.exists() for required in speaking_files):
                        problems.append(f"{attempt['attempt_id']}: missing speaking intake artifact")
            except (OSError, KeyError, TypeError, ValueError) as error:
                invalid_data = True
                problems.append(f"{path}: {error}")

        ledger = base / "error-events.jsonl"
        if ledger.exists():
            try:
                lines = ledger.read_text(encoding="utf-8").splitlines()
            except OSError as error:
                invalid_data = True
                problems.append(f"{ledger}: {error}")
                lines = []
            for number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError("event must be a JSON mapping")
                    validate_error_event(event)
                    if event["attempt_id"] not in attempts:
                        problems.append(f"orphan event {event['event_id']}")
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                    invalid_data = True
                    problems.append(f"{ledger}:{number}: {error}")

        for attempt in attempts.values():
            if attempt["record_type"] == "revision" and attempt["parent_attempt_id"] not in attempts:
                problems.append(f"missing revision parent for {attempt['attempt_id']}")

        if attempts and not invalid_data:
            with tempfile.TemporaryDirectory() as temporary:
                expected_root = Path(temporary)
                raw_base = expected_root / "tracker" / modality
                shutil.copytree(base / "attempts", raw_base / "attempts")
                if ledger.exists():
                    shutil.copy2(ledger, raw_base / "error-events.jsonl")
                rebuild_modality(expected_root, modality)
                expected_files = {
                    path.relative_to(raw_base)
                    for path in (raw_base / "reports").glob("*.md")
                }
                expected_files.update({Path("dashboard.csv"), Path("profile.md")})
                actual_reports = (
                    {
                        path.relative_to(base)
                        for path in (base / "reports").glob("*.md")
                    }
                    if (base / "reports").exists()
                    else set()
                )
                expected_reports = {
                    path for path in expected_files if path.parts[0] == "reports"
                }
                if actual_reports != expected_reports:
                    problems.append(f"{modality}: derived report set is stale")
                for relative in expected_files:
                    expected = raw_base / relative
                    actual = base / relative
                    try:
                        stale = (
                            not actual.exists()
                            or actual.read_text(encoding="utf-8")
                            != expected.read_text(encoding="utf-8")
                        )
                    except OSError:
                        stale = True
                    if stale:
                        problems.append(f"{modality}: stale derived file {relative}")
    return sorted(problems)
