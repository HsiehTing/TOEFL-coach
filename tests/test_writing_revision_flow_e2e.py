from copy import deepcopy
from pathlib import Path

from test_validation import MANIFEST, valid_attempt
from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.writing import register_writing_attempt


PROMPT = """Which solution should the government choose to support people whose jobs are no longer needed?

Choose either direct financial support or free job training and explain why.
"""

FORMAL_RESPONSE = """I believe free job training is better. Training can help workers learn useful skills, but my example does not yet identify a realistic course or job. Overall, the government should combine training with partial cash aid."""

REVISION_ONE_RESPONSE = """I believe free job training is better. For example, a cashier can take a digital inventory course and apply for logistics jobs. Overall, training is better, but the sentence about costly programs still joins two complete ideas with a comma."""

REVISION_TWO_RESPONSE = """I believe free job training is better. Modern training programs are costly, so many displaced workers cannot afford them without government support. For example, a cashier whose job was replaced by an automated checkout system can take a digital inventory-management course and apply for entry-level logistics jobs. Overall, free training in modern technologies is the better option."""


FORMAL_FEEDBACK = """# Result

Simulated Academic Discussion task score: 3/5.

# Why this level

The response chooses training and offers a relevant but incomplete reason.

# Why not the next level

The conclusion adds a third policy, and the employment example is not concrete.

# Evidence

No counted event is needed for this flow fixture.

# Priorities

1. Choose free training without adding cash aid.
2. Add a course-to-job example.
3. Repair the costly-program sentence.

# Rewrite task

Revise the position, example, and costly-program sentence.
"""


REVISION_ONE_FEEDBACK = """# Result

Simulated Academic Discussion task score: 4/5.

# Why this level

Two of the three assigned priorities are resolved; sentence control remains incomplete.

# Why not the next level

The costly-program sentence still needs a correct clause connection.

# Evidence

No counted event is needed for this flow fixture.

# Priorities

1. Join the costly-program ideas with `so`.

# Rewrite task

Revise only the remaining sentence-control target.

# Targeted drill

Drill status: `not_required_yet`.
Reason: This is revision round 1, so the third revision gate has not been reached.
"""


REVISION_TWO_FEEDBACK = """# Result

Simulated Academic Discussion task score: 4/5.

# Why this level

All three assigned priorities are now resolved, including the remaining clause connection.

# Why not the next level

The response is strong enough for a final naturalness-and-precision pass.

# Evidence

No new counted must-fix or should-fix issue appears.

# Priorities

1. Preserve this sentence control on a new prompt.

# Rewrite task

No further rewrite is required for this revision.

# Targeted drill

Drill status: `skipped`.
Reason: All assigned targets were resolved before the third revision was triggered.

# Naturalness and precision follow-up

1. Excerpt: `I believe free job training is better.`
   Reader effect: The position is clear but can name the comparison more precisely. Option: I believe free job training is more effective than temporary cash support.

2. Excerpt: `Overall, free training in modern technologies is the better option.`
   Reader effect: The conclusion repeats the opening without emphasizing the lasting employment benefit. Option: Overall, free technology training offers a more durable path back to employment.

"""


def _revision(
    parent: dict,
    attempt_id: str,
    submitted_at: str,
    response: str,
    *,
    resolved: int,
    partly_resolved: int,
) -> dict:
    attempt = deepcopy(parent)
    attempt.update(
        {
            "attempt_id": attempt_id,
            "record_type": "revision",
            "parent_attempt_id": parent["attempt_id"],
            "submitted_at": submitted_at,
            "word_count": len(response.split()),
            "source_hash": canonical_source_hash(PROMPT, response),
            "task_score": {"scale": "0-5", "value": 4, "confidence": "medium"},
            "revision_outcomes": {
                "assigned": 3,
                "resolved": resolved,
                "partly_resolved": partly_resolved,
                "unresolved": 3 - resolved - partly_resolved,
                "new_errors": 0,
                "resolution_rate": resolved / 3,
            },
        }
    )
    return attempt


def test_government_training_session_reaches_skipped_drill_then_follow_up(
    tmp_path: Path,
) -> None:
    """Exercise the learner's formal → R1 → R2 completion path end to end."""
    formal = valid_attempt()
    formal.update(
        {
            "attempt_id": "W-AD-FLOW-001",
            "submitted_at": "2026-08-12T09:00:00+08:00",
            "word_count": len(FORMAL_RESPONSE.split()),
            "source_hash": canonical_source_hash(PROMPT, FORMAL_RESPONSE),
        }
    )
    formal_path = register_writing_attempt(
        tmp_path,
        MANIFEST,
        formal,
        PROMPT,
        FORMAL_RESPONSE,
        FORMAL_FEEDBACK,
        [],
    )

    revision_one = _revision(
        formal,
        "W-AD-FLOW-001-R1",
        "2026-08-12T10:00:00+08:00",
        REVISION_ONE_RESPONSE,
        resolved=2,
        partly_resolved=1,
    )
    revision_one_path = register_writing_attempt(
        tmp_path,
        MANIFEST,
        revision_one,
        PROMPT,
        REVISION_ONE_RESPONSE,
        REVISION_ONE_FEEDBACK,
        [],
    )

    revision_two = _revision(
        revision_one,
        "W-AD-FLOW-001-R2",
        "2026-08-12T11:00:00+08:00",
        REVISION_TWO_RESPONSE,
        resolved=3,
        partly_resolved=0,
    )
    revision_two_path = register_writing_attempt(
        tmp_path,
        MANIFEST,
        revision_two,
        PROMPT,
        REVISION_TWO_RESPONSE,
        REVISION_TWO_FEEDBACK,
        [],
    )

    first_feedback = (revision_one_path / "feedback-round-1.md").read_text()
    completed_feedback = (revision_two_path / "feedback-round-1.md").read_text()

    assert formal_path.exists()
    assert "# Targeted drill" in first_feedback
    assert "Drill status: `not_required_yet`." in first_feedback
    assert "# Naturalness and precision follow-up" not in first_feedback

    assert "# Targeted drill" in completed_feedback
    assert "Drill status: `skipped`." in completed_feedback
    assert "# Naturalness and precision follow-up" in completed_feedback
    assert "## Mini-practice" not in completed_feedback
    assert completed_feedback.index("# Targeted drill") < completed_feedback.index(
        "# Naturalness and precision follow-up"
    )

    persisted = read_yaml(revision_two_path / "attempt.yaml")
    assert persisted["parent_attempt_id"] == revision_one["attempt_id"]
    assert persisted["revision_outcomes"]["resolution_rate"] == 1.0
    assert sum(
        read_yaml(path / "attempt.yaml")["record_type"] == "formal_original"
        for path in (tmp_path / "tracker/writing/attempts").iterdir()
        if path.is_dir()
    ) == 1
