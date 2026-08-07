"""Versioned, derived writing-skill family aggregation."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from toefl_tracker.models import ValidationError
from toefl_tracker.taxonomy import load_taxonomy


@dataclass(frozen=True)
class SkillFamily:
    name: str
    members: tuple[str, ...]
    task_types: tuple[str, ...]


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"skill family {label} must be a non-empty string")
    return value


def load_skill_families(root: Path) -> dict[str, SkillFamily]:
    path = root / "standards/ets-2026/writing-skill-families.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValidationError(f"cannot load writing skill families: {error}") from error
    if not isinstance(data, dict) or type(data.get("version")) is not int:
        raise ValidationError("writing skill families must declare an integer version")
    raw_families = data.get("families")
    if not isinstance(raw_families, dict) or not raw_families:
        raise ValidationError("writing skill families must be a non-empty mapping")

    taxonomy = load_taxonomy(root)
    families: dict[str, SkillFamily] = {}
    for raw_name, raw_family in raw_families.items():
        name = _nonempty_string(raw_name, "name")
        if not isinstance(raw_family, dict):
            raise ValidationError(f"skill family {name} must be a mapping")
        raw_members = raw_family.get("members")
        raw_tasks = raw_family.get("task_types")
        if not isinstance(raw_members, list) or not raw_members:
            raise ValidationError(f"skill family {name} members must be a non-empty list")
        if not isinstance(raw_tasks, list) or not raw_tasks:
            raise ValidationError(f"skill family {name} task_types must be a non-empty list")
        members = tuple(_nonempty_string(member, f"{name} member") for member in raw_members)
        task_types = tuple(_nonempty_string(task, f"{name} task_type") for task in raw_tasks)
        if len(set(members)) != len(members):
            raise ValidationError(f"skill family {name} contains duplicate members")
        if len(set(task_types)) != len(task_types) or not set(task_types) <= {"email", "academic_discussion"}:
            raise ValidationError(f"skill family {name} has invalid task_types")
        for member in members:
            entry = taxonomy.get(member)
            if entry is None or entry.modality not in {"writing", "all"}:
                raise ValidationError(f"skill family {name} contains non-writing taxonomy member: {member}")
            if not set(task_types) <= set(entry.task_types):
                raise ValidationError(f"skill family {name} task_types exceed member scope: {member}")
        if name in families:
            raise ValidationError(f"duplicate writing skill family: {name}")
        families[name] = SkillFamily(name=name, members=members, task_types=task_types)
    return families


def aggregate_family_hits(
    families: dict[str, SkillFamily],
    attempts: Iterable[dict],
    events: Iterable[dict],
    *,
    task_type: str | None = None,
) -> dict[str, dict]:
    """Aggregate counted formal-original evidence without creating new events."""

    by_attempt: dict[str, dict] = {}
    for attempt in attempts:
        attempt_id = attempt.get("attempt_id")
        if isinstance(attempt_id, str):
            by_attempt[attempt_id] = attempt
    summaries: dict[str, dict] = {}
    for name, family in families.items():
        evidence: list[dict] = []
        for event in events:
            code = event.get("code")
            attempt = by_attempt.get(event.get("attempt_id"))
            if (
                code not in family.members
                or attempt is None
                or attempt.get("modality") != "writing"
                or attempt.get("record_type") != "formal_original"
                or attempt.get("task_type") not in family.task_types
                or (task_type is not None and attempt.get("task_type") != task_type)
                or event.get("level") not in {"must_fix", "should_fix"}
            ):
                continue
            evidence.append({
                "code": code,
                "attempt_id": attempt["attempt_id"],
                "task_type": attempt["task_type"],
                "source_excerpt": event.get("source_excerpt", ""),
            })
        summaries[name] = {
            "family": name,
            "members": list(family.members),
            "task_types": list(family.task_types),
            "event_count": len(evidence),
            "formal_record_count": len({row["attempt_id"] for row in evidence}),
            "evidence": evidence,
        }
    return summaries
