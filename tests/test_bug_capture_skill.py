from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_bug_capture_skill_requires_the_cli_before_investigation() -> None:
    skill = ROOT / ".agents/skills/bug-capture/SKILL.md"
    reference = ROOT / ".agents/skills/bug-capture/references/bug-capture-cli.md"

    text = skill.read_text(encoding="utf-8")

    assert "tools/capture_bug_report.py" in text
    assert "Do not begin a code fix" in text
    assert "--include-git-diff" in text
    assert "--confirm-safe-git-diff" in text
    assert "tools/verify_bug_reports.py" in text
    assert "tools/recover_bug_reports.py" in text
    assert "tools/resolve_bug_report.py" in text
    assert "--format json" in text
    assert "Do not use it for planned feature work" in text
    assert "Treat a user-declared learning test environment as normal use" in text
    assert "bug-resolution" in text
    assert "intended purpose" in text
    assert "references/bug-capture-cli.md" in text
    assert "Build a complete capture packet" in text
    assert "Preflight the evidence and retention decision" in text
    assert "Capture and Read the Receipt" in text
    assert "validation.passed" in text
    assert "Handle failure without corrupting the record" in text
    assert "Report and stop" in text
    assert "TODO" not in text
    assert reference.exists()

    contract = reference.read_text(encoding="utf-8")
    assert "## 1. Input contract" in contract
    assert "## 2. Command template" in contract
    assert "## 3. Success contract" in contract
    assert "## 4. Failure and recovery matrix" in contract
    assert "## 5. Handoff contract" in contract
    assert "--purpose" in contract
    assert "--reproducibility" in contract
    assert '"validation": {"passed": true, "problems": []}' in contract
    assert "Never predict, reuse, or manually choose" in contract


def test_bug_capture_skill_decision_fixtures_cover_capture_ask_and_skip() -> None:
    scenarios = (ROOT / "tests/fixtures/bug-capture/decision-scenarios.md").read_text(encoding="utf-8")
    assert "## 1. Complete normal-use defect — capture" in scenarios
    assert "## 2. Incomplete report — ask" in scenarios
    assert "## 3. Implementation-time test failure — do not capture" in scenarios
    assert "## 4. Intended fail-closed capability gap — do not capture" in scenarios
