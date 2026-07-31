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
