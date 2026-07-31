from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / ".agents/skills/toefl-writing-coach"


def test_writing_taxonomy_separates_shared_and_task_codes() -> None:
    text = (SKILL / "references/writing-error-taxonomy.md").read_text()
    shared = {
        "GRAM-ARTICLE",
        "GRAM-NEGATION",
        "GRAM-CLAUSE",
        "GRAM-AGREEMENT",
        "LEX-WORDFORM",
        "LEX-COLLOCATION",
        "MECH-SPELLING",
        "MECH-PUNCTUATION",
    }
    email = {
        "EMAIL-PURPOSE",
        "EMAIL-MISSING-POINT",
        "EMAIL-REGISTER",
        "EMAIL-POLITENESS",
        "EMAIL-ORGANIZATION",
        "EMAIL-ACTION",
    }
    discussion = {
        "DISCUSSION-ALIGNMENT",
        "DISCUSSION-POSITION",
        "DISCUSSION-BORROWING",
        "DISCUSSION-CONTRIBUTION",
        "DISCUSSION-ELABORATION",
        "DISCUSSION-SUPPORT",
    }
    assert all(f"`{code}`" in text for code in shared | email | discussion)


def test_each_open_response_standard_states_the_score_boundary() -> None:
    for name in ("writing-email.md", "writing-discussion.md"):
        text = (ROOT / "standards/ets-2026" / name).read_text()
        assert "0–5" in text
        assert "模擬 task score" in text
        assert "不得換算完整 Writing section band" in text
