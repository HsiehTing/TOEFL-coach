from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / ".agents/skills/bug-resolution/SKILL.md"
REFERENCE = ROOT / ".agents/skills/bug-resolution/references/bug-resolution-cli.md"


def test_bug_resolution_requires_captured_evidence_and_explicit_authority() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "tracker/bug-reports/<BUG-ID>/report.yaml" in text
    assert "tools/verify_bug_reports.py --format json" in text
    assert "Read `reproduction.md` before diagnosis" in text
    assert "explicit authority" in text
    assert "Separate authority from diagnosis" in text
    assert "Verify the captured source of truth" in text
    assert "Diagnose and validate the smallest scoped change" in text


def test_bug_resolution_uses_append_only_resolution_commands() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "tools/resolve_bug_report.py" in text
    assert "tools/rebuild_bug_report_index.py" in text
    assert "Do not edit `report.yaml`" in text
    assert "fixed_verified" in text
    assert "durable commit or PR reference" in text
    assert "leave the bug `reported`" in text


def test_bug_resolution_has_executable_outcome_and_recovery_contract() -> None:
    contract = REFERENCE.read_text(encoding="utf-8")

    assert "## 1. Preflight contract" in contract
    assert "## 2. Outcome selection" in contract
    assert "## 3. Command templates" in contract
    assert "## 4. Post-write verification and derived index" in contract
    assert "## 5. Failure and stop matrix" in contract
    assert "## 6. Handoff contract" in contract
    assert "--fix-reference" in contract
    assert "duplicate|cannot_reproduce|wont_fix" in contract
    assert '"passed": true, "problems": []' in contract
    assert "do not repair immutable files manually" in contract
