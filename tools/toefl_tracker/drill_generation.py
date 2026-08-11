"""Deterministic, evidence-linked Writing drill-pack generation."""

import hashlib
import json
import re
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
_PACK_FORMAT_VERSION = 4
_DEFAULT_MINIMUM_ACCURACY = 0.8


def _canonical_hash(value: dict[str, Any]) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _recommendation_fields(recommendation: dict) -> tuple[str, str, str, list[str], int, float]:
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
    minimum_accuracy = drill.get("minimum_accuracy", _DEFAULT_MINIMUM_ACCURACY)
    if type(minimum_accuracy) not in {int, float} or not 0 < minimum_accuracy <= 1:
        raise ValidationError("drill recommendation minimum_accuracy must be between 0 and 1")
    return recommendation_id, source_attempt_id, task_type, sorted(set(codes)), drill["item_count"], float(minimum_accuracy)


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


_CLAUSE_VARIANTS = {
    "email": [
        (
            "rewrite_fragment",
            "Rewrite this fragment as one complete sentence explaining why the university should add an AI laboratory: `Because AI is increasingly used by technology companies.`",
            "The answer contains a main clause after the dependent `Because` clause and clearly states the requested reason.",
        ),
        (
            "combine",
            "Combine these ideas into one professional email sentence using `because` or `so`: `The current computer room is often full. I recommend adding another computer laboratory.`",
            "The answer has one complete sentence, a clear connector, and the recommendation remains explicit.",
        ),
        (
            "rewrite_fragment",
            "Repair this sentence boundary: `Although building the laboratory would be expensive. It would benefit many students.`",
            "The `Although` clause is attached to a complete main clause; do not leave it as a sentence fragment.",
        ),
        (
            "produce",
            "Write one sentence beginning with `As artificial intelligence becomes more advanced and widely adopted by companies, ...` and finish it with a clear student benefit.",
            "The sentence has a complete main clause after the opening `As` clause and states a specific benefit.",
        ),
        (
            "combine",
            "Combine these ideas into one professional email sentence with `because`: `Many students cannot find a free computer. They need another laboratory.`",
            "The answer has one complete sentence, a clear connector, and the recommendation remains explicit.",
        ),
        (
            "rewrite_fragment",
            "Repair this fragment as one complete email sentence: `Since the laboratory serves many departments.`",
            "The dependent `Since` clause is attached to a complete main clause and states a clear result.",
        ),
        (
            "produce",
            "Write one sentence beginning with `If the university adds a laboratory, ...` and finish it with a specific student benefit.",
            "The conditional clause is followed by a complete main clause and a specific benefit.",
        ),
        (
            "combine",
            "Combine these ideas into one professional email sentence with `so`: `Evening classes are crowded. The university should extend laboratory hours.`",
            "The answer has one complete sentence, a clear connector, and the requested action remains explicit.",
        ),
    ],
    "academic_discussion": [
        (
            "rewrite_fragment",
            "Rewrite this fragment as one complete sentence supporting a university policy: `Because public transportation is often unreliable for students.`",
            "The answer contains a main clause after the dependent `Because` clause and states a clear policy-related result.",
        ),
        (
            "combine",
            "Combine these ideas into one sentence using `because` or `therefore`: `The policy would reduce commuting costs. More students could attend evening classes.`",
            "The answer has one complete sentence and makes the cause-and-effect relationship explicit.",
        ),
        (
            "rewrite_fragment",
            "Repair this sentence boundary: `Although the proposal requires public funding. It could reduce pollution.`",
            "The `Although` clause is attached to a complete main clause; do not leave it as a sentence fragment.",
        ),
        (
            "produce",
            "Write one sentence beginning with `As public transportation becomes more accessible, ...` and finish it with a concrete outcome.",
            "The sentence has a complete main clause after the opening `As` clause and gives a concrete outcome.",
        ),
        (
            "combine",
            "Combine these ideas into one Academic Discussion sentence with `because`: `The policy lowers commuting costs. More students can attend evening classes.`",
            "The answer has one complete sentence and makes the cause-and-effect relationship explicit.",
        ),
        (
            "rewrite_fragment",
            "Repair this fragment as one complete sentence about a university policy: `Since the buses are unreliable for students.`",
            "The dependent `Since` clause is attached to a complete main clause and states a clear result.",
        ),
        (
            "produce",
            "Write one sentence beginning with `If the university improves public transportation, ...` and finish it with a concrete outcome.",
            "The conditional clause is followed by a complete main clause and a concrete outcome.",
        ),
        (
            "combine",
            "Combine these ideas into one Academic Discussion sentence with `so`: `The proposal requires funding. It could reduce pollution.`",
            "The answer has one complete sentence and makes the logical relationship explicit.",
        ),
    ],
}


def _clause_item(number: int, task_type: str, evidence: dict) -> dict:
    variants = _CLAUSE_VARIANTS[task_type]
    kind, task, guidance = variants[(number - 1) % len(variants)]
    return {
        "item_id": f"I{number:02d}",
        "kind": kind,
        "prompt": task,
        "response_fields": ["response"],
        "evidence": {"attempt_id": evidence["attempt_id"], "event_id": evidence["event_id"], "code": evidence["code"]},
        "answer_guidance": guidance,
    }


def _causal_item(number: int, evidence: dict) -> dict:
    prompts = [
        "For a fresh Academic Discussion position about a university policy, write one short sentence showing claim → mechanism → concrete outcome → link back.",
        "For a fresh Academic Discussion position about public services, write one short sentence showing claim → mechanism → concrete outcome → link back.",
        "For a fresh Academic Discussion position about student life, write one short sentence showing claim → mechanism → concrete outcome → link back.",
        "For a fresh Academic Discussion position about community benefits, write one short sentence showing claim → mechanism → concrete outcome → link back.",
        "For a fresh Academic Discussion position about an institutional change, write one short sentence showing claim → mechanism → concrete outcome → link back.",
        "For a fresh Academic Discussion position about a public investment, write one short sentence showing claim → mechanism → concrete outcome → link back.",
        "For a fresh Academic Discussion position about a practical reform, write one short sentence showing claim → mechanism → concrete outcome → link back.",
        "For a fresh Academic Discussion position about long-term effects, write one short sentence showing claim → mechanism → concrete outcome → link back.",
    ]
    return {
        "item_id": f"I{number:02d}",
        "kind": "causal_chain",
        "prompt": prompts[(number - 1) % len(prompts)],
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
        "GRAM-ARTICLE": (
            [
                ("article_choice", "Rewrite this noun phrase with the correct article: `a AI laboratory`. Then use it in one complete email sentence."),
                ("article_choice", "Rewrite this phrase with the correct article: `a useful opportunity`. Then use it in one complete sentence."),
                ("article_choice", "Rewrite this phrase with the correct article: `an university policy`. Then use it in one complete sentence."),
                ("article_choice", "Rewrite this phrase with the correct article: `the additional laboratory`. Then use it in one complete sentence."),
            ],
            "The article must match the noun phrase and the full sentence must be complete.",
        ),
        "GRAM-AGREEMENT": (
            [
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `New facilities could benefits both faculty and students.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `The proposal encourage students to participate.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `A clear message help customers recognize the brand.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `These updates improves the company's public image.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `A company's colors and logo communicates its identity.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `Several customers prefers the updated package.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `The new campaign attract younger audiences.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `Regular updates keeps a brand visible.`"),
            ],
            "The modal `could` is followed by the base verb `benefit`.",
        ),
        "LEX-WORDFORM": (
            [
                ("word_form", "Choose the correct form and rewrite the sentence: `The university should consider my propose.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `The campaign was success among younger customers.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `Regular updates can create a strong impress.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `The company wants to regular its advertising.`"),
            ],
            "The noun `proposal` is the object of `consider`.",
        ),
        "LEX-COLLOCATION": (
            [
                ("collocation", "Rewrite this sentence using natural English: `The laboratory can teach students practical using skills.`"),
                ("collocation", "Rewrite this sentence using natural English: `The campaign gives a positive influence to customers.`"),
                ("collocation", "Rewrite this sentence using natural English: `The company wants to do a decision quickly.`"),
                ("collocation", "Rewrite this sentence using natural English: `The new design can catch customers' eyes.`"),
                ("collocation", "Rewrite this sentence using natural English: `The campaign can make an effect on sales.`"),
                ("collocation", "Rewrite this sentence using natural English: `Customers are easy to be attracted by the new package.`"),
                ("collocation", "Rewrite this sentence using natural English: `The brand should keep its image consistency.`"),
                ("collocation", "Rewrite this sentence using natural English: `The update can let customers remember the product.`"),
            ],
            "The answer uses a natural collocation such as `develop practical skills` or `gain practical experience`.",
        ),
        "EMAIL-ACTION": (
            [
                ("email_action", "Write one professional email sentence asking Ms. Lee to support a proposal and present it to the university administration."),
                ("email_action", "Write one professional email sentence asking Professor Chen to approve a student survey and share it with the department."),
                ("email_action", "Write one professional email sentence asking the coordinator to extend the registration deadline and notify students."),
                ("email_action", "Write one professional email sentence asking the library director to add evening hours and announce the change."),
                ("email_action", "Write one professional email sentence asking the dean to approve a workshop and inform the faculty."),
                ("email_action", "Write one professional email sentence asking the student affairs office to extend advising hours and notify students."),
                ("email_action", "Write one professional email sentence asking the instructor to review your proposal and forward it to the committee."),
                ("email_action", "Write one professional email sentence asking the department chair to support a new course and announce it to students."),
            ],
            "The recipient, requested action, and destination of the proposal are all explicit.",
        ),
    }
    variants, guidance = templates[code]
    kind, prompt = variants[(number - 1) % len(variants)]
    return _focused_item(number, evidence, kind=kind, prompt=prompt, guidance=guidance)


def _learner_markdown(pack: dict) -> str:
    lines = [f"# Writing Targeted Drill `{pack['drill_id']}`", "", f"Route: `{pack['task_type']}`", "", "Write your own answers. The answer key is intentionally separate.", ""]
    for item in pack["items"]:
        lines.extend([f"## {item['item_id']}", item["prompt"], ""])
        for field in item["response_fields"]:
            lines.append(f"- {field}: [write your answer here]")
        lines.append("")
    return "\n".join(lines)


def _answer_key_markdown(pack: dict) -> str:
    lines = [f"# Answer key — `{pack['drill_id']}`", "", "Use after completing the learner drill.", ""]
    for item in pack["items"]:
        lines.extend([f"## {item['item_id']}", item["answer_guidance"], ""])
    return "\n".join(lines)


_SECTION_RE = re.compile(r"(?ms)^## (?P<item_id>[^\n]+)\n(?P<body>.*?)(?=^## |\Z)")
_FIELD_RE = re.compile(r"(?m)^- (?P<field>[A-Za-z0-9_]+):(?:[ \t]*(?P<value>.*))?$")
_PLACEHOLDER = "[write your answer here]"


def _response_sections(markdown: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for match in _SECTION_RE.finditer(markdown):
        item_id = match.group("item_id").strip()
        if item_id in sections:
            raise ValidationError(f"drill response file has duplicate item: {item_id}")
        sections[item_id] = match.group("body")
    if not sections:
        raise ValidationError("drill response file has no item sections")
    return sections


def read_completed_drill(pack_dir: Path) -> dict[str, Any]:
    """Read learner responses from a generated drill.md without reading the answer key."""
    metadata_path = pack_dir / "drill-pack.yaml"
    markdown_path = pack_dir / "drill.md"
    if not metadata_path.exists() or not markdown_path.exists():
        raise ValidationError("drill pack requires drill-pack.yaml and drill.md")
    pack = read_yaml(metadata_path)
    if pack.get("version") != _PACK_FORMAT_VERSION:
        raise ValidationError(
            "legacy or incompatible drill pack; generate a new versioned pack before registering it"
        )
    markdown = markdown_path.read_text(encoding="utf-8")
    expected_items = pack.get("items")
    if not isinstance(expected_items, list) or not expected_items:
        raise ValidationError("drill-pack.yaml has no items")
    expected = {
        item.get("item_id"): item
        for item in expected_items
        if isinstance(item, dict) and isinstance(item.get("item_id"), str)
    }
    if len(expected) != len(expected_items):
        raise ValidationError("drill-pack.yaml has invalid item IDs")
    sections = _response_sections(markdown)
    if set(sections) != set(expected):
        raise ValidationError("drill response file item IDs do not match drill-pack.yaml")

    # The learner may edit response field values only. Any other change would
    # make the persisted prompt ambiguous and can reintroduce an answer key or
    # stale renderer output into the immutable attempt evidence.
    skeleton_lines = []
    lines = markdown.splitlines()
    for line in lines:
        field_match = _FIELD_RE.match(line)
        if field_match:
            skeleton_lines.append(f"- {field_match.group('field')}: {_PLACEHOLDER}")
        else:
            skeleton_lines.append(line)
    if "\n".join(skeleton_lines).rstrip() != _learner_markdown(pack).rstrip():
        raise ValidationError("drill learner artifact is stale or contains non-response content")

    responses: dict[str, dict[str, str]] = {}
    prompt_lines: list[str] = []
    for line in lines:
        field_match = _FIELD_RE.match(line)
        if field_match:
            field = field_match.group("field")
            value = (field_match.group("value") or "").strip()
            if value == _PLACEHOLDER:
                value = ""
            prompt_lines.append(f"- {field}:")
        else:
            prompt_lines.append(line)

    for item_id, item in expected.items():
        body = sections[item_id]
        fields = item.get("response_fields")
        if not isinstance(fields, list) or not fields:
            raise ValidationError(f"drill item has invalid response fields: {item_id}")
        field_matches = list(_FIELD_RE.finditer(body))
        found = {match.group("field") for match in field_matches}
        if found != set(fields):
            raise ValidationError(f"drill response fields do not match drill-pack.yaml: {item_id}")
        item_responses: dict[str, str] = {}
        for match in field_matches:
            value = (match.group("value") or "").strip()
            if value == _PLACEHOLDER:
                value = ""
            if not value:
                raise ValidationError(f"drill response is incomplete: {item_id}.{match.group('field')}")
            item_responses[match.group("field")] = value
        responses[item_id] = item_responses

    response_lines = []
    for item in expected_items:
        item_id = item["item_id"]
        for field in item["response_fields"]:
            response_lines.append(f"{item_id}.{field}: {responses[item_id][field]}")
    return {
        "pack": pack,
        "prompt": "\n".join(prompt_lines).rstrip() + "\n",
        "response": "\n".join(response_lines).rstrip() + "\n",
        "responses": responses,
    }


def build_drill_pack(root: Path, recommendation: dict, *, seed: int = 0) -> dict:
    """Build a deterministic, non-scored drill pack from persisted evidence."""
    if type(seed) is not int:
        raise ValidationError("drill seed must be an integer")
    recommendation_id, source_attempt_id, task_type, codes, item_count, minimum_accuracy = _recommendation_fields(recommendation)
    _validate_codes(root, task_type, codes)
    evidence = _source_evidence(root, source_attempt_id, task_type, codes)
    identity = {
        # Bump the pack format when learner-facing prompts change. Existing
        # packs are immutable; a new format must receive a new stable ID.
        "version": _PACK_FORMAT_VERSION,
        "recommendation_id": recommendation_id,
        "source_attempt_id": source_attempt_id,
        "task_type": task_type,
        "target_codes": codes,
        "evidence_event_ids": [row["event_id"] for row in evidence],
        "seed": seed,
        "minimum_accuracy": minimum_accuracy,
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
