from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / ".agents/skills/toefl-speaking-coach"


def test_speaking_taxonomy_contains_common_and_route_codes() -> None:
    text = (SKILL / "references/speaking-error-taxonomy.md").read_text()
    required = {
        "SPK-INTELLIGIBILITY",
        "SPK-PRONUNCIATION",
        "SPK-STRESS",
        "SPK-RHYTHM",
        "SPK-INTONATION",
        "SPK-FLUENCY",
        "SPK-GRAMMAR",
        "SPK-VOCABULARY",
        "LR-OMISSION",
        "LR-ADDITION",
        "LR-SUBSTITUTION",
        "LR-WORD-ORDER",
        "INTERVIEW-DIRECTNESS",
        "INTERVIEW-RELEVANCE",
        "INTERVIEW-ELABORATION",
        "INTERVIEW-COHERENCE",
    }
    assert all(f"`{code}`" in text for code in required)


def test_standards_fix_item_counts_and_diagnostic_boundary() -> None:
    repeat = (ROOT / "standards/ets-2026/speaking-listen-repeat.md").read_text()
    interview = (ROOT / "standards/ets-2026/speaking-interview.md").read_text()
    assert "7 items" in repeat
    assert "4 questions" in interview
    assert "診斷" in repeat and "診斷" in interview
    assert "不得換算完整 Speaking section band" in repeat
    assert "不得換算完整 Speaking section band" in interview


def test_skill_requires_quality_and_mapping_before_assessment() -> None:
    text = (SKILL / "SKILL.md").read_text()
    assert len(text.splitlines()) < 200
    assert "references/audio-intake.md" in text
    assert "references/listen-and-repeat.md" in text
    assert "references/take-an-interview.md" in text
    assert "配對完成前不得正式評估" in text
    assert "diagnostic_only" in text
    assert "最多三個" in text
    assert "預設不複製原始音檔" in text


def test_routes_are_not_mixed() -> None:
    repeat = (SKILL / "references/listen-and-repeat.md").read_text()
    interview = (SKILL / "references/take-an-interview.md").read_text()
    assert "Source reconstruction" in repeat
    assert "Idea elaboration" not in repeat
    assert "Idea elaboration" in interview
    assert "Source reconstruction" not in interview
