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
