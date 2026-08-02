from collections import Counter
from collections.abc import Mapping, Sequence


SEVERITY = {"minor": 1, "clarity_reducing": 2, "meaning_changing": 3}


def classify_code(code: str, attempts: Sequence[dict], events: Sequence[dict]) -> str | None:
    if not isinstance(code, str) or code == "UNCLASSIFIED":
        return None
    comparable = [
        attempt for attempt in attempts
        if isinstance(attempt, Mapping)
        and attempt.get("record_type") == "formal_original"
        and isinstance(attempt.get("attempt_id"), str)
        and isinstance(attempt.get("opportunities"), Mapping)
        and type(attempt["opportunities"].get(code)) is int
        and attempt["opportunities"][code] > 0
    ]
    if not comparable:
        return None

    counted_events = [
        event for event in events
        if isinstance(event, Mapping)
        and event.get("code") == code
        and isinstance(event.get("attempt_id"), str)
        and isinstance(event.get("level"), str)
        and event.get("level") in {"must_fix", "should_fix"}
        and isinstance(event.get("severity"), str)
        and event.get("severity") in SEVERITY
    ]
    counts = Counter(event["attempt_id"] for event in counted_events)
    severity_by_attempt = {
        attempt.get("attempt_id"): max(
            (
                SEVERITY[event["severity"]]
                for event in counted_events
                if event.get("attempt_id") == attempt.get("attempt_id")
            ),
            default=0,
        )
        for attempt in comparable
    }
    series = [counts[attempt.get("attempt_id")] for attempt in comparable]
    rates = [
        counts[attempt.get("attempt_id")] / attempt["opportunities"][code]
        for attempt in comparable
    ]
    severities = [severity_by_attempt[attempt.get("attempt_id")] for attempt in comparable]
    occurred_indices = [index for index, value in enumerate(series) if value > 0]
    if not occurred_indices:
        return None

    controlled_at = next(
        (
            index
            for index in range(3, len(series))
            if series[index - 2:index + 1] == [0, 0, 0]
            and any(value > 0 for value in series[:index - 2])
        ),
        None,
    )
    if controlled_at is not None and any(value > 0 for value in series[controlled_at + 1:]):
        return "relapsed"
    if series[-3:] == [0, 0, 0] and any(value > 0 for value in series[:-3]):
        return "controlled"
    if len(series) >= 4 and (
        sum(rates[-2:]) < sum(rates[-4:-2])
        or max(severities[-2:]) < max(severities[-4:-2])
    ):
        return "improving"
    if len(series) >= 3 and sum(value > 0 for value in series[-5:]) >= 3:
        return "persistent"
    affected = sum(value > 0 for value in series)
    return "new" if affected == 1 else "recurring"
