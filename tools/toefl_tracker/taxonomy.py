from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from toefl_tracker.models import ValidationError


@dataclass(frozen=True)
class TaxonomyEntry:
    taxonomy_version: int
    modality: str
    scope: str
    task_types: tuple[str, ...]
    dimension: str
    taxonomy_review_required: bool = False


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"taxonomy {field} must be a non-empty string")
    return value


def load_taxonomy(root: Path) -> dict[str, TaxonomyEntry]:
    path = root / "standards/ets-2026/taxonomy.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValidationError(f"cannot load taxonomy: {error}") from error
    if not isinstance(data, dict) or type(data.get("taxonomy_version")) is not int:
        raise ValidationError("taxonomy must declare an integer taxonomy_version")
    codes = data.get("codes")
    if not isinstance(codes, dict) or not codes:
        raise ValidationError("taxonomy codes must be a non-empty mapping")

    entries: dict[str, TaxonomyEntry] = {}
    for code, raw in codes.items():
        code = _string(code, "code")
        if not isinstance(raw, dict):
            raise ValidationError(f"taxonomy entry {code} must be a mapping")
        version = raw.get("taxonomy_version")
        if type(version) is not int or version != data["taxonomy_version"]:
            raise ValidationError(f"taxonomy entry {code} has an invalid taxonomy_version")
        modality = _string(raw.get("modality"), f"entry {code} modality")
        if modality not in {"writing", "speaking", "all"}:
            raise ValidationError(f"taxonomy entry {code} has an invalid modality")
        scope = _string(raw.get("scope"), f"entry {code} scope")
        if scope not in {"common", "route"}:
            raise ValidationError(f"taxonomy entry {code} has an invalid scope")
        raw_tasks = raw.get("task_types")
        if not isinstance(raw_tasks, list) or not raw_tasks:
            raise ValidationError(f"taxonomy entry {code} task_types must be a non-empty list")
        task_types = tuple(_string(task, f"entry {code} task_type") for task in raw_tasks)
        dimension = _string(raw.get("dimension"), f"entry {code} dimension")
        review = raw.get("taxonomy_review_required", False)
        if type(review) is not bool:
            raise ValidationError(f"taxonomy entry {code} taxonomy_review_required must be boolean")
        if code == "UNCLASSIFIED":
            if dimension != "taxonomy_review" or review is not True:
                raise ValidationError("UNCLASSIFIED requires taxonomy_review_required")
        elif review:
            raise ValidationError("only UNCLASSIFIED may require taxonomy review")
        entries[code] = TaxonomyEntry(
            taxonomy_version=version,
            modality=modality,
            scope=scope,
            task_types=task_types,
            dimension=dimension,
            taxonomy_review_required=review,
        )
    return entries
