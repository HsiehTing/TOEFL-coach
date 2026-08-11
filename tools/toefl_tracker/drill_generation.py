"""Deterministic, evidence-linked Writing drill-pack generation."""

import hashlib
import json
import re
import shutil
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
_PACK_FORMAT_VERSION = 11
_DEFAULT_MINIMUM_ACCURACY = 0.8
_CONTEXT_TEMPLATE_FAMILIES = {
    "academic_discussion": {"academic_brand_identity"},
    "email": {
        "email_campus_facility",
        "email_career_decision_advice",
        "email_printing_problem_resolution",
    },
}


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


def _source_context(root: Path, source_attempt_id: str, task_type: str) -> dict[str, Any]:
    prompt_path = root / "tracker/writing/attempts" / source_attempt_id / "prompt.md"
    if not prompt_path.exists():
        raise ValidationError("drill pack requires the persisted source prompt for context binding")
    prompt = prompt_path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    if not prompt:
        raise ValidationError("drill pack requires a non-empty source prompt for context binding")
    lower = prompt.lower()
    if task_type == "academic_discussion":
        if "brand" in lower or "advertis" in lower or "marketing" in lower:
            summary = "brand identity, advertising updates, and customer reactions"
            template_family = "academic_brand_identity"
        else:
            raise ValidationError(
                "drill generation has no context-safe Academic Discussion template for this source prompt"
            )
    else:
        if "job opportunity" in lower or "career goal" in lower or "weigh her options" in lower:
            summary = "career options, personal priorities, and practical advice"
            template_family = "email_career_decision_advice"
        elif "printing shop" in lower or "wrong version" in lower or "printed materials" in lower:
            summary = "an incorrect printed file and an urgent correction request"
            template_family = "email_printing_problem_resolution"
        elif (
            "laboratory" in lower
            or "computer room" in lower
            or ("facility" in lower and "university" in lower)
        ):
            summary = "university facilities and student access"
            template_family = "email_campus_facility"
        else:
            raise ValidationError(
                "drill generation has no context-safe Email template for this source prompt"
            )
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return {
        "summary": summary,
        "template_family": template_family,
        "prompt_hash": "sha256:" + digest,
    }


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


def writing_drill_support_status(
    root: Path, task_type: str, code: str, source_attempt_id: str | None = None
) -> tuple[bool, str]:
    """Return whether a code and its source prompt have a safe drill renderer."""
    try:
        _validate_codes(root, task_type, [code])
        if source_attempt_id is not None:
            _source_context(root, source_attempt_id, task_type)
    except ValidationError as error:
        return False, str(error)
    return True, ""


def supports_writing_drill(
    root: Path, task_type: str, code: str, source_attempt_id: str | None = None
) -> bool:
    """Return whether an evidence-linked drill can be generated for this route."""
    return writing_drill_support_status(root, task_type, code, source_attempt_id)[0]


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
            "Rewrite this fragment as one complete sentence: `Because changing customer preferences affect business decisions.`",
            "The answer contains a main clause after the dependent `Because` clause and states a clear result.",
        ),
        (
            "combine",
            "Combine these ideas into one sentence using `because` or `therefore`: `Regular updates match current trends. More customers notice the brand.`",
            "The answer has one complete sentence and makes the cause-and-effect relationship explicit.",
        ),
        (
            "rewrite_fragment",
            "Repair this sentence boundary: `Although frequent updates require planning. They can keep a brand relevant.`",
            "The `Although` clause is attached to a complete main clause; do not leave it as a fragment.",
        ),
        (
            "produce",
            "Write one sentence beginning with `As customer preferences change, ...` and finish it with a concrete outcome.",
            "The sentence has a complete main clause after the opening `As` clause and gives a concrete outcome.",
        ),
        (
            "combine",
            "Combine these ideas into one Academic Discussion sentence with `because`: `The campaign feels current. Younger customers pay attention to the brand.`",
            "The answer has one complete sentence and makes the cause-and-effect relationship explicit.",
        ),
        (
            "rewrite_fragment",
            "Repair this fragment as one complete sentence: `Since a brand's message no longer matches current trends.`",
            "The dependent `Since` clause is attached to a complete main clause and states a clear result.",
        ),
        (
            "produce",
            "Write one sentence beginning with `If a company updates its advertising, ...` and finish it with a concrete outcome.",
            "The conditional clause is followed by a complete main clause and a concrete outcome.",
        ),
        (
            "combine",
            "Combine these ideas into one Academic Discussion sentence with `so`: `The design remains recognizable. Existing customers continue to trust the brand.`",
            "The answer has one complete sentence and makes the logical relationship explicit.",
        ),
    ],
}

_EMAIL_CLAUSE_VARIANTS = {
    "email_campus_facility": _CLAUSE_VARIANTS["email"],
    "email_career_decision_advice": [
        ("rewrite_fragment", "Rewrite this fragment as one complete advice sentence: `Because the new job may support Sarah's long-term career goals.`", "Attach the dependent clause to a complete main clause and give clear advice."),
        ("combine", "Combine these ideas using `because` or `so`: `Sarah values professional growth. She should compare the new role with her long-term goals.`", "Write one complete sentence with an explicit reason and practical advice."),
        ("rewrite_fragment", "Repair this sentence boundary: `Although the position offers a higher salary. Sarah should also consider the cost of moving.`", "Attach the `Although` clause to a complete main clause."),
        ("produce", "Write one sentence beginning with `Before Sarah accepts the new job, ...` and finish it with a specific decision-making step.", "Include a complete main clause and one concrete step."),
        ("combine", "Combine these ideas using `because`: `The new city may offer better opportunities. Sarah should research its living costs.`", "Write one complete sentence with a clear cause-and-effect relationship."),
        ("rewrite_fragment", "Repair this fragment as one complete advice sentence: `Since the decision would affect Sarah's personal priorities.`", "Attach the dependent clause to a complete main clause and give useful advice."),
        ("produce", "Write one sentence beginning with `If Sarah lists the advantages and disadvantages, ...` and finish it with a likely benefit.", "Use a complete conditional sentence and a clear outcome."),
        ("combine", "Combine these ideas using `so`: `Sarah can talk with people who know the new city. She can make a more informed decision.`", "Write one complete sentence with a logical result."),
    ],
    "email_printing_problem_resolution": [
        ("rewrite_fragment", "Rewrite this fragment as one complete request sentence: `Because the printing shop delivered the wrong version of my presentation file.`", "Attach the dependent clause to a complete main clause and state the needed action."),
        ("combine", "Combine these ideas using `because` or `so`: `My presentation is approaching. I need the correct file printed today.`", "Write one complete sentence with an urgent but professional request."),
        ("rewrite_fragment", "Repair this sentence boundary: `Although I submitted the correct file. The shop printed an older version.`", "Attach the `Although` clause to a complete main clause."),
        ("produce", "Write one sentence beginning with `Since the correct materials are needed before my presentation, ...` and finish it with a clear request.", "Include a complete main clause and an explicit requested action."),
        ("combine", "Combine these ideas using `because`: `The delivered copy is incorrect. The manager should arrange a reprint immediately.`", "Write one complete sentence with a clear cause and requested solution."),
        ("rewrite_fragment", "Repair this fragment as one complete email sentence: `If the shop can print the correct version before noon.`", "Complete the conditional clause with a clear result or request."),
        ("produce", "Write one sentence beginning with `When you receive the corrected file, ...` and finish it with a professional request.", "Include a complete main clause and a specific action."),
        ("combine", "Combine these ideas using `so`: `The wrong version cannot be used. Please confirm the reprint time.`", "Write one complete sentence with a logical result and professional tone."),
    ],
}


def _clause_item(
    number: int, task_type: str, evidence: dict, context_summary: str, template_family: str
) -> dict:
    variants = (
        _EMAIL_CLAUSE_VARIANTS[template_family]
        if task_type == "email"
        else _CLAUSE_VARIANTS[task_type]
    )
    kind, task, guidance = variants[(number - 1) % len(variants)]
    task = f"Using the source context about {context_summary}, {task[0].lower() + task[1:]}"
    return {
        "item_id": f"I{number:02d}",
        "kind": kind,
        "response_mode": "open_response",
        "prompt": task,
        "response_fields": ["response"],
        "evidence": {"attempt_id": evidence["attempt_id"], "event_id": evidence["event_id"], "code": evidence["code"]},
        "answer_guidance": guidance,
    }


def _causal_item(number: int, evidence: dict, context_summary: str) -> dict:
    prompts = [
        "Write one short sentence showing a clear claim, mechanism, concrete outcome, and link back to the position.",
        "Write one short sentence that explains how a proposed change leads to a specific outcome and supports the position.",
        "Write one short sentence that connects a claim to a customer or community reaction, then to a concrete result.",
        "Write one short sentence that acknowledges an opposing concern and explains why the position still succeeds.",
        "Write one short sentence that turns a trend or condition into a clear cause-and-effect argument.",
        "Write one short sentence that gives a concrete example and explicitly returns to the main position.",
        "Write one short sentence that explains why the proposed strategy matters over the long term.",
        "Write one short sentence that links a practical action, its effect, and the final benefit to the position.",
    ]
    return {
        "item_id": f"I{number:02d}",
        "kind": "causal_chain",
        "response_mode": "open_response",
        "prompt": f"{prompts[(number - 1) % len(prompts)]} The context is {context_summary}. Write 25–35 words in one sentence.",
        "response_fields": ["response"],
        "evidence": {"attempt_id": evidence["attempt_id"], "event_id": evidence["event_id"], "code": evidence["code"]},
        "answer_guidance": "A valid chain explains how the claim causes a concrete outcome and explicitly returns to the position.",
    }


def _focused_item(number: int, evidence: dict, *, kind: str, prompt: str, guidance: str) -> dict:
    return {
        "item_id": f"I{number:02d}", "kind": kind, "response_mode": "open_response", "prompt": prompt,
        "response_fields": ["response"],
        "evidence": {"attempt_id": evidence["attempt_id"], "event_id": evidence["event_id"], "code": evidence["code"]},
        "answer_guidance": guidance,
    }


def _normalise_prompt(value: str) -> str:
    return " ".join(value.lower().split())


def validate_drill_pack(pack: dict) -> None:
    """Reject a pack that cannot safely preserve its evidence and learner boundary."""
    if not isinstance(pack, dict):
        raise ValidationError("drill pack must be a mapping")
    required = {
        "version", "drill_id", "task_type", "target_codes", "context_summary",
        "template_family", "source_prompt_hash", "items", "learner_markdown",
        "answer_key_markdown",
    }
    if not required <= pack.keys():
        raise ValidationError("drill pack is missing required quality fields")
    if pack["version"] != _PACK_FORMAT_VERSION:
        raise ValidationError("drill pack has an incompatible quality-contract version")
    if (
        not isinstance(pack["drill_id"], str)
        or not pack["drill_id"].startswith("WD-")
        or pack["task_type"] not in {"email", "academic_discussion"}
        or not isinstance(pack["context_summary"], str)
        or not pack["context_summary"].strip()
        or not isinstance(pack["template_family"], str)
        or pack["template_family"] not in _CONTEXT_TEMPLATE_FAMILIES[pack["task_type"]]
        or not isinstance(pack["source_prompt_hash"], str)
        or not pack["source_prompt_hash"].startswith("sha256:")
    ):
        raise ValidationError("drill pack has invalid context binding")

    items = pack["items"]
    if not isinstance(items, list) or not items:
        raise ValidationError("drill pack must contain at least one item")
    item_ids: set[str] = set()
    prompts: set[str] = set()
    context = _normalise_prompt(pack["context_summary"])
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError("drill pack item must be a mapping")
        item_id = item.get("item_id")
        prompt = item.get("prompt")
        response_mode = item.get("response_mode")
        fields = item.get("response_fields")
        evidence = item.get("evidence")
        if not isinstance(item_id, str) or not item_id or item_id in item_ids:
            raise ValidationError("drill pack item IDs must be unique non-empty strings")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValidationError(f"drill pack item has an empty prompt: {item_id}")
        if response_mode not in {"open_response", "closed_response"}:
            raise ValidationError(f"drill pack item has invalid response mode: {item_id}")
        normalised_prompt = _normalise_prompt(prompt)
        if normalised_prompt in prompts:
            raise ValidationError(f"drill pack has duplicate prompts: {item_id}")
        if context not in normalised_prompt:
            raise ValidationError(f"drill pack item is not bound to its source context: {item_id}")
        if (
            not isinstance(fields, list)
            or not fields
            or any(not isinstance(field, str) or not field.strip() for field in fields)
            or len(fields) != len(set(fields))
        ):
            raise ValidationError(f"drill pack item has invalid response fields: {item_id}")
        if (
            not isinstance(evidence, dict)
            or not all(isinstance(evidence.get(field), str) and evidence[field].strip()
                       for field in {"attempt_id", "event_id", "code"})
        ):
            raise ValidationError(f"drill pack item has incomplete evidence: {item_id}")
        item_ids.add(item_id)
        prompts.add(normalised_prompt)

    learner_markdown = pack["learner_markdown"]
    answer_key_markdown = pack["answer_key_markdown"]
    if not isinstance(learner_markdown, str) or not isinstance(answer_key_markdown, str):
        raise ValidationError("drill pack artifacts must be text")
    learner_lower = learner_markdown.lower()
    if any(marker in learner_lower for marker in ("one sample answer:", "acceptable when:", "# answer key")):
        raise ValidationError("drill learner artifact leaks answer-key content")
    if learner_markdown.rstrip() != _learner_markdown(pack).rstrip():
        raise ValidationError("drill learner artifact does not match the validated pack")
    if answer_key_markdown.rstrip() != _answer_key_markdown(pack).rstrip():
        raise ValidationError("drill answer-key artifact does not match the validated pack")


def _email_specialized_templates(template_family: str) -> dict[str, tuple[list[tuple[str, str]], str]]:
    if template_family == "email_career_decision_advice":
        return {
            "GRAM-ARTICLE": ([("article_choice", prompt) for prompt in [
                "Rewrite this phrase with the correct article: `a exciting opportunity`. Then use it in one advice sentence.",
                "Rewrite this phrase with the correct article: `an new job in another city`. Then use it in one advice sentence.",
                "Rewrite this phrase with the correct article: `a informed decision`. Then use it in one advice sentence.",
                "Rewrite this phrase with the correct article: `an better work-life balance`. Then use it in one advice sentence.",
                "Rewrite this phrase with the correct article: `a useful conversation with a mentor`. Then use it in one advice sentence.",
                "Rewrite this phrase with the correct article: `an long-term career plan`. Then use it in one advice sentence.",
                "Rewrite this phrase with the correct article: `a opportunity to develop new skills`. Then use it in one advice sentence.",
                "Rewrite this phrase with the correct article: `an important personal priority`. Then use it in one advice sentence.",
            ]], "The article must match the noun phrase and the advice sentence must be complete."),
            "GRAM-AGREEMENT": ([("agreement_control", prompt) for prompt in [
                "Correct the verb and rewrite: `The new job offer several benefits.`",
                "Correct the verb and rewrite: `Sarah's personal priorities affects her decision.`",
                "Correct the verb and rewrite: `Moving costs need careful consideration.`",
                "Correct the verb and rewrite: `A list of advantages and disadvantages help Sarah compare her options.`",
                "Correct the verb and rewrite: `The opportunities in the new city seems promising.`",
                "Correct the verb and rewrite: `Her family and close friends gives useful perspectives.`",
                "Correct the verb and rewrite: `A higher salary does not always outweigh other priorities.`",
                "Correct the verb and rewrite: `The possible changes require thoughtful planning.`",
            ]], "The subject and verb must agree while preserving practical career advice."),
            "LEX-WORDFORM": ([("word_form", prompt) for prompt in [
                "Choose the correct form and rewrite: `Sarah should consider the advantages and disadvantage carefully.`",
                "Choose the correct form and rewrite: `The new role could be a value opportunity.`",
                "Choose the correct form and rewrite: `She needs more clear before making a decision.`",
                "Choose the correct form and rewrite: `Moving may have a significant affect on her routine.`",
                "Choose the correct form and rewrite: `A mentor can provide help advice.`",
                "Choose the correct form and rewrite: `Sarah should decide thoughtful rather than quickly.`",
                "Choose the correct form and rewrite: `The offer may improve her professional develop.`",
                "Choose the correct form and rewrite: `Her choice should reflect her personal prefer.`",
            ]], "Choose a grammatically correct word form while keeping the advice meaningful."),
            "LEX-COLLOCATION": ([("collocation", prompt) for prompt in [
                "Rewrite naturally: `Sarah should do a decision after comparing her options.`",
                "Rewrite naturally: `The new role can give a positive influence on her career.`",
                "Rewrite naturally: `She should take a research about living costs.`",
                "Rewrite naturally: `Sarah can make a balance between salary and personal priorities.`",
                "Rewrite naturally: `Her mentor can give her a useful suggestion about the offer.`",
                "Rewrite naturally: `The move may bring a big change to her daily life.`",
                "Rewrite naturally: `She should pay attention on the long-term opportunities.`",
                "Rewrite naturally: `Sarah needs to make a careful choice between both jobs.`",
            ]], "Use a natural English collocation in a clear advice sentence."),
            "EMAIL-ACTION": ([("email_action", prompt) for prompt in [
                "Write one supportive email sentence advising Sarah to compare the new role with her long-term goals.",
                "Write one supportive email sentence advising Sarah to research housing and living costs before moving.",
                "Write one supportive email sentence advising Sarah to speak with a mentor before deciding.",
                "Write one supportive email sentence encouraging Sarah to list the advantages and disadvantages.",
                "Write one supportive email sentence encouraging Sarah to consider her personal priorities.",
                "Write one supportive email sentence advising Sarah to ask about growth opportunities in the new role.",
                "Write one supportive email sentence encouraging Sarah to give herself enough time to decide.",
                "Write one supportive email sentence advising Sarah to consider how the move would affect her support network.",
            ]], "The advice, its recipient, and a practical action must be explicit."),
        }
    if template_family == "email_printing_problem_resolution":
        return {
            "GRAM-ARTICLE": ([("article_choice", prompt) for prompt in [
                "Rewrite this phrase with the correct article: `a urgent reprint`. Then use it in one request sentence.",
                "Rewrite this phrase with the correct article: `an incorrect file version`. Then use it in one request sentence.",
                "Rewrite this phrase with the correct article: `a important class presentation`. Then use it in one request sentence.",
                "Rewrite this phrase with the correct article: `an updated document`. Then use it in one request sentence.",
                "Rewrite this phrase with the correct article: `a immediate solution`. Then use it in one request sentence.",
                "Rewrite this phrase with the correct article: `an earlier file`. Then use it in one request sentence.",
                "Rewrite this phrase with the correct article: `a clear confirmation`. Then use it in one request sentence.",
                "Rewrite this phrase with the correct article: `an urgent printing request`. Then use it in one request sentence.",
            ]], "The article must match the noun phrase and the request sentence must be complete."),
            "GRAM-AGREEMENT": ([("agreement_control", prompt) for prompt in [
                "Correct the verb and rewrite: `The delivered materials does not match my submitted file.`",
                "Correct the verb and rewrite: `The incorrect copies needs to be replaced today.`",
                "Correct the verb and rewrite: `My presentation require the correct printed version.`",
                "Correct the verb and rewrite: `The manager and staff is responsible for checking the file.`",
                "Correct the verb and rewrite: `The correct materials has to be ready before class.`",
                "Correct the verb and rewrite: `The printing shop need to confirm the reprint time.`",
                "Correct the verb and rewrite: `These pages contains an older version of my work.`",
                "Correct the verb and rewrite: `A prompt solution help me prepare for the presentation.`",
            ]], "The subject and verb must agree while preserving the printing-correction request."),
            "LEX-WORDFORM": ([("word_form", prompt) for prompt in [
                "Choose the correct form and rewrite: `The delivered copy was print incorrectly.`",
                "Choose the correct form and rewrite: `I need the file to be print again.`",
                "Choose the correct form and rewrite: `Please provide a quickly solution.`",
                "Choose the correct form and rewrite: `The mistake may affect my presentation prepare.`",
                "Choose the correct form and rewrite: `I would appreciate your immediate respond.`",
                "Choose the correct form and rewrite: `The manager should confirm the reprint is possible.`",
                "Choose the correct form and rewrite: `The delivered version is differ from my original file.`",
                "Choose the correct form and rewrite: `A prompt correction is necessary because of the presentation's important.`",
            ]], "Choose a grammatically correct word form while keeping the request clear and professional."),
            "LEX-COLLOCATION": ([("collocation", prompt) for prompt in [
                "Rewrite naturally: `The shop printed a wrong version of my file.`",
                "Rewrite naturally: `Please make a reprint of the correct document.`",
                "Rewrite naturally: `I hope you can give me a quick solution for this mistake.`",
                "Rewrite naturally: `The error can make an effect on my presentation.`",
                "Rewrite naturally: `Please confirm me the time for the corrected copies.`",
                "Rewrite naturally: `I need to solve this problem as soon as possible.`",
                "Rewrite naturally: `The printed pages are different with the file I submitted.`",
                "Rewrite naturally: `The manager should take an action to fix the error.`",
            ]], "Use a natural English collocation in a polite, urgent request."),
            "EMAIL-ACTION": ([("email_action", prompt) for prompt in [
                "Write one professional email sentence asking the manager to reprint the correct file immediately.",
                "Write one professional email sentence asking the manager to confirm when the corrected copies will be ready.",
                "Write one professional email sentence asking the manager to check the attached file before printing it again.",
                "Write one professional email sentence asking the manager to replace the incorrect materials before the presentation.",
                "Write one professional email sentence asking the manager to explain how the printing error will be corrected.",
                "Write one professional email sentence asking the manager to prioritize the reprint because the presentation is soon.",
                "Write one professional email sentence asking the manager to notify you as soon as the correct copies are available.",
                "Write one professional email sentence asking the manager to ensure that the revised file, not the older version, is printed.",
            ]], "The recipient, requested correction, and urgency must be explicit."),
        }
    raise ValidationError("drill generation has no context-safe specialized template")


def _specialized_item(
    number: int, evidence: dict, context_summary: str, task_type: str, template_family: str
) -> dict:
    code = evidence["code"]
    templates = {
        "GRAM-ARTICLE": (
            [
                ("article_choice", "Rewrite this noun phrase with the correct article: `a AI laboratory`. Then use it in one complete email sentence."),
                ("article_choice", "Rewrite this noun phrase with the correct article: `an new campus facility`. Then use it in one complete email sentence."),
                ("article_choice", "Rewrite this phrase with the correct article: `an university policy`. Then use it in one complete sentence."),
                ("article_choice", "Rewrite this phrase with the correct article: `the additional laboratory`. Then use it in one complete sentence."),
                ("article_choice", "Rewrite this noun phrase with the correct article: `a accessible study space`. Then use it in one complete email sentence."),
                ("article_choice", "Rewrite this noun phrase with the correct article: `an improved computer room`. Then use it in one complete email sentence."),
                ("article_choice", "Rewrite this noun phrase with the correct article: `a evening study area`. Then use it in one complete email sentence."),
                ("article_choice", "Rewrite this noun phrase with the correct article: `an important facility proposal`. Then use it in one complete email sentence."),
            ],
            "The article must match the noun phrase and the full sentence must be complete.",
        ),
        "GRAM-AGREEMENT": (
            [
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `New facilities could benefits both faculty and students.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `The proposal encourage students to participate.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `The new laboratory provide more computer access.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `Extended library hours helps students study after class.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `A campus facility with modern equipment serve several departments.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `These improvements gives students more learning options.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `The student council support a practical facility proposal.`"),
                ("agreement_control", "Correct the verb in this sentence and rewrite it: `Additional study spaces makes the campus more accessible.`"),
            ],
            "The modal `could` is followed by the base verb `benefit`.",
        ),
        "LEX-WORDFORM": (
            [
                ("word_form", "Choose the correct form and rewrite the sentence: `The university should consider my propose.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `The facility would be benefit for many students.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `Students need more accessibly study spaces.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `The council should support the improve of campus services.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `The university should make the laboratory more afford for students.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `The proposal would provide a practical learn environment.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `Modern equipment would increase the facility's effect.`"),
                ("word_form", "Choose the correct form and rewrite the sentence: `The new service would improve student satisfy.`"),
            ],
            "The noun `proposal` is the object of `consider`.",
        ),
        "LEX-COLLOCATION": (
            [
                ("collocation", "Rewrite this sentence using natural English: `The laboratory can teach students practical using skills.`"),
                ("collocation", "Rewrite this sentence using natural English: `The facility gives a positive influence to student learning.`"),
                ("collocation", "Rewrite this sentence using natural English: `The university should do a decision about the proposal.`"),
                ("collocation", "Rewrite this sentence using natural English: `The new space can catch students' eyes.`"),
                ("collocation", "Rewrite this sentence using natural English: `The laboratory can make an effect on study habits.`"),
                ("collocation", "Rewrite this sentence using natural English: `Students are easy to be supported by the new service.`"),
                ("collocation", "Rewrite this sentence using natural English: `The university should keep its facility quality.`"),
                ("collocation", "Rewrite this sentence using natural English: `The proposal can let students improve their skills.`"),
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
    if task_type == "email" and template_family != "email_campus_facility":
        templates = _email_specialized_templates(template_family)
    variants, guidance = templates[code]
    if task_type == "academic_discussion":
        academic_templates = {
            "GRAM-ARTICLE": [
                ("article_choice", f"Using the source context about {context_summary}, rewrite this phrase with the correct article: `a effective campaign`."),
                ("article_choice", f"Using the source context about {context_summary}, rewrite this phrase with the correct article: `an consistent message`."),
                ("article_choice", f"Using the source context about {context_summary}, rewrite this phrase with the correct article: `a updated design`."),
                ("article_choice", f"Using the source context about {context_summary}, rewrite this phrase with the correct article: `an younger audience`."),
            ],
            "GRAM-AGREEMENT": [
                ("agreement_control", f"Using the source context about {context_summary}, correct the verb: `Regular updates keeps a brand relevant.`"),
                ("agreement_control", f"Using the source context about {context_summary}, correct the verb: `A clear logo help customers remember a brand.`"),
                ("agreement_control", f"Using the source context about {context_summary}, correct the verb: `Younger customers prefers current designs.`"),
                ("agreement_control", f"Using the source context about {context_summary}, correct the verb: `These campaigns attracts new buyers.`"),
                ("agreement_control", f"Using the source context about {context_summary}, correct the verb: `A modern message appeal to new audiences.`"),
                ("agreement_control", f"Using the source context about {context_summary}, correct the verb: `Brand colors and slogans builds recognition.`"),
                ("agreement_control", f"Using the source context about {context_summary}, correct the verb: `The updated packages increases attention.`"),
                ("agreement_control", f"Using the source context about {context_summary}, correct the verb: `Regular changes keeps customers interested.`"),
            ],
            "LEX-COLLOCATION": [
                ("collocation", f"Using the source context about {context_summary}, rewrite naturally: `The campaign gives a positive influence to customers.`"),
                ("collocation", f"Using the source context about {context_summary}, rewrite naturally: `The brand should keep its image consistency.`"),
                ("collocation", f"Using the source context about {context_summary}, rewrite naturally: `The design can catch customers' eyes.`"),
                ("collocation", f"Using the source context about {context_summary}, rewrite naturally: `The update can let customers remember the product.`"),
                ("collocation", f"Using the source context about {context_summary}, rewrite naturally: `The campaign can make an effect on sales.`"),
                ("collocation", f"Using the source context about {context_summary}, rewrite naturally: `Customers are easy to be attracted by the package.`"),
                ("collocation", f"Using the source context about {context_summary}, rewrite naturally: `The company should do a decision about its message.`"),
                ("collocation", f"Using the source context about {context_summary}, rewrite naturally: `The new image makes a strong impression to buyers.`"),
            ],
            "LEX-WORDFORM": [
                ("word_form", f"Using the source context about {context_summary}, choose the correct form: `The campaign was success among younger customers.`"),
                ("word_form", f"Using the source context about {context_summary}, choose the correct form: `Regular updates can create a strong impress.`"),
                ("word_form", f"Using the source context about {context_summary}, choose the correct form: `The company wants to regular its advertising.`"),
                ("word_form", f"Using the source context about {context_summary}, choose the correct form: `The design is easily recognize by customers.`"),
            ],
        }
        if code in academic_templates:
            variants = academic_templates[code]
            guidance = "The correction must preserve the source context and satisfy the target grammar or collocation condition."
    kind, prompt = variants[(number - 1) % len(variants)]
    if task_type == "email":
        prompt = f"Using the source context about {context_summary}, {prompt[0].lower() + prompt[1:]}"
        guidance = f"{guidance} Keep the response within the source context."
    return _focused_item(number, evidence, kind=kind, prompt=prompt, guidance=guidance)


def _learner_markdown(pack: dict) -> str:
    lines = [f"# Writing Targeted Drill `{pack['drill_id']}`", "", f"Route: `{pack['task_type']}`", f"Context: `{pack['context_summary']}`", "", "Write your own answers. The answer key is intentionally separate.", ""]
    for item in pack["items"]:
        lines.extend([f"## {item['item_id']}", item["prompt"], ""])
        for field in item["response_fields"]:
            lines.append(f"- {field}: [write your answer here]")
        lines.append("")
    return "\n".join(lines)


def _sample_answer(item: dict, context_summary: str, template_family: str) -> str:
    kind = item["kind"]
    is_brand_context = "brand" in context_summary.lower()
    if template_family == "email_career_decision_advice":
        samples = {
            "rewrite_fragment": "Because the new job could support Sarah's goals, she should compare its benefits with her personal priorities.",
            "combine": "Sarah should research living costs because the new city may offer better career opportunities.",
            "produce": "Before Sarah accepts the new job, she should discuss the decision with a mentor she trusts.",
            "article_choice": "Sarah should view the offer as an important career opportunity.",
            "agreement_control": "Sarah's personal priorities affect her decision.",
            "word_form": "Sarah should consider the advantages and disadvantages carefully.",
            "collocation": "Sarah should make a decision after comparing her options.",
            "email_action": "Sarah, please compare the new role with your long-term goals before deciding.",
        }
        return samples.get(kind, "A response that gives clear, practical career advice is acceptable.")
    if template_family == "email_printing_problem_resolution":
        samples = {
            "rewrite_fragment": "Because the shop printed the wrong file version, please arrange an urgent reprint of the correct document.",
            "combine": "Because my presentation is approaching, I need the correct file printed today.",
            "produce": "Since the materials are needed before my presentation, please confirm the reprint time today.",
            "article_choice": "Please arrange an urgent reprint of the correct file.",
            "agreement_control": "The incorrect copies need to be replaced today.",
            "word_form": "I would appreciate your immediate response.",
            "collocation": "Please reprint the correct version of my file.",
            "email_action": "Please reprint the correct file immediately and confirm when it will be ready.",
        }
        return samples.get(kind, "A polite, urgent request that identifies the correction is acceptable.")
    if kind in {"rewrite_fragment", "combine", "produce"}:
        return (
            "Because customer preferences change, companies should update their advertising to keep the brand relevant."
            if is_brand_context
            else "Because students need practical AI training, the university should add another laboratory."
        )
    if kind == "causal_chain":
        return (
            "Regular updates keep a brand relevant to younger customers, increase their interest in its products, encourage purchases, and support long-term business growth."
            if is_brand_context
            else "The proposed change meets students' needs, improves their access to resources, and therefore supports the university's long-term goals."
        )
    samples = (
        {
            "article_choice": "The company launched an effective campaign for younger customers.",
            "agreement_control": "Regular updates keep a brand relevant to customers.",
            "word_form": "The campaign was successful among younger customers.",
            "collocation": "The campaign has a positive effect on customers' purchase decisions.",
        }
        if is_brand_context
        else {
            "article_choice": "The university should add an AI laboratory for students.",
            "agreement_control": "The new laboratory provides more computer access.",
            "word_form": "The facility would be beneficial for many students.",
            "collocation": "The laboratory helps students develop practical skills.",
        }
    )
    samples["email_action"] = "Ms. Lee, please support the proposal and present it to the university administration."
    return samples.get(kind, "A response that meets every stated grammar and meaning condition is acceptable.")


def _answer_key_markdown(pack: dict) -> str:
    lines = [f"# Answer key — `{pack['drill_id']}`", "", "Use after completing the learner drill. The sample is not the only acceptable answer.", ""]
    for item in pack["items"]:
        lines.extend([
            f"## {item['item_id']}",
            f"One sample answer: {_sample_answer(item, pack['context_summary'], pack['template_family'])}",
            f"Acceptable when: {item['answer_guidance']}",
            "",
        ])
    return "\n".join(lines)


def _assessment_template(pack: dict) -> str:
    rows = [
        {
            "item_id": item["item_id"],
            "status": "",
            "reason": "",
        }
        for item in pack["items"]
    ]
    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


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


def _sentence_count(response: str) -> int:
    return len(re.findall(r"[.!?]+(?=\s|$)", response.strip()))


def _word_count(response: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)?", response))


def build_assessment_hints(completed: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic format checks; a coach still judges meaning and accuracy."""
    if not isinstance(completed, dict) or not isinstance(completed.get("pack"), dict):
        raise ValidationError("assessment hints require a completed generated drill")
    pack = completed["pack"]
    responses = completed.get("responses")
    if not isinstance(responses, dict):
        raise ValidationError("assessment hints require parsed learner responses")
    items: list[dict[str, Any]] = []
    for item in pack.get("items", []):
        if not isinstance(item, dict) or not isinstance(item.get("item_id"), str):
            raise ValidationError("assessment hints require valid drill items")
        item_id = item["item_id"]
        item_responses = responses.get(item_id)
        if not isinstance(item_responses, dict):
            raise ValidationError(f"assessment hints are missing responses for {item_id}")
        fields: list[dict[str, Any]] = []
        for field in item.get("response_fields", []):
            response = item_responses.get(field)
            if not isinstance(response, str) or not response.strip():
                raise ValidationError(f"assessment hints require a response for {item_id}.{field}")
            word_count = _word_count(response)
            sentence_count = _sentence_count(response)
            checks = [
                {
                    "check": "sentence_ending",
                    "status": "pass" if sentence_count else "attention",
                    "detail": "A sentence-ending punctuation mark was found."
                    if sentence_count else "No sentence-ending punctuation mark was found.",
                }
            ]
            if item.get("kind") == "causal_chain":
                checks.extend([
                    {
                        "check": "one_sentence",
                        "status": "pass" if sentence_count == 1 else "attention",
                        "detail": f"Detected {sentence_count} sentence endings; the item asks for one sentence.",
                    },
                    {
                        "check": "word_range_25_35",
                        "status": "pass" if 25 <= word_count <= 35 else "attention",
                        "detail": f"Detected {word_count} words; the item asks for 25–35 words.",
                    },
                ])
            fields.append(
                {
                    "field": field,
                    "word_count": word_count,
                    "sentence_count": sentence_count,
                    "checks": checks,
                }
            )
        items.append(
            {
                "item_id": item_id,
                "response_mode": item["response_mode"],
                "fields": fields,
            }
        )
    return {
        "version": 1,
        "drill_id": pack.get("drill_id"),
        "review_mode": "diagnostic_only",
        "scoring_authority": "coach_required",
        "items": items,
    }


def write_assessment_hints(pack_dir: Path) -> Path:
    """Write a disposable, diagnostic-only coach aid beside the unfinished drill."""
    completed = read_completed_drill(pack_dir)
    path = pack_dir / "assessment-hints.json"
    atomic_write_text(path, json.dumps(build_assessment_hints(completed), ensure_ascii=False, indent=2) + "\n")
    return path


def _assessment_review_markdown(completed: dict[str, Any], hints: dict[str, Any]) -> str:
    """Render a temporary coach worksheet without assigning an automatic score."""
    pack = completed["pack"]
    responses = completed["responses"]
    hints_by_item = {
        row["item_id"]: row
        for row in hints["items"]
        if isinstance(row, dict) and isinstance(row.get("item_id"), str)
    }
    lines = [
        f"# Coach assessment worksheet — `{pack['drill_id']}`",
        "",
        "Use this temporary worksheet to decide the entries in `assessment.json`. "
        "It is not an automatic score: the coach must judge meaning, grammar, and whether the response meets the stated condition.",
        "",
        f"Route: `{pack['task_type']}`",
        f"Context: {pack['context_summary']}",
        "",
        "For each item, choose exactly one status in `assessment.json`: `meets_target`, "
        "`partially_meets_target`, or `needs_revision`. In `reason`, cite the learner response and explain the decision; do not mark an answer wrong merely because it differs from a sample answer.",
        "",
    ]
    for item in pack["items"]:
        item_id = item["item_id"]
        hint_fields = hints_by_item[item_id]["fields"]
        lines.extend([
            f"## {item_id}",
            f"- Target code: `{item['evidence']['code']}`",
            f"- Source evidence: `{item['evidence']['event_id']}` from `{item['evidence']['attempt_id']}`",
            f"- Prompt: {item['prompt']}",
            f"- Acceptable when: {item['answer_guidance']}",
            "- Learner response:",
        ])
        for field in item["response_fields"]:
            lines.append(f"  - {field}: {responses[item_id][field]}")
        lines.append("- Format checks (diagnostic only):")
        for field_hint in hint_fields:
            checks = "; ".join(
                f"{check['check']} = {check['status']} ({check['detail']})"
                for check in field_hint["checks"]
            )
            lines.append(
                f"  - {field_hint['field']}: {field_hint['word_count']} words; "
                f"{field_hint['sentence_count']} sentence endings; {checks}"
            )
        lines.extend([
            "- Coach decision: [complete `assessment.json`; do not score in this worksheet]",
            "",
        ])
    return "\n".join(lines)


def write_assessment_review(pack_dir: Path) -> Path:
    """Write a disposable semantic-review worksheet beside an unfinished drill."""
    completed = read_completed_drill(pack_dir)
    hints = build_assessment_hints(completed)
    path = pack_dir / "assessment-review.md"
    atomic_write_text(path, _assessment_review_markdown(completed, hints).rstrip() + "\n")
    return path


def build_drill_pack(root: Path, recommendation: dict, *, seed: int = 0) -> dict:
    """Build a deterministic, non-scored drill pack from persisted evidence."""
    if type(seed) is not int:
        raise ValidationError("drill seed must be an integer")
    recommendation_id, source_attempt_id, task_type, codes, item_count, minimum_accuracy = _recommendation_fields(recommendation)
    _validate_codes(root, task_type, codes)
    if item_count < len(codes):
        raise ValidationError("drill item_count must provide at least one item for every target code")
    evidence = _source_evidence(root, source_attempt_id, task_type, codes)
    context = _source_context(root, source_attempt_id, task_type)
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
        "context_summary": context["summary"],
        "template_family": context["template_family"],
        "source_prompt_hash": context["prompt_hash"],
    }
    drill_id = "WD-" + _canonical_hash(identity)[:16].upper()
    evidence_by_code = {
        code: [row for row in evidence if row["code"] == code]
        for code in codes
    }
    items: list[dict] = []
    for number in range(1, item_count + 1):
        code = codes[(seed + number - 1) % len(codes)]
        code_rows = evidence_by_code[code]
        row = code_rows[(seed + (number - 1) // len(codes)) % len(code_rows)]
        if row["code"] == "GRAM-CLAUSE":
            items.append(_clause_item(number, task_type, row, context["summary"], context["template_family"]))
        elif row["code"] in _CAUSAL_CODES:
            items.append(_causal_item(number, row, context["summary"]))
        else:
            items.append(_specialized_item(
                number, row, context["summary"], task_type, context["template_family"]
            ))
    pack = {
        **identity,
        "drill_id": drill_id,
        "items": items,
    }
    pack["learner_markdown"] = _learner_markdown(pack)
    pack["answer_key_markdown"] = _answer_key_markdown(pack)
    validate_drill_pack(pack)
    return pack


def write_drill_pack(root: Path, pack: dict) -> Path:
    """Persist a generated pack once; a differing pack with the same ID is rejected."""
    validate_drill_pack(pack)
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
            assessment_path = destination / "assessment.json"
            if not assessment_path.exists():
                atomic_write_text(assessment_path, _assessment_template(pack))
            return destination
        raise ValidationError("refusing to overwrite an immutable drill pack")
    for name, content in expected.items():
        atomic_write_text(destination / name, content)
    atomic_write_text(destination / "assessment.json", _assessment_template(pack))
    return destination


def attach_generated_drill_lineage(attempt: dict, pack: dict) -> None:
    """Copy the minimum transfer contract from a completed pack into its attempt."""
    required = {
        "version", "drill_id", "recommendation_id", "source_attempt_id", "task_type",
        "target_codes", "minimum_accuracy", "source_prompt_hash", "items",
    }
    if (
        not isinstance(pack, dict)
        or not required <= set(pack)
        or pack.get("version") != _PACK_FORMAT_VERSION
        or not isinstance(pack.get("items"), list)
        or not isinstance(pack.get("target_codes"), list)
    ):
        raise ValidationError("generated drill pack has invalid transfer lineage")
    drill = attempt.setdefault("drill", {})
    if not isinstance(drill, dict):
        raise ValidationError("targeted drill requires drill metadata")
    expected_lineage = {
        "source_attempt_ids": [pack["source_attempt_id"]],
        "target_codes": pack["target_codes"],
        "item_count": len(pack["items"]),
    }
    for field, expected in expected_lineage.items():
        if drill.get(field) != expected:
            raise ValidationError(f"targeted drill {field} does not match the generated pack")
    drill.update(
        {
            "drill_pack_id": pack["drill_id"],
            "recommendation_id": pack["recommendation_id"],
            "minimum_accuracy": pack["minimum_accuracy"],
            "source_prompt_hash": pack["source_prompt_hash"],
            "pack_version": pack["version"],
            "artifact_retention": "result_only",
        }
    )


def summarize_item_results_by_code(pack: dict, item_results: list[dict]) -> list[dict]:
    """Create the per-code performance record needed after a one-time pack is removed."""
    items = pack.get("items") if isinstance(pack, dict) else None
    target_codes = pack.get("target_codes") if isinstance(pack, dict) else None
    if not isinstance(items, list) or not isinstance(target_codes, list):
        raise ValidationError("generated drill pack has invalid item-code lineage")
    code_by_item: dict[str, str] = {}
    for item in items:
        evidence = item.get("evidence") if isinstance(item, dict) else None
        item_id = item.get("item_id") if isinstance(item, dict) else None
        code = evidence.get("code") if isinstance(evidence, dict) else None
        if not isinstance(item_id, str) or not isinstance(code, str) or code not in target_codes:
            raise ValidationError("generated drill item has invalid code lineage")
        code_by_item[item_id] = code
    if not isinstance(item_results, list) or {row.get("item_id") for row in item_results if isinstance(row, dict)} != set(code_by_item):
        raise ValidationError("item results do not cover the generated drill")
    summaries = {
        code: {"code": code, "item_count": 0, "correct_count": 0, "partial_count": 0}
        for code in target_codes
    }
    for row in item_results:
        item_id = row.get("item_id") if isinstance(row, dict) else None
        if (
            not isinstance(row, dict)
            or not isinstance(item_id, str)
            or item_id not in code_by_item
            or row.get("status") not in {
            "meets_target", "partially_meets_target", "needs_revision",
            }
        ):
            raise ValidationError("item results have invalid assessment statuses")
        summary = summaries[code_by_item[item_id]]
        summary["item_count"] += 1
        summary["correct_count"] += row["status"] == "meets_target"
        summary["partial_count"] += row["status"] == "partially_meets_target"
    if any(summary["item_count"] == 0 for summary in summaries.values()):
        raise ValidationError("generated drill does not assess every target code")
    return [summaries[code] for code in target_codes]


def retire_registered_drill_pack(root: Path, pack: dict) -> None:
    """Remove one completed, generated drill after its durable result is registered."""
    drill_id = pack.get("drill_id")
    if not isinstance(drill_id, str) or not drill_id.startswith("WD-"):
        raise ValidationError("drill pack requires a stable drill_id before retirement")
    destination = root / "tracker/writing/drill-packs" / drill_id
    if not destination.is_dir():
        raise ValidationError("generated drill pack is unavailable for retirement")
    shutil.rmtree(destination)


def retire_registered_drill_attempt_content(root: Path, attempt_id: str) -> None:
    """Remove one-time learner prompt and response after successful registration."""
    if not isinstance(attempt_id, str) or not attempt_id.strip():
        raise ValidationError("targeted drill requires an attempt ID before content retirement")
    destination = root / "tracker/writing/attempts" / attempt_id
    attempt_path = destination / "attempt.yaml"
    if not attempt_path.exists():
        raise ValidationError("registered targeted drill is unavailable for content retirement")
    attempt = read_yaml(attempt_path)
    retention = attempt.get("drill", {}).get("artifact_retention") if isinstance(attempt.get("drill"), dict) else None
    if attempt.get("record_type") != "targeted_drill" or retention != "result_only":
        raise ValidationError("only a result-only targeted drill may retire its content")
    for name in ("prompt.md", "response-original.md"):
        path = destination / name
        if path.exists():
            path.unlink()
