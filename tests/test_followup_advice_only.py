import pytest

from toefl_tracker.models import ValidationError
from toefl_tracker.writing import _validate_revision_follow_up


def _feedback(section: str) -> str:
    return """# Result
Simulated task score: 4/5
# Why this level
The request is clear.
# Why not the next level
Some wording can be more idiomatic.
# Evidence
| Evidence | Level |
| --- | --- |
| `The request is clear.` | polish |
# Priorities
1. Use direct, specific requests.
# Rewrite task
No further rewrite is required.
""" + section


def test_follow_up_accepts_advice_without_learner_exercise() -> None:
    response = "Students urgently need quieter study space."
    feedback = _feedback("""# Naturalness and precision follow-up
1. Excerpt: `Students urgently need quieter study space`
   Reader effect: The wording is understandable but indirect. Option: Students need a quieter place to study.
## Transfer suggestion
Activity: Write a response to a new prompt about a study-space request.
""")

    _validate_revision_follow_up(feedback, response)


def test_follow_up_rejects_mini_practice_even_after_a_no_issue_audit() -> None:
    response = "The request is clear and direct. The deadline is specific."
    feedback = _feedback("""# Naturalness and precision follow-up
No naturalness or precision issue to flag.
## Naturalness audit
1. Candidate: `The request is clear and direct.` — The wording is concise and idiomatic.
2. Candidate: `The deadline is specific.` — The reference is precise and needs no change.
## Transfer suggestion
Activity: Write a response to a new prompt using the same control.
## Mini-practice
1. Rewrite the request.
""")

    with pytest.raises(ValidationError, match="must not contain mini-practice"):
        _validate_revision_follow_up(feedback, response)
