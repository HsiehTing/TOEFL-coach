from pathlib import Path

import pytest

from toefl_tracker.models import ValidationError
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
| `Students urgently need quieter study space` | polish |
# Priorities
1. Use direct, specific requests.
# Rewrite task
Use this control in a new prompt.
""" + section


def test_revision_follow_up_is_bounded_and_non_scoring(tmp_path: Path) -> None:
    response = "Students urgently need quieter study space. Students urgently need a quiet place before exams."
    feedback = _feedback("""# Naturalness and precision follow-up
1. Excerpt: `Students urgently need quieter study space`
   Reader effect: The repeated urgency can sound insistent rather than specific. Option: Students need a quieter place to study before final exams.
## Mini-practice
1. Rewrite your second sentence so it adds a different concrete effect.
2. Replace one general word with a more precise word for the study setting.
""")
    # The parent is not relevant to this focused artifact contract, so only
    # validate assessment-level feedback here.
    from toefl_tracker.writing import _validate_revision_follow_up
    _validate_revision_follow_up(feedback, response)


@pytest.mark.parametrize("section, message", [
    ("# Naturalness and precision follow-up\n1. Excerpt: `missing text`\n## Mini-practice\n1. One\n2. Two\n", "learner text"),
    ("# Naturalness and precision follow-up\n1. Excerpt: `Students urgently need quieter study space`\n## Mini-practice\n1. One\n", "two to four"),
    ("# Naturalness and precision follow-up\n1. Excerpt: `Students urgently need quieter study space`\n## Mini-practice\n1. One\n2. Two\nAnswer: An answer\n", "must not reveal"),
])
def test_revision_follow_up_rejects_unbounded_or_leaked_content(section: str, message: str) -> None:
    from toefl_tracker.writing import _validate_revision_follow_up
    with pytest.raises(ValidationError, match=message):
        _validate_revision_follow_up(_feedback(section), "Students urgently need quieter study space.")
