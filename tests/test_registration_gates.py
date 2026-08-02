import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

from register_attempt import main as register_attempt_main
from register_writing_attempt import main as register_writing_main
from test_validation import valid_attempt
from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.writing import build_writing_registration


ROOT = Path(__file__).parents[1]


def _write_inputs(tmp_path: Path, attempt: dict, feedback: str) -> dict[str, Path]:
    (tmp_path / "standards").mkdir()
    (tmp_path / "standards/ets-2026").mkdir()
    (tmp_path / "standards/ets-2026/manifest.yaml").write_text(
        (ROOT / "standards/ets-2026/manifest.yaml").read_text(), encoding="utf-8"
    )
    paths = {
        "attempt": tmp_path / "attempt.yaml",
        "prompt": tmp_path / "prompt.md",
        "response": tmp_path / "response.md",
        "feedback": tmp_path / "feedback.md",
        "events": tmp_path / "events.jsonl",
    }
    paths["attempt"].write_text(yaml.safe_dump(attempt), encoding="utf-8")
    paths["prompt"].write_text("Prompt", encoding="utf-8")
    paths["response"].write_text("A response", encoding="utf-8")
    paths["feedback"].write_text(feedback, encoding="utf-8")
    paths["events"].write_text("", encoding="utf-8")
    return paths


WRITING_FEEDBACK = """# Result
Simulated task score: 3/5
# Why this level
Evidence.
# Why not the next level
Evidence.
# Evidence
No counted errors.
# Priorities
1. Improve article selection.
# Rewrite task
Revise the response.
"""


def test_generic_cli_rejects_speaking_with_dedicated_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    attempt = valid_attempt()
    attempt.update({
        "modality": "speaking",
        "task_type": "listen_and_repeat",
        "rubric_version": "ets-speaking-blueprint-2026-diagnostic",
        "result_type": "diagnostic_only",
        "audio_quality": {"decodable": True, "clipping": False},
    })
    paths = _write_inputs(tmp_path, attempt, WRITING_FEEDBACK)
    monkeypatch.setattr(sys, "argv", [
        "register_attempt.py", "--root", str(tmp_path),
        *[item for name in ("attempt", "prompt", "response", "feedback", "events")
          for item in (f"--{name}", str(paths[name]))],
    ])

    with pytest.raises(SystemExit):
        register_attempt_main()

    assert "register_speaking_session.py" in capsys.readouterr().err


def test_writing_cli_runs_feedback_gate_before_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempt = valid_attempt()
    paths = _write_inputs(tmp_path, attempt, "unstructured feedback")
    monkeypatch.setattr(sys, "argv", [
        "register_writing_attempt.py", "--root", str(tmp_path),
        *[item for name in ("attempt", "prompt", "response", "feedback", "events")
          for item in (f"--{name}", str(paths[name]))],
    ])

    with pytest.raises(ValidationError, match="headings"):
        register_writing_main()

    assert not (tmp_path / "tracker/writing/attempts").exists()


def test_writing_builder_rejects_contextually_fabricated_event_before_bundle(
    tmp_path: Path,
) -> None:
    shutil.copytree(ROOT / "standards", tmp_path / "standards")
    attempt = valid_attempt()
    prompt = "Prompt"
    response = "A response"
    attempt["source_hash"] = canonical_source_hash(prompt, response)
    event = {
        "event_id": "ERR-1", "attempt_id": attempt["attempt_id"],
        "taxonomy_version": 1, "code": "GRAM-NEGATION",
        "source_excerpt": "fabricated", "audio_timestamp": None,
        "suggested_revision": "Revise it.", "reason": "Evidence.",
        "level": "must_fix", "severity": "meaning_changing",
        "task_specific": False, "opportunity_present": True,
        "historical_status": "new",
    }
    manifest = yaml.safe_load((ROOT / "standards/ets-2026/manifest.yaml").read_text())

    with pytest.raises(ValidationError, match="excerpt is not present"):
        build_writing_registration(
            tmp_path,
            manifest,
            attempt,
            prompt,
            response,
            WRITING_FEEDBACK.replace("No counted errors.", "fabricated"),
            [event],
        )


def test_production_clis_do_not_import_dict_based_register_attempt() -> None:
    for path in (
        ROOT / "tools/register_attempt.py",
        ROOT / "tools/register_writing_attempt.py",
        ROOT / "tools/register_speaking_session.py",
    ):
        assert "from toefl_tracker.register import register_attempt" not in path.read_text()
