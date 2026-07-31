from collections import Counter


SEVERITY = {"minor": 1, "clarity_reducing": 2, "meaning_changing": 3}


def classify_code(code: str, attempts: list[dict], events: list[dict]) -> str | None:
    comparable = [
        attempt for attempt in attempts
        if attempt["record_type"] == "formal_original"
        and attempt.get("opportunities", {}).get(code, 0) > 0
    ]
    if not comparable:
        return None

    counted_events = [
        event for event in events
        if event["code"] == code and event["level"] in {"must_fix", "should_fix"}
    ]
    counts = Counter(event["attempt_id"] for event in counted_events)
    severity_by_attempt = {
        attempt["attempt_id"]: max(
            (
                SEVERITY[event["severity"]]
                for event in counted_events
                if event["attempt_id"] == attempt["attempt_id"]
            ),
            default=0,
        )
        for attempt in comparable
    }
    series = [counts[attempt["attempt_id"]] for attempt in comparable]
    rates = [
        counts[attempt["attempt_id"]] / attempt["opportunities"][code]
        for attempt in comparable
    ]
    severities = [severity_by_attempt[attempt["attempt_id"]] for attempt in comparable]
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
    if len(series) >= 5 and sum(value > 0 for value in series[-5:]) >= 3:
        return "persistent"
    affected = sum(value > 0 for value in series)
    return "new" if affected == 1 else "recurring"
