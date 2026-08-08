"""Deterministic, evidence-linked Writing drill-pack generation."""

import hashlib
import json
from itertools import cycle
from pathlib import Path
from typing import Any

import yaml

from toefl_tracker.io import atomic_write_text, read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.taxonomy import load_taxonomy


_CAUSAL_CODES = {"DISCUSSION-ELABORATION", "DISCUSSION-SUPPORT"}
_SUPPORTED_CODES = {
    "GRAM-CLAUSE", "GRAM-ARTICLE", "GRAM-AGREEMENT", "LEX-WORDFORM",
    "LEX-COLLOCATION", "EMAIL-ACTION", *_CAUSAL_CODES,
}


def _canonical_hash(value: dict[str, Any]) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _recommendation_fields(recommendation: dict) -> tuple[str, str, str, list[str], int]:
    if not isinstance(recommendation, dict):
        raise ValidationError("drill recommendation must be a mapping")
    required = {"recommendation_id", "source_attempt_id", "task_type", "target_codes", "drill"}
    if not required <= recommendation.keys():
        raise ValidationError("drill recommendation is missing required fields")
    recommendation_id = recommendation["recommendation_id"]
    source_attempt_id = recommendation["source_attempt_id"]
    task_type = recommendation["task_type"]
    codes = recommendation["target_codes"]
    drill = recommendation["drill"]
    if not all(isinstance(value, str) and value.strip() for value in (recommendation_id, source_attempt_id)):
        raise ValidationError("drill recommendation IDs must be non-empty strings")
    if task_type not in {"email", "academic_discussion"}:
        raise ValidationError("drill recommendation has invalid task_type")
    if not isinstance(codes, list) or not codes or any(not isinstance(code, str) for code in codes):
        raise ValidationError("drill recommendation target_codes must be non-empty strings")
    if not isinstance(drill, dict) or type(drill.get("item_count")) is not int or drill["item_count"] <= 0:
        raise ValidationError("drill recommendation requires a positive item_count")
    return recommendation_id, source_attempt_id, task_type, sorted(set(codes)), drill["item_count"]


def _source_evidence(root: Path, source_attempt_id: str, task_type: str, codes: list[str]) -> list[dict]:
    directory = root / "tracker/writing/attempts" / source_attempt_id
    attempt_path = directory / "attempt.yaml"
    events_path = directory / "events.jsonl"
    if not attempt_path.exists() or not events_path.exists():
        raise ValidationError("drill pack requires immutable evidence from a persisted source attempt")
    attempt = read_yaml(attempt_path)
    if (
        attempt.get("attempt_id") != source_attempt_id
        or attempt.get("modality") != "writing"
        or attempt.get("record_type") != "formal_original"
        or attempt.get("task_type") != task_type
    ):
        raise ValidationError("drill recommendation source attempt does not match its route")
    rows: list[dict] = []
    try:
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if isinstance(row, dict) and row.get("code") in codes and row.get("level") in {"must_fix", "should_fix"}:
                    rows.append(row)
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError("drill pack cannot read immutable evidence") from error
    if not rows:
        raise ValidationError("drill pack requires immutable evidence for every target code")
    represented = {row.get("code") for row in rows}
    if not set(codes) <= represented:
        raise ValidationError("drill pack requires immutable evidence for every target code")
    for row in rows:
        if not isinstance(row.get("event_id"), str) or not row["event_id"].strip():
            raise ValidationError("drill evidence requires an event_id")
        if not isinstance(row.get("source_excerpt"), str) or not row["source_excerpt"].strip():
            raise ValidationError("drill evidence requires an exact source excerpt")
    return sorted(rows, key=lambda row: (row["code"], row["event_id"]))


def _validate_codes(root: Path, task_type: str, codes: list[str]) -> None:
    taxonomy = load_taxonomy(root)
    for code in codes:
        entry = taxonomy.get(code)
        if entry is None:
            raise ValidationError(f"unknown drill target code: {code}")
        if entry.modality not in {"writing", "all"}:
            raise ValidationError(f"drill target code is not Writing: {code}")
        if task_type not in entry.task_types:
            raise ValidationError(f"drill target code does not apply to {task_type}: {code}")
        if code not in _SUPPORTED_CODES:
            raise ValidationError(f"drill generation is not yet supported for code: {code}")


def supports_writing_drill(root: Path, task_type: str, code: str) -> bool:
    """Return whether an evidence-linked drill can be generated for this route."""
    try:
        _validate_codes(root, task_type, [code])
    except ValidationError:
        return False
    return True


def _clause_item(number: int, task_type: str, evidence: dict) -> dict:
    route_context = (
        "a professional email that completes one requested action"
        if task_type == "email"
        else "an Academic Discussion post that states and supports a position"
    )
    variants = [
        ("identify_boundary", "Identify the clause-boundary problem in a fresh example, then explain the repair in one phrase."),
        ("combine", "Combine two short ideas into one clear sentence with a complete main clause."),
        ("rewrite", "Rewrite a fresh sentence so that every dependent clause has a clear main clause."),
        ("produce", "Write one new sentence with a precise connector and a complete independent clause."),
    ]
    kind, task = variants[(number - 1) % len(variants)]
    return {
        "item_id": f"I{number:02d}",
        "kind": kind,
        "prompt": f"For {route_context}, {task}",
        "response_fields": ["response"],
        "evidence": {"attempt_id": evidence["attempt_id"], "event_id": evidence["event_id"], "code": evidence["code"]},
        "answer_guidance": "A valid response has a complete main clause and makes the logical relationship explicit.",
    }


def _causal_item(number: int, evidence: dict) -> dict:
    return {
        "item_id": f"I{number:02d}",
        "kind": "causal_chain",
        "prompt": "For a fresh Academic Discussion position, build a causal chain. Do not reuse wording from the source response.",
        "response_fields": ["claim", "mechanism", "concrete_outcome", "link_back"],
        "evidence": {"attempt_id": evidence["attempt_id"], "event_id": evidence["event_id"], "code": evidence["code"]},
        "answer_guidance": "A valid chain explains how the claim causes a concrete outcome and explicitly returns to the position.",
    }


def _focused_item(number: int, evidence: dict, *, kind: str, prompt: str, guidance: str) -> dict:
    return {
        "item_id": f"I{number:02d}", "kind": kind, "prompt": prompt,
        "response_fields": ["response"],
        "evidence": {"attempt_id": evidence["attempt_id"], "event_id": evidence["event_id"], "code": evidence["code"]},
        "answer_guidance": guidance,
    }


def _specialized_item(number: int, evidence: dict) -> dict:
    code = evidence["code"]
    templates = {
        "GRAM-ARTICLE": ("article_choice", "Write a fresh sentence and choose each article based on the following noun sound, not merely its spelling.", "Each article matches the intended countability and following sound."),
        "GRAM-AGREEMENT": ("agreement_control", "Write a fresh sentence whose subject and verb clearly agree, including one longer noun phrase.", "The finite verb agrees with the real grammatical subject."),
        "LEX-WORDFORM": ("word_form", "Choose and use the correct word form in a fresh sentence; explain the role it plays in the sentence.", "The chosen form matches the required part of speech and meaning."),
        "LEX-COLLOCATION": ("collocation", "Write a fresh sentence using a natural verb–noun or adjective–noun combination for this route.", "The word combination is idiomatic in the intended context."),
        "EMAIL-ACTION": ("email_action", "Write one professional email sentence that states the requested action, who should take it, and any essential deadline.", "The recipient can identify the requested action and timing immediately."),
    }
    kind, prompt, guidance = templates[code]
    return _focused_item(number, evidence, kind=kind, prompt=prompt, guidance=guidance)


def _learner_markdown(pack: dict) -> str:
    lines = [f"# Writing Targeted Drill `{pack['drill_id']}`", "", f"Route: `{pack['task_type']}`", "", "Write your own answers. The answer key is intentionally separate.", ""]
    for item in pack["items"]:
        lines.extend([f"## {item['item_id']}", item["prompt"], ""])
        for field in item["response_fields"]:
            lines.append(f"- {field}:")
        lines.append("")
    return "\n".join(lines)


def _answer_key_markdown(pack: dict) -> str:
    lines = [f"# Answer key — `{pack['drill_id']}`", "", "Use after completing the learner drill.", ""]
    for item in pack["items"]:
        lines.extend([f"## {item['item_id']}", item["answer_guidance"], ""])
    return "\n".join(lines)


def build_drill_pack(root: Path, recommendation: dict, *, seed: int = 0) -> dict:
    """Build a deterministic, non-scored drill pack from persisted evidence."""
    if type(seed) is not int:
        raise ValidationError("drill seed must be an integer")
    recommendation_id, source_attempt_id, task_type, codes, item_count = _recommendation_fields(recommendation)
    _validate_codes(root, task_type, codes)
    evidence = _source_evidence(root, source_attempt_id, task_type, codes)
    identity = {
        "version": 1,
        "recommendation_id": recommendation_id,
        "source_attempt_id": source_attempt_id,
        "task_type": task_type,
        "target_codes": codes,
        "evidence_event_ids": [row["event_id"] for row in evidence],
        "seed": seed,
    }
    drill_id = "WD-" + _canonical_hash(identity)[:16].upper()
    evidence_cycle = cycle(evidence[seed % len(evidence):] + evidence[:seed % len(evidence)])
    items: list[dict] = []
    for number in range(1, item_count + 1):
        row = next(evidence_cycle)
        if row["code"] == "GRAM-CLAUSE":
            items.append(_clause_item(number, task_type, row))
        elif row["code"] in _CAUSAL_CODES:
            items.append(_causal_item(number, row))
        else:
            items.append(_specialized_item(number, row))
    pack = {
        **identity,
        "drill_id": drill_id,
        "items": items,
    }
    pack["learner_markdown"] = _learner_markdown(pack)
    pack["answer_key_markdown"] = _answer_key_markdown(pack)
    return pack


def write_drill_pack(root: Path, pack: dict) -> Path:
    """Persist a generated pack once; a differing pack with the same ID is rejected."""
    drill_id = pack.get("drill_id")
    if not isinstance(drill_id, str) or not drill_id.startswith("WD-"):
        raise ValidationError("drill pack requires a stable drill_id")
    destination = root / "tracker/writing/drill-packs" / drill_id
    persisted = {key: value for key, value in pack.items() if key not in {"learner_markdown", "answer_key_markdown"}}
    expected = {
        "drill-pack.yaml": yaml.safe_dump(persisted, allow_unicode=True, sort_keys=False),
        "drill.md": pack["learner_markdown"].rstrip() + "\n",
        "answer-key.md": pack["answer_key_markdown"].rstrip() + "\n",
    }
    if destination.exists():
        if all((destination / name).exists() and (destination / name).read_text(encoding="utf-8") == content for name, content in expected.items()):
            return destination
        raise ValidationError("refusing to overwrite an immutable drill pack")
    for name, content in expected.items():
        atomic_write_text(destination / name, content)
    return destination
