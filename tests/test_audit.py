import json
import shutil
from pathlib import Path

import yaml

from test_validation import valid_attempt
from toefl_tracker.audit import audit_workspace
from toefl_tracker.reports import rebuild_modality


def test_orphan_event_is_reported(tmp_path: Path) -> None:
    ledger = tmp_path / "tracker/writing/error-events.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({
        "event_id": "E-1",
        "attempt_id": "MISSING",
        "taxonomy_version": 1,
        "code": "GRAM-ARTICLE",
        "source_excerpt": "a object",
        "audio_timestamp": None,
        "suggested_revision": "an object",
        "reason": "Article selection.",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }) + "\n")
    problems = audit_workspace(tmp_path)
    assert any("orphan event E-1" in problem for problem in problems)


def test_stale_derived_dashboard_is_reported(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    shutil.copytree(root / "standards", tmp_path / "standards")
    destination = tmp_path / "tracker/writing/attempts/W-AD-20260731-001"
    destination.mkdir(parents=True)
    (destination / "attempt.yaml").write_text(
        yaml.safe_dump(valid_attempt(), allow_unicode=True),
        encoding="utf-8",
    )
    rebuild_modality(tmp_path, "writing")
    dashboard = tmp_path / "tracker/writing/dashboard.csv"
    dashboard.write_text(dashboard.read_text() + "stale,row\n", encoding="utf-8")
    assert any("stale derived file" in problem for problem in audit_workspace(tmp_path))
