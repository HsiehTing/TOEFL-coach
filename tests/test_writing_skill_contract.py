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


def test_skill_routes_references_and_enforces_iteration() -> None:
    text = (SKILL / "SKILL.md").read_text()
    assert len(text.splitlines()) < 180
    assert "references/email-feedback.md" in text
    assert "references/discussion-feedback.md" in text
    assert "references/writing-error-taxonomy.md" in text
    assert "第一輪不提供完整範文" in text
    assert "最多三個" in text
    assert "tools/validate_tracker.py" in text


def test_writing_skill_uses_dedicated_registration_gate() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "tools/register_writing_attempt.py" in text
    assert "tools/generate_writing_drill.py" in text
    assert "tools/register_writing_transfer.py" in text
    assert "tools/validate_tracker.py" in text


def test_revision_skill_declares_drill_and_follow_up_state_machine() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "revision_targets → targeted_drill_gate → naturalness_follow_up → transfer" in text
    assert all(
        f"`{status}`" in text
        for status in ("not_required_yet", "skipped", "required", "declined", "completed")
    )
    assert "learner explicitly opts in" in text
    assert "learner declines the drill" in text
    assert "Invitation: After reviewing the exact-excerpt feedback" in text
    assert "## New issues (not assigned targets)" in text
    assert "never lower the target-resolution rate" in text
    assert "Do not add a new issue to `# Priorities`" in text
    assert "Make revision feedback constructive, not merely corrective." in text
    assert "For at most two high-leverage items" in text
    assert "Distinguish a hard error from an acceptable-but-less-natural choice" in text
    assert "do not emit the follow-up heading" in text
    assert "Transfer is available only after the follow-up" in text
    assert "Learner questions and assessed practice belong only to a learner-approved targeted drill" in text


def test_task_contracts_have_distinct_required_fields() -> None:
    email = (SKILL / "references/email-feedback.md").read_text()
    discussion = (SKILL / "references/discussion-feedback.md").read_text()
    assert "Register and politeness" in email
    assert "Original contribution" not in email
    assert "Original contribution" in discussion
    assert "Register and politeness" not in discussion


def test_discussion_skill_defines_causal_chain_drill_without_full_model() -> None:
    discussion = (SKILL / "references/discussion-feedback.md").read_text(encoding="utf-8")
    assert "IDEA-DEVELOPMENT" in discussion
    assert "claim" in discussion.lower()
    assert "mechanism" in discussion.lower()
    assert "不提供完整範文" in discussion


def test_discussion_skill_requires_compact_constructive_revision_explanations() -> None:
    discussion = (SKILL / "references/discussion-feedback.md").read_text(encoding="utf-8")
    assert "Constructive revision explanation" in discussion
    assert "parallel verbs after `able to`" in discussion
    assert "acceptable-but-less-natural" in discussion
