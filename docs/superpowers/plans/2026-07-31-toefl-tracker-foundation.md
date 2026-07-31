# TOEFL Tracker Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the versioned ETS standards store, persistent attempt/error ledger, deterministic status engine, report rebuilders, validator, and repository-wide `AGENTS.md` contract shared by the writing and speaking coaches.

**Architecture:** Human- and AI-authored assessments are stored as immutable YAML/Markdown attempts plus append-only JSONL error events. A small Python package performs schema validation, duplicate detection, status calculation, report generation, and integrity checks; thin command-line wrappers expose those operations. Derived CSV and Markdown reports are always rebuilt from attempts and events.

**Tech Stack:** Python 3.11+, PyYAML 6.x, pytest 8.x, Markdown, YAML, JSONL, CSV, Git.

## Global Constraints

- Target TOEFL iBT version is the test effective from 2026-01-21.
- The learner's long-term Writing and Speaking section target is band 6.
- Never present a single-task result as a complete section score.
- Preserve original submissions; revisions and re-evaluations are separate records.
- Only `must_fix` and `should_fix` events count in error rates; `polish` does not.
- Revisions and targeted drills never increase formal attempt/session counts.
- Every counted event must point to an exact excerpt or audio timestamp.
- Every `improving` or `controlled` decision requires a positive opportunity count.
- Standards changes create a new rubric version and never silently rewrite old evaluations.
- Raw audio is not copied into the repository by default.
- Use test-driven development and commit after each task.

---

## File Map

- `pyproject.toml`: Python version, runtime dependency, pytest configuration.
- `.gitignore`: Python artifacts and private local audio.
- `AGENTS.md`: concise coaching constitution and skill router.
- `standards/ets-2026/manifest.yaml`: authoritative source metadata and verification date.
- `standards/ets-2026/score-policy.md`: official versus simulated score boundaries.
- `tools/toefl_tracker/models.py`: enums, constants, and validation errors.
- `tools/toefl_tracker/io.py`: YAML/JSONL loading, canonical hashes, and atomic writes.
- `tools/toefl_tracker/validation.py`: attempt and error-event validation.
- `tools/toefl_tracker/register.py`: immutable registration and duplicate detection.
- `tools/toefl_tracker/status.py`: historical error-state calculation.
- `tools/toefl_tracker/reports.py`: dashboard, profile, and cadence report generation.
- `tools/toefl_tracker/audit.py`: cross-file integrity validation.
- `tools/register_attempt.py`: registration CLI.
- `tools/rebuild_reports.py`: report rebuild CLI.
- `tools/validate_tracker.py`: integrity-check CLI.
- `tests/`: focused unit and integration tests.

### Task 1: Bootstrap the Python Project and Privacy Boundary

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `tools/toefl_tracker/__init__.py`
- Create: `tests/test_project_contract.py`

**Interfaces:**
- Consumes: none.
- Produces: importable `toefl_tracker` package under `tools/`; pytest configuration used by every later task.

- [ ] **Step 1: Write the failing project-contract test**

```python
# tests/test_project_contract.py
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_private_audio_and_python_artifacts_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "tracker/**/media/" in ignore
    assert "__pycache__/" in ignore
    assert ".pytest_cache/" in ignore


def test_supported_python_floor_is_311() -> None:
    config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.11"' in config
    assert '"PyYAML>=6.0,<7"' in config
```

- [ ] **Step 2: Run the test and verify the missing files fail**

Run: `python3 -m pytest tests/test_project_contract.py -v`

Expected: FAIL because `.gitignore` and `pyproject.toml` do not exist.

- [ ] **Step 3: Create the minimal project configuration**

```toml
# pyproject.toml
[project]
name = "toefl-coaching-tracker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["PyYAML>=6.0,<7"]

[project.optional-dependencies]
dev = ["pytest>=8,<9"]

[tool.pytest.ini_options]
pythonpath = ["tools"]
testpaths = ["tests"]
addopts = "-ra"
```

```gitignore
# .gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
tracker/**/media/
```

```python
# tools/toefl_tracker/__init__.py
"""Deterministic storage and reporting for the TOEFL coaching workspace."""
```

- [ ] **Step 4: Install the local test dependencies and rerun**

Run: `python3 -m pip install -e '.[dev]'`

Expected: installation succeeds.

Run: `python3 -m pytest tests/test_project_contract.py -v`

Expected: 2 tests pass.

- [ ] **Step 5: Commit the bootstrap**

```bash
git add pyproject.toml .gitignore tools/toefl_tracker/__init__.py tests/test_project_contract.py
git commit -m "build: bootstrap TOEFL tracker"
```

### Task 2: Add the Versioned ETS Standards Manifest and Score Policy

**Files:**
- Create: `standards/ets-2026/manifest.yaml`
- Create: `standards/ets-2026/score-policy.md`
- Create: `tests/test_standards.py`

**Interfaces:**
- Consumes: PyYAML installed in Task 1.
- Produces: manifest keys `schema_version`, `test_version`, `effective_from`, `last_verified`, and `sources`; stable rubric IDs used by all attempt records.

- [ ] **Step 1: Write the failing standards tests**

```python
# tests/test_standards.py
from datetime import date
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "standards/ets-2026/manifest.yaml"


def test_manifest_identifies_the_2026_test_and_official_sources() -> None:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["test_version"] == "TOEFL iBT 2026"
    assert data["effective_from"] == date(2026, 1, 21)
    assert data["last_verified"] == date(2026, 7, 31)
    assert set(data["rubrics"]) == {
        "ets-writing-email-2025-applicable-2026",
        "ets-writing-discussion-2025-applicable-2026",
        "ets-speaking-blueprint-2026-diagnostic",
    }
    assert all(
        url.startswith(("https://www.ets.org/", "https://www.es.ets.org/"))
        for url in data["sources"].values()
    )


def test_score_policy_forbids_task_to_section_conversion() -> None:
    policy = (ROOT / "standards/ets-2026/score-policy.md").read_text(encoding="utf-8")
    assert "單題結果不得宣稱為完整 section band" in policy
    assert "0–5" in policy
    assert "1–6" in policy
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m pytest tests/test_standards.py -v`

Expected: FAIL because the standards files do not exist.

- [ ] **Step 3: Add the exact standards metadata**

```yaml
# standards/ets-2026/manifest.yaml
schema_version: 1
test_version: "TOEFL iBT 2026"
effective_from: 2026-01-21
last_verified: 2026-07-31
rubrics:
  ets-writing-email-2025-applicable-2026:
    task_type: email
    scale: "0-5"
  ets-writing-discussion-2025-applicable-2026:
    task_type: academic_discussion
    scale: "0-5"
  ets-speaking-blueprint-2026-diagnostic:
    task_type: speaking
    scale: diagnostic
sources:
  writing_tasks: "https://www.ets.org/toefl/test-takers/ibt/about/content/writing.html"
  writing_rubric: "https://www.ets.org/content/dam/ets-org/pdfs/toefl/writing-rubrics.pdf"
  test_blueprint: "https://www.es.ets.org/pdfs/toefl/toefl-ibt-test-specifications-2026.pdf"
  score_scale: "https://www.ets.org/toefl/institutions/ibt/score-scale-update.html"
```

```markdown
# standards/ets-2026/score-policy.md
# TOEFL 2026 分數標示政策

- Write an Email 與 Write for an Academic Discussion 可依 ETS 公開 rubric 提供 0–5 的任務層級模擬分數。
- Speaking 單組練習只提供明確標示的診斷結果，除非 ETS 日後公開可直接套用的任務量尺。
- TOEFL section 成績採 1–6 band；單題結果不得宣稱為完整 section band。
- 完整 section band 需要完整 section 的有效作答與 ETS 適用換算依據。
- 所有回饋必須標示 `official_basis`、`simulated_task_score` 或 `diagnostic_only`。
```

- [ ] **Step 4: Run the standards tests**

Run: `python3 -m pytest tests/test_standards.py -v`

Expected: 2 tests pass.

- [ ] **Step 5: Commit the standards baseline**

```bash
git add standards/ets-2026 tests/test_standards.py
git commit -m "docs: add ETS 2026 standards manifest"
```

### Task 3: Implement Attempt and Error-Event Validation

**Files:**
- Create: `tools/toefl_tracker/models.py`
- Create: `tools/toefl_tracker/io.py`
- Create: `tools/toefl_tracker/validation.py`
- Create: `tests/test_validation.py`

**Interfaces:**
- Consumes: rubric IDs from `standards/ets-2026/manifest.yaml`.
- Produces:
  - `ValidationError(ValueError)`
  - `canonical_source_hash(prompt: str, response: str) -> str`
  - `validate_attempt(data: dict, manifest: dict) -> None`
  - `validate_error_event(data: dict) -> None`
  - `read_yaml(path: Path) -> dict`
  - `atomic_write_text(path: Path, content: str) -> None`

- [ ] **Step 1: Write failing validation tests**

```python
# tests/test_validation.py
from pathlib import Path

import pytest
import yaml

from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.validation import validate_attempt, validate_error_event


MANIFEST = yaml.safe_load(
    (Path(__file__).parents[1] / "standards/ets-2026/manifest.yaml").read_text()
)


def valid_attempt() -> dict:
    return {
        "schema_version": 1,
        "attempt_id": "W-AD-20260731-001",
        "modality": "writing",
        "task_type": "academic_discussion",
        "record_type": "formal_original",
        "submitted_at": "2026-07-31T10:00:00+08:00",
        "practiced_at": None,
        "timed": True,
        "duration_seconds": 600,
        "assistance": {"spellcheck": False, "translation": False, "other": None},
        "word_count": 120,
        "rubric_version": "ets-writing-discussion-2025-applicable-2026",
        "standard_verified_at": "2026-07-31",
        "task_score": {"scale": "0-5", "value": 3, "confidence": "medium"},
        "task_metrics": {"prompt_alignment": "partial", "elaboration": "partial"},
        "source_hash": canonical_source_hash("prompt", "response"),
        "opportunities": {"GRAM-NEGATION": 1},
        "parent_attempt_id": None,
        "revision_outcomes": None,
    }


def test_valid_attempt_is_accepted() -> None:
    validate_attempt(valid_attempt(), MANIFEST)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("record_type", "draft"),
        ("task_type", "listen_and_repeat"),
        ("rubric_version", "invented-rubric"),
        ("opportunities", {"GRAM-NEGATION": -1}),
    ],
)
def test_invalid_attempt_fields_are_rejected(field: str, value: object) -> None:
    attempt = valid_attempt()
    attempt[field] = value
    with pytest.raises(ValidationError):
        validate_attempt(attempt, MANIFEST)


def test_counted_event_requires_traceable_evidence() -> None:
    event = {
        "event_id": "ERR-20260731-0001",
        "attempt_id": "W-AD-20260731-001",
        "taxonomy_version": 1,
        "code": "GRAM-NEGATION",
        "source_excerpt": "",
        "audio_timestamp": None,
        "suggested_revision": "I do not think it is sufficient.",
        "reason": "Double negative changes the claim.",
        "level": "must_fix",
        "severity": "meaning_changing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }
    with pytest.raises(ValidationError, match="evidence"):
        validate_error_event(event)


def test_revision_outcomes_must_reconcile() -> None:
    attempt = valid_attempt()
    attempt["record_type"] = "revision"
    attempt["parent_attempt_id"] = "W-AD-20260730-001"
    attempt["revision_outcomes"] = {
        "assigned": 3,
        "resolved": 2,
        "partly_resolved": 1,
        "unresolved": 0,
        "new_errors": 1,
        "resolution_rate": 0.5,
    }
    with pytest.raises(ValidationError, match="resolution_rate"):
        validate_attempt(attempt, MANIFEST)
```

- [ ] **Step 2: Run the tests and verify import failure**

Run: `python3 -m pytest tests/test_validation.py -v`

Expected: FAIL because the tracker modules do not exist.

- [ ] **Step 3: Add constants and validation error**

```python
# tools/toefl_tracker/models.py
class ValidationError(ValueError):
    """Raised when persistent tracker data violates the repository contract."""


MODALITIES = {"writing", "speaking"}
TASK_TYPES = {
    "writing": {"email", "academic_discussion"},
    "speaking": {"listen_and_repeat", "take_an_interview"},
}
RECORD_TYPES = {"formal_original", "revision", "targeted_drill", "discussion_only"}
LEVELS = {"must_fix", "should_fix", "polish"}
SEVERITIES = {"minor", "clarity_reducing", "meaning_changing"}
STATUSES = {"new", "recurring", "persistent", "improving", "controlled", "relapsed"}
```

- [ ] **Step 4: Add deterministic I/O helpers**

```python
# tools/toefl_tracker/io.py
import hashlib
import os
import tempfile
from pathlib import Path

import yaml


def canonical_source_hash(prompt: str, response: str) -> str:
    canonical = prompt.replace("\r\n", "\n").strip() + "\n---\n" + response.replace("\r\n", "\n").strip()
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
```

- [ ] **Step 5: Implement strict validators**

```python
# tools/toefl_tracker/validation.py
import re
from datetime import date, datetime

from toefl_tracker.models import (
    LEVELS, MODALITIES, RECORD_TYPES, SEVERITIES, STATUSES, TASK_TYPES, ValidationError
)


REQUIRED_ATTEMPT_FIELDS = {
    "schema_version", "attempt_id", "modality", "task_type", "record_type",
    "submitted_at", "practiced_at", "timed", "duration_seconds", "assistance",
    "rubric_version", "standard_verified_at", "task_metrics", "source_hash",
    "opportunities", "parent_attempt_id", "revision_outcomes",
}


def validate_attempt(data: dict, manifest: dict) -> None:
    missing = REQUIRED_ATTEMPT_FIELDS - data.keys()
    if missing:
        raise ValidationError(f"missing attempt fields: {sorted(missing)}")
    if data["schema_version"] != 1:
        raise ValidationError("unsupported attempt schema_version")
    if data["modality"] not in MODALITIES:
        raise ValidationError("invalid modality")
    if data["task_type"] not in TASK_TYPES[data["modality"]]:
        raise ValidationError("task_type does not match modality")
    if data["record_type"] not in RECORD_TYPES:
        raise ValidationError("invalid record_type")
    if data["rubric_version"] not in manifest["rubrics"]:
        raise ValidationError("unknown rubric_version")
    rubric_task = manifest["rubrics"][data["rubric_version"]]["task_type"]
    if rubric_task not in {data["task_type"], data["modality"]}:
        raise ValidationError("rubric_version does not match task_type")
    try:
        datetime.fromisoformat(data["submitted_at"])
    except (TypeError, ValueError) as error:
        raise ValidationError("submitted_at must be ISO 8601") from error
    for field in ("practiced_at", "standard_verified_at"):
        if data[field] is not None:
            try:
                date.fromisoformat(data[field])
            except (TypeError, ValueError) as error:
                raise ValidationError(f"{field} must be an ISO date or null") from error
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", data["source_hash"]):
        raise ValidationError("source_hash must be a SHA-256 digest")
    opportunities = data["opportunities"]
    if not isinstance(opportunities, dict) or any(
        not isinstance(value, int) or value < 0 for value in opportunities.values()
    ):
        raise ValidationError("opportunities must map codes to non-negative integers")
    if not isinstance(data["task_metrics"], dict):
        raise ValidationError("task_metrics must be a mapping")
    if data["timed"] not in {True, False, None}:
        raise ValidationError("timed must be true, false, or null")
    if data["duration_seconds"] is not None and (
        not isinstance(data["duration_seconds"], int) or data["duration_seconds"] <= 0
    ):
        raise ValidationError("duration_seconds must be a positive integer or null")
    if not isinstance(data["assistance"], dict):
        raise ValidationError("assistance must be a mapping")
    if set(data["assistance"]) != {"spellcheck", "translation", "other"}:
        raise ValidationError("assistance fields are invalid")
    if data["modality"] == "writing":
        score = data.get("task_score", {})
        if data.get("word_count", -1) < 0:
            raise ValidationError("writing word_count must be non-negative")
        if score.get("scale") != "0-5" or not isinstance(score.get("value"), int) or not 0 <= score["value"] <= 5:
            raise ValidationError("writing task_score must be an integer on scale 0-5")
    if data["modality"] == "speaking" and data.get("result_type") != "diagnostic_only":
        raise ValidationError("speaking result_type must be diagnostic_only")
    if data["record_type"] == "revision" and not data["parent_attempt_id"]:
        raise ValidationError("revision requires parent_attempt_id")
    if data["record_type"] != "revision" and data["parent_attempt_id"] is not None:
        raise ValidationError("only revisions may have parent_attempt_id")
    outcomes = data["revision_outcomes"]
    if data["record_type"] != "revision" and outcomes is not None:
        raise ValidationError("only revisions may have revision_outcomes")
    if data["record_type"] == "revision":
        keys = {"assigned", "resolved", "partly_resolved", "unresolved", "new_errors", "resolution_rate"}
        if not isinstance(outcomes, dict) or set(outcomes) != keys:
            raise ValidationError("revision_outcomes fields are invalid")
        if outcomes["assigned"] <= 0:
            raise ValidationError("revision assigned count must be positive")
        completed = outcomes["resolved"] + outcomes["partly_resolved"] + outcomes["unresolved"]
        if completed != outcomes["assigned"]:
            raise ValidationError("revision outcome counts do not reconcile")
        expected_rate = outcomes["resolved"] / outcomes["assigned"]
        if abs(outcomes["resolution_rate"] - expected_rate) > 1e-9:
            raise ValidationError("revision resolution_rate is inconsistent")


def validate_error_event(data: dict) -> None:
    required = {
        "event_id", "attempt_id", "taxonomy_version", "code", "source_excerpt",
        "audio_timestamp", "suggested_revision", "reason", "level", "severity",
        "task_specific", "opportunity_present", "historical_status",
    }
    missing = required - data.keys()
    if missing:
        raise ValidationError(f"missing event fields: {sorted(missing)}")
    if data["level"] not in LEVELS:
        raise ValidationError("invalid event level")
    if data["severity"] not in SEVERITIES:
        raise ValidationError("invalid event severity")
    if data["historical_status"] not in STATUSES:
        raise ValidationError("invalid historical_status")
    if data["opportunity_present"] is not True:
        raise ValidationError("an error event requires opportunity_present=true")
    if data["level"] in {"must_fix", "should_fix"} and not (
        str(data["source_excerpt"]).strip() or data["audio_timestamp"]
    ):
        raise ValidationError("counted event requires traceable evidence")
```

- [ ] **Step 6: Run validation tests**

Run: `python3 -m pytest tests/test_validation.py -v`

Expected: 7 tests pass.

- [ ] **Step 7: Commit the validation layer**

```bash
git add tools/toefl_tracker tests/test_validation.py
git commit -m "feat: validate TOEFL attempt records"
```

### Task 4: Register Immutable Attempts and Reject Duplicates

**Files:**
- Create: `tools/toefl_tracker/register.py`
- Create: `tools/register_attempt.py`
- Create: `tests/test_register.py`

**Interfaces:**
- Consumes: `validate_attempt`, `validate_error_event`, `canonical_source_hash`, `atomic_write_text`.
- Produces:
  - `register_attempt(root: Path, attempt: dict, prompt: str, response: str, feedback: str, events: list[dict]) -> Path`
  - CLI arguments `--root`, `--attempt`, `--prompt`, `--response`, `--feedback`, `--events`.

- [ ] **Step 1: Write registration and duplicate tests**

```python
# tests/test_register.py
import json
from pathlib import Path

import pytest

from test_validation import MANIFEST, valid_attempt
from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.register import register_attempt


def test_register_writes_immutable_attempt_and_events(tmp_path: Path) -> None:
    attempt = valid_attempt()
    attempt["source_hash"] = canonical_source_hash("prompt", "response")
    event = {
        "event_id": "ERR-20260731-0001",
        "attempt_id": attempt["attempt_id"],
        "taxonomy_version": 1,
        "code": "GRAM-NEGATION",
        "source_excerpt": "do not think it is not",
        "audio_timestamp": None,
        "suggested_revision": "do not think it is",
        "reason": "Double negative.",
        "level": "must_fix",
        "severity": "meaning_changing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": "new",
    }
    path = register_attempt(tmp_path, MANIFEST, attempt, "prompt", "response", "feedback", [event])
    assert (path / "attempt.yaml").exists()
    assert (path / "prompt.md").read_text() == "prompt\n"
    assert (path / "response-original.md").read_text() == "response\n"
    rows = (tmp_path / "tracker/writing/error-events.jsonl").read_text().splitlines()
    assert json.loads(rows[0])["event_id"] == event["event_id"]


def test_duplicate_source_hash_is_rejected(tmp_path: Path) -> None:
    attempt = valid_attempt()
    attempt["source_hash"] = canonical_source_hash("prompt", "response")
    register_attempt(tmp_path, MANIFEST, attempt, "prompt", "response", "feedback", [])
    duplicate = {**attempt, "attempt_id": "W-AD-20260731-002"}
    with pytest.raises(ValidationError, match="duplicate"):
        register_attempt(tmp_path, MANIFEST, duplicate, "prompt", "response", "feedback", [])


def test_revision_uses_revision_filename_and_parent_link(tmp_path: Path) -> None:
    original = valid_attempt()
    register_attempt(tmp_path, MANIFEST, original, "prompt", "response", "feedback", [])
    revision = {
        **valid_attempt(),
        "attempt_id": "W-AD-20260731-001-R1",
        "record_type": "revision",
        "parent_attempt_id": original["attempt_id"],
        "revision_outcomes": {
            "assigned": 2,
            "resolved": 1,
            "partly_resolved": 1,
            "unresolved": 0,
            "new_errors": 0,
            "resolution_rate": 0.5,
        },
        "source_hash": canonical_source_hash("prompt", "revised response"),
    }
    path = register_attempt(
        tmp_path, MANIFEST, revision, "prompt", "revised response", "feedback", []
    )
    assert (path / "response-revision.md").read_text() == "revised response\n"
    assert not (path / "response-original.md").exists()
```

- [ ] **Step 2: Run and verify the tests fail**

Run: `python3 -m pytest tests/test_register.py -v`

Expected: FAIL because `toefl_tracker.register` does not exist.

- [ ] **Step 3: Implement registration**

```python
# tools/toefl_tracker/register.py
import json
from pathlib import Path

import yaml

from toefl_tracker.io import atomic_write_text, canonical_source_hash, read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.validation import validate_attempt, validate_error_event


def _attempt_directories(root: Path, modality: str) -> list[Path]:
    base = root / "tracker" / modality / "attempts"
    return sorted(path for path in base.glob("*") if path.is_dir()) if base.exists() else []


def _response_filename(modality: str, record_type: str) -> str:
    if modality == "writing":
        return "response-revision.md" if record_type == "revision" else "response-original.md"
    return "transcript-revision.md" if record_type == "revision" else "transcript-original.md"


def register_attempt(
    root: Path,
    manifest: dict,
    attempt: dict,
    prompt: str,
    response: str,
    feedback: str,
    events: list[dict],
) -> Path:
    expected_hash = canonical_source_hash(prompt, response)
    if attempt["source_hash"] != expected_hash:
        raise ValidationError("source_hash does not match prompt and response")
    validate_attempt(attempt, manifest)
    for event in events:
        validate_error_event(event)
        if event["attempt_id"] != attempt["attempt_id"]:
            raise ValidationError("event attempt_id does not match attempt")
    for directory in _attempt_directories(root, attempt["modality"]):
        existing = read_yaml(directory / "attempt.yaml")
        if existing["attempt_id"] == attempt["attempt_id"]:
            raise ValidationError("attempt_id already exists")
        if existing["source_hash"] == attempt["source_hash"]:
            raise ValidationError(f"duplicate source_hash: {existing['attempt_id']}")
    if attempt["record_type"] == "revision":
        parent = root / "tracker" / attempt["modality"] / "attempts" / attempt["parent_attempt_id"]
        if not (parent / "attempt.yaml").exists():
            raise ValidationError("revision parent does not exist")
    destination = root / "tracker" / attempt["modality"] / "attempts" / attempt["attempt_id"]
    destination.mkdir(parents=True, exist_ok=False)
    atomic_write_text(destination / "attempt.yaml", yaml.safe_dump(attempt, allow_unicode=True, sort_keys=False))
    atomic_write_text(destination / "prompt.md", prompt.rstrip() + "\n")
    response_name = _response_filename(attempt["modality"], attempt["record_type"])
    atomic_write_text(destination / response_name, response.rstrip() + "\n")
    atomic_write_text(destination / "feedback-round-1.md", feedback.rstrip() + "\n")
    ledger = root / "tracker" / attempt["modality"] / "error-events.jsonl"
    previous = ledger.read_text(encoding="utf-8") if ledger.exists() else ""
    appended = "".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events)
    atomic_write_text(ledger, previous + appended)
    return destination
```

- [ ] **Step 4: Add the thin CLI**

```python
# tools/register_attempt.py
import argparse
import json
from pathlib import Path

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.register import register_attempt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    args = parser.parse_args()
    manifest = read_yaml(args.root / "standards/ets-2026/manifest.yaml")
    events = [json.loads(line) for line in args.events.read_text().splitlines() if line.strip()]
    attempt = read_yaml(args.attempt)
    prompt = args.prompt.read_text()
    response = args.response.read_text()
    attempt["source_hash"] = canonical_source_hash(prompt, response)
    destination = register_attempt(
        args.root,
        manifest,
        attempt,
        prompt,
        response,
        args.feedback.read_text(),
        events,
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run registration tests**

Run: `python3 -m pytest tests/test_register.py -v`

Expected: 3 tests pass.

- [ ] **Step 6: Commit registration**

```bash
git add tools/toefl_tracker/register.py tools/register_attempt.py tests/test_register.py
git commit -m "feat: register immutable TOEFL attempts"
```

### Task 5: Compute Error History States from Formal Originals

**Files:**
- Create: `tools/toefl_tracker/status.py`
- Create: `tests/test_status.py`

**Interfaces:**
- Consumes: ordered formal-original attempts containing `attempt_id`, `opportunities`; counted error events.
- Produces: `classify_code(code: str, attempts: list[dict], events: list[dict]) -> str | None`.

- [ ] **Step 1: Write table-driven status tests**

```python
# tests/test_status.py
import pytest

from toefl_tracker.status import classify_code


def attempts(counts: list[int]) -> list[dict]:
    return [
        {
            "attempt_id": f"W-AD-20260731-{index:03d}",
            "record_type": "formal_original",
            "opportunities": {"GRAM-NEGATION": 1},
        }
        for index in range(1, len(counts) + 1)
    ]


def events(counts: list[int]) -> list[dict]:
    result = []
    for index, count in enumerate(counts, start=1):
        for occurrence in range(count):
            result.append({
                "attempt_id": f"W-AD-20260731-{index:03d}",
                "code": "GRAM-NEGATION",
                "level": "must_fix",
                "severity": "meaning_changing",
                "event_id": f"E-{index}-{occurrence}",
            })
    return result


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ([1], "new"),
        ([1, 1], "recurring"),
        ([1, 0, 1, 0, 1], "persistent"),
        ([2, 2, 1, 0], "improving"),
        ([1, 0, 0, 0], "controlled"),
        ([1, 0, 0, 0, 1], "relapsed"),
    ],
)
def test_status_transitions(counts: list[int], expected: str) -> None:
    assert classify_code("GRAM-NEGATION", attempts(counts), events(counts)) == expected


def test_attempt_without_opportunity_does_not_advance_control() -> None:
    rows = attempts([1, 0, 0, 0])
    rows[2]["opportunities"]["GRAM-NEGATION"] = 0
    assert classify_code("GRAM-NEGATION", rows, events([1, 0, 0, 0])) == "new"


def test_lower_recent_severity_is_improving_even_when_rate_is_flat() -> None:
    rows = attempts([1, 1, 1, 1])
    history = events([1, 1, 1, 1])
    history[0]["severity"] = "meaning_changing"
    history[1]["severity"] = "meaning_changing"
    history[2]["severity"] = "clarity_reducing"
    history[3]["severity"] = "clarity_reducing"
    assert classify_code("GRAM-NEGATION", rows, history) == "improving"
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m pytest tests/test_status.py -v`

Expected: FAIL because `toefl_tracker.status` does not exist.

- [ ] **Step 3: Implement the ordered state machine**

```python
# tools/toefl_tracker/status.py
from collections import Counter


SEVERITY = {"minor": 1, "clarity_reducing": 2, "meaning_changing": 3}


def classify_code(code: str, attempts: list[dict], events: list[dict]) -> str | None:
    comparable = [
        attempt for attempt in attempts
        if attempt["record_type"] == "formal_original"
        and attempt.get("opportunities", {}).get(code, 0) > 0
    ]
    if not comparable:
        return None
    counts = Counter(
        event["attempt_id"]
        for event in events
        if event["code"] == code and event["level"] in {"must_fix", "should_fix"}
    )
    severity_by_attempt = {
        attempt["attempt_id"]: max(
            (
                SEVERITY[event["severity"]]
                for event in events
                if event["code"] == code
                and event["attempt_id"] == attempt["attempt_id"]
                and event["level"] in {"must_fix", "should_fix"}
            ),
            default=0,
        )
        for attempt in comparable
    }
    series = [counts[attempt["attempt_id"]] for attempt in comparable]
    rates = [
        counts[attempt["attempt_id"]] / attempt["opportunities"][code]
        for attempt in comparable
    ]
    severities = [severity_by_attempt[attempt["attempt_id"]] for attempt in comparable]
    occurred_indices = [index for index, value in enumerate(series) if value > 0]
    if not occurred_indices:
        return None
    controlled_at = next(
        (
            index
            for index in range(3, len(series))
            if series[index - 2:index + 1] == [0, 0, 0]
            and any(value > 0 for value in series[:index - 2])
        ),
        None,
    )
    if controlled_at is not None and any(value > 0 for value in series[controlled_at + 1:]):
        return "relapsed"
    if series[-3:] == [0, 0, 0] and any(value > 0 for value in series[:-3]):
        return "controlled"
    if len(series) >= 4 and (
        sum(rates[-2:]) < sum(rates[-4:-2])
        or max(severities[-2:]) < max(severities[-4:-2])
    ):
        return "improving"
    if len(series) >= 5 and sum(value > 0 for value in series[-5:]) >= 3:
        return "persistent"
    affected = sum(value > 0 for value in series)
    return "new" if affected == 1 else "recurring"
```

- [ ] **Step 4: Run the status tests and resolve the opportunity expectation**

Run: `python3 -m pytest tests/test_status.py -v`

Expected: all 8 tests pass; the no-opportunity case remains `new` because the skipped attempt cannot count toward three clean comparable attempts.

- [ ] **Step 5: Commit the status engine**

```bash
git add tools/toefl_tracker/status.py tests/test_status.py
git commit -m "feat: classify recurring TOEFL errors"
```

### Task 6: Rebuild Dashboards, Profiles, and Three-Practice Reports

**Files:**
- Create: `tools/toefl_tracker/reports.py`
- Create: `tools/rebuild_reports.py`
- Create: `tests/test_reports.py`

**Interfaces:**
- Consumes: valid attempt directories and modality error ledger.
- Produces:
  - `rebuild_modality(root: Path, modality: str) -> list[Path]`
  - `tracker/<modality>/dashboard.csv`
  - `tracker/<modality>/profile.md`
  - `tracker/<modality>/reports/<report-id>.md`

- [ ] **Step 1: Write cadence and exclusion tests**

```python
# tests/test_reports.py
from pathlib import Path

import yaml

from toefl_tracker.reports import rebuild_modality


def write_attempt(root: Path, attempt_id: str, task_type: str, record_type: str) -> None:
    directory = root / "tracker/writing/attempts" / attempt_id
    directory.mkdir(parents=True)
    data = {
        "attempt_id": attempt_id,
        "modality": "writing",
        "task_type": task_type,
        "record_type": record_type,
        "submitted_at": f"2026-07-{10 + int(attempt_id[-1]):02d}T10:00:00+08:00",
        "word_count": 100,
        "duration_seconds": 600,
        "task_score": {"scale": "0-5", "value": 3, "confidence": "medium"},
        "task_metrics": {},
        "opportunities": {},
        "parent_attempt_id": "W-AD-2" if record_type == "revision" else None,
        "revision_outcomes": (
            {
                "assigned": 2,
                "resolved": 1,
                "partly_resolved": 1,
                "unresolved": 0,
                "new_errors": 0,
                "resolution_rate": 0.5,
            }
            if record_type == "revision"
            else None
        ),
    }
    (directory / "attempt.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def test_third_formal_writing_creates_common_and_task_reports(tmp_path: Path) -> None:
    write_attempt(tmp_path, "W-AD-1", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2", "academic_discussion", "formal_original")
    write_attempt(tmp_path, "W-AD-2-R1", "academic_discussion", "revision")
    write_attempt(tmp_path, "W-AD-3", "academic_discussion", "formal_original")
    generated = rebuild_modality(tmp_path, "writing")
    names = {path.name for path in generated}
    assert "writing-common-0003.md" in names
    assert "writing-academic-discussion-0003.md" in names
    dashboard = (tmp_path / "tracker/writing/dashboard.csv").read_text()
    assert "W-AD-2-R1" not in dashboard
    report = (tmp_path / "tracker/writing/reports/writing-common-0003.md").read_text()
    assert "Revision resolution rate: 50.0%" in report
    assert "## Next two focuses" in report


def test_rebuild_restores_every_crossed_three_attempt_boundary(tmp_path: Path) -> None:
    for index in range(1, 8):
        write_attempt(tmp_path, f"W-AD-{index}", "academic_discussion", "formal_original")
    generated = {path.name for path in rebuild_modality(tmp_path, "writing")}
    assert "writing-common-0003.md" in generated
    assert "writing-common-0006.md" in generated
    assert "writing-academic-discussion-0003.md" in generated
    assert "writing-academic-discussion-0006.md" in generated
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m pytest tests/test_reports.py -v`

Expected: FAIL because the report module does not exist.

- [ ] **Step 3: Implement deterministic report rebuilding**

```python
# tools/toefl_tracker/reports.py
import csv
import json
from collections import Counter
from io import StringIO
from pathlib import Path

from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.status import classify_code


def _load_attempts(root: Path, modality: str) -> list[dict]:
    base = root / "tracker" / modality / "attempts"
    rows = [read_yaml(path) for path in base.glob("*/attempt.yaml")] if base.exists() else []
    return sorted(rows, key=lambda row: (row["submitted_at"], row["attempt_id"]))


def _load_events(root: Path, modality: str) -> list[dict]:
    path = root / "tracker" / modality / "error-events.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _dashboard(formals: list[dict], events: list[dict]) -> str:
    buffer = StringIO()
    fields = [
        "attempt_id", "submitted_at", "task_type", "timed", "score", "word_count",
        "duration_seconds", "counted_errors", "errors_per_100_words",
        "meaning_changing_per_100_words", "task_metrics",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    counts = Counter(
        event["attempt_id"] for event in events if event["level"] in {"must_fix", "should_fix"}
    )
    severe = Counter(
        event["attempt_id"]
        for event in events
        if event["level"] in {"must_fix", "should_fix"}
        and event["severity"] == "meaning_changing"
    )
    for attempt in formals:
        words = attempt.get("word_count")
        writer.writerow({
            "attempt_id": attempt["attempt_id"],
            "submitted_at": attempt["submitted_at"],
            "task_type": attempt["task_type"],
            "timed": attempt.get("timed", ""),
            "score": attempt.get("task_score", {}).get("value", ""),
            "word_count": words or "",
            "duration_seconds": attempt.get("duration_seconds", ""),
            "counted_errors": counts[attempt["attempt_id"]],
            "errors_per_100_words": (
                f"{counts[attempt['attempt_id']] * 100 / words:.2f}" if words else ""
            ),
            "meaning_changing_per_100_words": (
                f"{severe[attempt['attempt_id']] * 100 / words:.2f}" if words else ""
            ),
            "task_metrics": json.dumps(
                attempt.get("task_metrics", {}), ensure_ascii=False, sort_keys=True
            ),
        })
    return buffer.getvalue()


def _report_markdown(
    title: str,
    formals: list[dict],
    revisions: list[dict],
    events: list[dict],
) -> str:
    formal_ids = {row["attempt_id"] for row in formals}
    counted = [
        event for event in events
        if event["attempt_id"] in formal_ids and event["level"] in {"must_fix", "should_fix"}
    ]
    ranking = Counter(event["code"] for event in counted)
    codes = [code for code, _ in ranking.most_common()]
    states = [
        (code, classify_code(code, formals, counted))
        for code in codes
    ]
    scores = [
        str(row.get("task_score", {}).get("value", "diagnostic"))
        for row in formals
    ]
    assigned = sum(row["revision_outcomes"]["assigned"] for row in revisions)
    resolved = sum(row["revision_outcomes"]["resolved"] for row in revisions)
    resolution = f"{resolved / assigned:.1%}" if assigned else "no revisions"
    severe = sum(event["severity"] == "meaning_changing" for event in counted)
    ranking_lines = "\n".join(
        f"- `{code}`: {count}" for code, count in ranking.most_common()
    ) or "- No counted errors"
    state_lines = "\n".join(
        f"- `{code}`: {state}" for code, state in states if state is not None
    ) or "- No established status"
    bottleneck = f"`{codes[0]}`" if codes else "No counted bottleneck"
    focus_lines = "\n".join(f"- `{code}`" for code in codes[:2]) or "- Maintain current control"
    metric_lines = "\n".join(
        f"- {row['attempt_id']}: {json.dumps(row.get('task_metrics', {}), ensure_ascii=False, sort_keys=True)}"
        for row in formals
    )
    return (
        f"# {title}\n\n"
        f"## Comparable range\n\n{formals[0]['attempt_id']} through {formals[-1]['attempt_id']}\n\n"
        f"## Result trend\n\n{' → '.join(scores)}\n\n"
        f"## Task metric snapshots\n\n{metric_lines}\n\n"
        f"## Severe-error trend\n\nMeaning-changing events: {severe}\n\n"
        f"## Recurring-error ranking\n\n{ranking_lines}\n\n"
        f"## Historical states\n\n{state_lines}\n\n"
        f"## Revision success\n\nRevision resolution rate: {resolution}\n\n"
        f"## Main next-level bottleneck\n\n{bottleneck}\n\n"
        f"## Next two focuses\n\n{focus_lines}\n"
    )


def rebuild_modality(root: Path, modality: str) -> list[Path]:
    attempts = _load_attempts(root, modality)
    formals = [row for row in attempts if row["record_type"] == "formal_original"]
    events = _load_events(root, modality)
    base = root / "tracker" / modality
    atomic_write_text(base / "dashboard.csv", _dashboard(formals, events))
    codes = sorted({event["code"] for event in events})
    states = [(code, classify_code(code, formals, events)) for code in codes]
    profile = "# Current Profile\n\n" + "".join(
        f"- `{code}`: {state}\n" for code, state in states if state is not None
    )
    atomic_write_text(base / "profile.md", profile)
    reports = []
    revisions = [row for row in attempts if row["record_type"] == "revision"]
    for boundary in range(3, len(formals) + 1, 3):
        window = formals[:boundary]
        window_ids = {row["attempt_id"] for row in window}
        window_revisions = [row for row in revisions if row["parent_attempt_id"] in window_ids]
        common = base / "reports" / f"{modality}-common-{boundary:04d}.md"
        atomic_write_text(
            common,
            _report_markdown(f"{modality.title()} Common Report", window, window_revisions, events),
        )
        reports.append(common)
    for task_type in sorted({row["task_type"] for row in formals}):
        rows = [row for row in formals if row["task_type"] == task_type]
        for boundary in range(3, len(rows) + 1, 3):
            window = rows[:boundary]
            window_ids = {row["attempt_id"] for row in window}
            window_revisions = [row for row in revisions if row["parent_attempt_id"] in window_ids]
            slug = task_type.replace("_", "-")
            report = base / "reports" / f"{modality}-{slug}-{boundary:04d}.md"
            atomic_write_text(
                report,
                _report_markdown(task_type, window, window_revisions, events),
            )
            reports.append(report)
    return reports
```

- [ ] **Step 4: Add the rebuild CLI**

```python
# tools/rebuild_reports.py
import argparse
from pathlib import Path

from toefl_tracker.reports import rebuild_modality


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--modality", choices=["writing", "speaking", "all"], default="all")
    args = parser.parse_args()
    modalities = ["writing", "speaking"] if args.modality == "all" else [args.modality]
    for modality in modalities:
        for path in rebuild_modality(args.root, modality):
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run report tests**

Run: `python3 -m pytest tests/test_reports.py -v`

Expected: 2 tests pass.

- [ ] **Step 6: Commit reporting**

```bash
git add tools/toefl_tracker/reports.py tools/rebuild_reports.py tests/test_reports.py
git commit -m "feat: rebuild TOEFL progress reports"
```

### Task 7: Audit Cross-File Integrity and Add the Repository Constitution

**Files:**
- Create: `tools/toefl_tracker/audit.py`
- Create: `tools/validate_tracker.py`
- Create: `AGENTS.md`
- Create: `tests/test_audit.py`
- Create: `tests/test_agents_contract.py`

**Interfaces:**
- Consumes: every standards, attempt, event, dashboard, and profile file.
- Produces:
  - `audit_workspace(root: Path) -> list[str]`
  - CLI exit code `0` for no problems and `1` for integrity errors.
  - root instructions routing writing and speaking requests to repo skills.

- [ ] **Step 1: Write failing audit tests**

```python
# tests/test_audit.py
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
```

```python
# tests/test_agents_contract.py
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_agents_file_contains_non_negotiable_coaching_rules() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    required = [
        "toefl-writing-coach",
        "toefl-speaking-coach",
        "繁體中文",
        "不得把單題結果當成完整 section band",
        "第一輪最多三個改善目標",
        "第一輪不提供完整範文",
        "revision 不計入 formal attempt",
        "預設不複製原始音檔",
        "validate_tracker.py",
    ]
    assert all(rule in text for rule in required)
    assert len(text.splitlines()) <= 100
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m pytest tests/test_audit.py tests/test_agents_contract.py -v`

Expected: FAIL because the audit module and `AGENTS.md` do not exist.

- [ ] **Step 3: Implement the integrity audit**

```python
# tools/toefl_tracker/audit.py
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
    manifest = read_yaml(manifest_path) if manifest_path.exists() else {"rubrics": {}}
    for modality in ("writing", "speaking"):
        base = root / "tracker" / modality
        attempts: dict[str, dict] = {}
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
                required_files = [directory / "prompt.md", directory / response_name, directory / "feedback-round-1.md"]
                if any(not required.exists() for required in required_files):
                    problems.append(f"{attempt['attempt_id']}: missing immutable evidence file")
                else:
                    expected_hash = canonical_source_hash(
                        (directory / "prompt.md").read_text(),
                        (directory / response_name).read_text(),
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
            except (KeyError, TypeError, ValueError) as error:
                problems.append(f"{path}: {error}")
        ledger = base / "error-events.jsonl"
        if ledger.exists():
            for number, line in enumerate(ledger.read_text().splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    validate_error_event(event)
                    if event["attempt_id"] not in attempts:
                        problems.append(f"orphan event {event['event_id']}")
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                    problems.append(f"{ledger}:{number}: {error}")
        for attempt in attempts.values():
            if attempt["record_type"] == "revision" and attempt["parent_attempt_id"] not in attempts:
                problems.append(f"missing revision parent for {attempt['attempt_id']}")
        if attempts:
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
                actual_reports = {
                    path.relative_to(base)
                    for path in (base / "reports").glob("*.md")
                } if (base / "reports").exists() else set()
                if actual_reports != {path for path in expected_files if path.parts[0] == "reports"}:
                    problems.append(f"{modality}: derived report set is stale")
                for relative in expected_files:
                    expected = raw_base / relative
                    actual = base / relative
                    if not actual.exists() or actual.read_text(encoding="utf-8") != expected.read_text(encoding="utf-8"):
                        problems.append(f"{modality}: stale derived file {relative}")
    return sorted(problems)
```

- [ ] **Step 4: Add the validator CLI**

```python
# tools/validate_tracker.py
import argparse
from pathlib import Path

from toefl_tracker.audit import audit_workspace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    problems = audit_workspace(args.root)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Create the concise root `AGENTS.md`**

```markdown
# AGENTS.md

## Mission

Coach this learner toward TOEFL iBT 2026 Writing and Speaking section band 6 using evidence-based, persistent feedback.

## Language

- Use 繁體中文 for explanations and coaching by default.
- Preserve English prompts and learner evidence verbatim.
- Give corrected English and practice instructions with concise Chinese explanations.

## Routing

- Writing prompt, response, revision, or writing progress request: use `.agents/skills/toefl-writing-coach`.
- Speaking prompt, audio, transcript, re-recording, or speaking progress request: use `.agents/skills/toefl-speaking-coach`.
- Load only the selected task route and its directly relevant references.
- Build a Sentence belongs to the 2026 Writing section but is outside the two open-response coaching routes in this phase.

## Score Boundaries

- Use the standards version recorded in `standards/ets-2026/manifest.yaml`.
- Label each result as official basis, simulated task score, or diagnostic only.
- 不得把單題結果當成完整 section band。
- If an official source cannot be rechecked, state the last verified standards date.
- Never silently replace a rubric version on an existing attempt.

## Feedback Contract

- First-round feedback gives evidence, current level, why not the next level, and 第一輪最多三個改善目標。
- 第一輪不提供完整範文；the learner revises or re-records first.
- Separate must-fix, should-fix, and polish; polish does not count in error rates.
- Every counted issue links to an exact excerpt or audio timestamp.
- Explain why the work is at the current level and why it has not reached the next level.

## Persistence

- A complete prompt and complete answer defaults to `formal_original` unless the learner says not to record it.
- A revision must link to its parent; revision 不計入 formal attempt。
- Never overwrite originals, revisions, or prior rubric evaluations.
- Run `tools/validate_tracker.py` after tracker changes and rebuild derived reports.
- Every three formal records trigger the applicable common report; every three same-task records trigger the task-specific report.
- Common language problems may cross writing routes; task-specific codes may not.
- Common speaking problems may cross speaking routes; task-specific codes may not.

## Audio Privacy

- Confirm examiner/learner segment mapping before formal speaking assessment.
- Do not expose private audio URLs.
- 預設不複製原始音檔；store transcripts, segments, metrics, analysis, and source references.
```

- [ ] **Step 6: Run focused and full validation**

Run: `python3 -m pytest tests/test_audit.py tests/test_agents_contract.py -v`

Expected: 3 tests pass.

Run: `python3 -m pytest -v`

Expected: all foundation tests pass.

Run: `python3 tools/validate_tracker.py --root .`

Expected: exit 0 with no output.

- [ ] **Step 7: Commit the foundation contract**

```bash
git add AGENTS.md tools/toefl_tracker/audit.py tools/validate_tracker.py tests/test_audit.py tests/test_agents_contract.py
git commit -m "feat: audit TOEFL tracker integrity"
```

## Foundation Completion Check

- [ ] Run `python3 -m pytest -v` and record the exact pass count.
- [ ] Run `python3 tools/validate_tracker.py --root .` and confirm exit 0.
- [ ] Run `git diff --check`.
- [ ] Confirm `git status --short` is empty after the final commit.
- [ ] Continue with `2026-07-31-toefl-writing-coach.md`, then `2026-07-31-toefl-speaking-coach.md`.
