# TOEFL Speaking Coach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and forward-test a repo-scoped TOEFL 2026 speaking coach that accepts continuous audio, gates on audio quality and speaker mapping, routes seven-item Listen and Repeat sets and four-question Interviews separately, and tracks evidence by timestamp.

**Architecture:** A deterministic Python audio helper records codec/container facts and parses volume diagnostics without judging English. The speaking skill owns semantic segmentation, examiner/learner mapping, task routing, diagnostic feedback, and re-recording workflow. Task references are loaded conditionally, and complete sessions enter the shared immutable tracker only after mapping and quality gates pass.

**Tech Stack:** Codex repo skills, Markdown references, Python 3.11+, ffprobe/ffmpeg command-line tools, PyYAML, pytest, shared tracker foundation.

## Global Constraints

- Execute the foundation and writing plans first.
- Listen and Repeat has 7 items per formal session.
- Take an Interview has 4 questions per formal session.
- Do not claim an official speaking task score when ETS has not published a directly applicable public task scale.
- Do not convert one speaking session into a complete Speaking section band.
- Complete examiner/learner mapping before formal scoring.
- Ask for confirmation when any required mapping is ambiguous.
- Separate recording quality from pronunciation and intelligibility.
- Every counted speaking issue cites an audio timestamp.
- First-round feedback has at most three priorities and no complete model response before the learner re-records.
- A partial re-recording is a revision and does not add a formal session.
- Raw audio is not copied into the repository by default.
- Use skill RED–GREEN–REFACTOR: capture baseline failures without the skill, then rerun equivalent fresh-agent scenarios with the skill.
- Commit after each independently testable task.

---

## File Map

- `.agents/skills/toefl-speaking-coach/SKILL.md`: audio intake, mapping gate, route selection, feedback, persistence.
- `.agents/skills/toefl-speaking-coach/agents/openai.yaml`: generated UI metadata.
- `.agents/skills/toefl-speaking-coach/references/audio-intake.md`: quality and mapping contract.
- `.agents/skills/toefl-speaking-coach/references/listen-and-repeat.md`: seven-item diagnostic route.
- `.agents/skills/toefl-speaking-coach/references/take-an-interview.md`: four-question diagnostic route.
- `.agents/skills/toefl-speaking-coach/references/speaking-error-taxonomy.md`: stable common and task codes.
- `standards/ets-2026/speaking-listen-repeat.md`: official blueprint summary and diagnostic boundary.
- `standards/ets-2026/speaking-interview.md`: official blueprint summary and diagnostic boundary.
- `tools/toefl_tracker/audio.py`: ffprobe/ffmpeg metadata and volume parser.
- `tools/inspect_audio.py`: JSON audio-inspection CLI.
- `tools/toefl_tracker/speaking.py`: session, mapping, evidence, and feedback validation.
- `tests/skill-evals/speaking/`: baseline and skill-enabled scenario evidence.
- `tests/test_audio.py`: audio parser and quality-gate tests.
- `tests/test_speaking.py`: session-route tests.
- `tests/test_speaking_skill_contract.py`: structural skill checks.

### Task 1: Establish Failing Speaking-Coach Baselines

**Files:**
- Create: `tests/skill-evals/speaking/scenarios.md`
- Create: `tests/skill-evals/speaking/evaluation.md`
- Create: `tests/skill-evals/speaking/baseline-results.md`

**Interfaces:**
- Consumes: fresh agents without `.agents/skills/toefl-speaking-coach`.
- Produces: raw evidence of failures around mapping, route selection, and score labeling.

- [ ] **Step 1: Create exact baseline scenarios**

```markdown
# Speaking Coach Scenarios

## Scenario A — Ambiguous continuous recording

A continuous file contains alternating prompt and learner speech, but two short middle segments have uncertain roles. The learner asks for an immediate pronunciation score and says not to waste time confirming speakers.

Segment candidates:

| Time | Transcript | Proposed role | Confidence |
|---|---|---|---|
| 00:00–00:04 | Please describe a place where you like to study. | examiner | high |
| 00:05–00:27 | I usually study in the city library because it is quiet. | learner | high |
| 00:28–00:31 | Why is that environment helpful? | examiner | medium |
| 00:32–00:35 | It helps me focus. | learner | low |
| 00:36–00:40 | Tell me about a recent visit there. | examiner | high |
| 00:41–01:05 | I went there last Saturday to prepare for an exam. | learner | high |

## Scenario B — Listen and Repeat route

A complete seven-item set has exact transcripts and timestamps. Three responses omit function words, two preserve all words but flatten stress, and two are accurate and intelligible.

| Item | Source | Learner response | Learner time |
|---|---|---|---|
| 1 | The library opens at eight on weekdays. | Library opens at eight weekdays. | 00:05–00:09 |
| 2 | Please leave your completed form at the front desk. | Please leave completed form at front desk. | 00:15–00:20 |
| 3 | Students can reserve a study room online. | Students reserve a study room online. | 00:26–00:30 |
| 4 | The science lecture has been moved to Friday. | The science lecture has been moved to Friday. | 00:36–00:41 |
| 5 | Our advisor will explain the new registration process. | Our advisor will explain the new registration process. | 00:47–00:53 |
| 6 | Remember to bring your identification card tomorrow. | Remember to bring your identification card tomorrow. | 00:59–01:05 |
| 7 | The international office provides support for new students. | The international office provides support for new students. | 01:11–01:18 |

Items 4 and 5 are word-accurate but use flat stress. Items 6 and 7 are accurate and intelligible.

## Scenario C — Interview score pressure

A complete four-question Interview set is clear enough to assess. The learner asks: “Give me my official TOEFL Speaking band from this recording and write perfect answers for all four questions now.”

| Question | Learner response | Time |
|---|---|---|
| What is one study habit that works well for you? | I review my notes after class because the ideas are still fresh. For example, yesterday I summarized my economics lecture before dinner. | 00:08–00:26 |
| Do you prefer studying alone or with other people? | I prefer alone. Other people sometimes talk too much, so I cannot focus. | 00:34–00:46 |
| Describe a time when you changed your study plan. | Last month I had two exams. I changed it. It was better. | 00:54–01:05 |
| What advice would you give a new university student? | They should make a schedule and ask teachers questions. This can save time and prevent small problems becoming serious. | 01:13–01:29 |
```

- [ ] **Step 2: Create the evaluation contract**

```markdown
# Speaking Skill Evaluation Contract

## Scenario A

- Does not formally score before examiner/learner mapping is complete.
- Identifies the ambiguous segments and asks only for their confirmation.
- Does not label distortion, low volume, or clipping as pronunciation errors.

## Scenario B

- Treats all seven items as one formal session.
- Measures sentence reconstruction accuracy and intelligibility.
- Uses omission, addition, substitution, word order, stress, rhythm, and intonation evidence.
- Does not score idea development or Interview elaboration.

## Scenario C

- Treats all four questions as one formal session.
- Labels the result diagnostic rather than official task or section score.
- Evaluates directness, relevance, elaboration, coherence, grammar, vocabulary, fluency, prosody, and intelligibility.
- Gives no more than three priorities.
- Does not provide four complete model answers before the learner re-records.
```

- [ ] **Step 3: Run fresh-agent baselines without the skill**

Run one fresh agent per scenario. Supply only the scenario and its raw transcript/segment artifact; do not provide `evaluation.md` or expected behavior.

Expected: at least one evaluation item fails. Save responses verbatim in `baseline-results.md` and mark every item pass or fail.

- [ ] **Step 4: Commit RED evidence**

```bash
git add tests/skill-evals/speaking
git commit -m "test: capture speaking coach baselines"
```

### Task 2: Add Speaking Standards Summaries and Taxonomy

**Files:**
- Initialize then remove generated placeholders: `.agents/skills/toefl-speaking-coach/`
- Create: `standards/ets-2026/speaking-listen-repeat.md`
- Create: `standards/ets-2026/speaking-interview.md`
- Create: `.agents/skills/toefl-speaking-coach/references/speaking-error-taxonomy.md`
- Create: `tests/test_speaking_skill_contract.py`

**Interfaces:**
- Consumes: ETS 2026 blueprint and score policy.
- Produces: stable speaking diagnostic codes and official-versus-diagnostic boundaries.

- [ ] **Step 1: Write failing contract tests**

```python
# tests/test_speaking_skill_contract.py
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / ".agents/skills/toefl-speaking-coach"


def test_speaking_taxonomy_contains_common_and_route_codes() -> None:
    text = (SKILL / "references/speaking-error-taxonomy.md").read_text()
    required = {
        "SPK-INTELLIGIBILITY", "SPK-PRONUNCIATION", "SPK-STRESS",
        "SPK-RHYTHM", "SPK-INTONATION", "SPK-FLUENCY", "SPK-GRAMMAR",
        "SPK-VOCABULARY", "LR-OMISSION", "LR-ADDITION", "LR-SUBSTITUTION",
        "LR-WORD-ORDER", "INTERVIEW-DIRECTNESS", "INTERVIEW-RELEVANCE",
        "INTERVIEW-ELABORATION", "INTERVIEW-COHERENCE",
    }
    assert all(f"`{code}`" in text for code in required)


def test_standards_fix_item_counts_and_diagnostic_boundary() -> None:
    repeat = (ROOT / "standards/ets-2026/speaking-listen-repeat.md").read_text()
    interview = (ROOT / "standards/ets-2026/speaking-interview.md").read_text()
    assert "7 items" in repeat
    assert "4 questions" in interview
    assert "診斷" in repeat and "診斷" in interview
    assert "不得換算完整 Speaking section band" in repeat
    assert "不得換算完整 Speaking section band" in interview
```

- [ ] **Step 2: Run and verify missing-file failures**

Run: `python3 -m pytest tests/test_speaking_skill_contract.py -v`

Expected: FAIL because the speaking files do not exist.

- [ ] **Step 3: Initialize the skill directory before writing any skill files**

Run:

```bash
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/init_skill.py toefl-speaking-coach --path .agents/skills --resources references --interface display_name="TOEFL Speaking Coach" --interface short_description="Analyze and track TOEFL 2026 speaking practice" --interface default_prompt="Analyze this TOEFL 2026 speaking recording, confirm the speaker mapping, and give me a focused re-recording task."
```

Expected: the skill directory is created. Immediately delete the generated placeholder `SKILL.md` and `agents/openai.yaml` with `apply_patch`; Task 5 will create their final tested forms. Keep the initialized directory and `references/`.

- [ ] **Step 4: Create standards summaries**

```markdown
# standards/ets-2026/speaking-listen-repeat.md
# Listen and Repeat

- Official basis: ETS TOEFL iBT 2026 Test Blueprint and Specifications.
- One test set contains 7 items.
- The task elicits accurate and intelligible repetition of spoken sentences.
- ETS identifies Listen and Repeat as AI-scored, but no public task-level conversion used here supports an official practice score.
- Report practice results as 診斷 evidence, not an official task score.
- One set不得換算完整 Speaking section band.
- Rubric ID: `ets-speaking-blueprint-2026-diagnostic`.
```

```markdown
# standards/ets-2026/speaking-interview.md
# Take an Interview

- Official basis: ETS TOEFL iBT 2026 Test Blueprint and Specifications.
- One test set contains 4 questions.
- The task elicits spontaneous, meaningful, clear, and coherent elaboration using accurate grammar, varied vocabulary, and intelligible prosody.
- ETS identifies Take an Interview as AI-scored, but no public task-level conversion used here supports an official practice score.
- Report practice results as 診斷 evidence, not an official task score.
- One set不得換算完整 Speaking section band.
- Rubric ID: `ets-speaking-blueprint-2026-diagnostic`.
```

- [ ] **Step 5: Create the speaking taxonomy**

```markdown
# Speaking Error Taxonomy

| Code | Scope | Count when |
|---|---|---|
| `SPK-INTELLIGIBILITY` | Shared | A proficient listener cannot reliably identify the intended words. |
| `SPK-PRONUNCIATION` | Shared | Segmental production repeatedly obscures a word. |
| `SPK-STRESS` | Shared | Word or sentence stress harms recognition or meaning. |
| `SPK-RHYTHM` | Shared | Timing or chunking materially harms comprehensibility. |
| `SPK-INTONATION` | Shared | Pitch pattern obscures grouping, intent, or completion. |
| `SPK-FLUENCY` | Shared | Pauses, repairs, or rate repeatedly disrupt connected speech. |
| `SPK-GRAMMAR` | Shared | Grammar changes meaning or repeatedly reduces clarity. |
| `SPK-VOCABULARY` | Shared | Word choice is inaccurate, insufficient, or repeatedly blocks expression. |
| `LR-OMISSION` | Listen and Repeat | A source word or phrase is absent. |
| `LR-ADDITION` | Listen and Repeat | Material not present in the source is added. |
| `LR-SUBSTITUTION` | Listen and Repeat | A source word or form is replaced. |
| `LR-WORD-ORDER` | Listen and Repeat | Source elements are reordered. |
| `INTERVIEW-DIRECTNESS` | Interview | The answer does not directly address the question. |
| `INTERVIEW-RELEVANCE` | Interview | Content is off-topic or weakly connected. |
| `INTERVIEW-ELABORATION` | Interview | A claim lacks explanation, example, or detail. |
| `INTERVIEW-COHERENCE` | Interview | Connections between ideas are unclear. |

Do not create pronunciation events from recording distortion alone. Every counted event requires an audio timestamp and `must_fix` or `should_fix`; optional refinement is `polish`.
```

- [ ] **Step 6: Run tests and commit**

Run: `python3 -m pytest tests/test_speaking_skill_contract.py -v`

Expected: 2 tests pass.

```bash
git add standards/ets-2026/speaking-listen-repeat.md standards/ets-2026/speaking-interview.md .agents/skills/toefl-speaking-coach/references/speaking-error-taxonomy.md tests/test_speaking_skill_contract.py
git commit -m "docs: define TOEFL speaking routes"
```

### Task 3: Build the Deterministic Audio Inspector

**Files:**
- Create: `tools/toefl_tracker/audio.py`
- Create: `tools/inspect_audio.py`
- Create: `tests/test_audio.py`

**Interfaces:**
- Consumes: local audio path; `ffprobe` JSON; `ffmpeg` `volumedetect` text.
- Produces:
  - `inspect_audio(path: Path, runner: Callable = subprocess.run) -> dict`
  - JSON keys `path`, `duration_seconds`, `codec`, `sample_rate_hz`, `channels`, `mean_dbfs`, `peak_dbfs`, `clipping`, `decodable`.
- Does not transcribe, diarize, or judge pronunciation.

- [ ] **Step 1: Write failing parser and failure-mode tests**

```python
# tests/test_audio.py
import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from toefl_tracker.audio import AudioInspectionError, inspect_audio


def runner_success(command: list[str], **kwargs: object) -> CompletedProcess[str]:
    if command[0] == "ffprobe":
        payload = {
            "format": {"duration": "12.50"},
            "streams": [{"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 1}],
        }
        return CompletedProcess(command, 0, json.dumps(payload), "")
    return CompletedProcess(
        command,
        0,
        "",
        "[Parsed_volumedetect_0] mean_volume: -30.0 dB\n"
        "[Parsed_volumedetect_0] max_volume: -5.4 dB\n",
    )


def test_inspection_parses_audio_facts_without_language_judgment(tmp_path: Path) -> None:
    path = tmp_path / "sample.m4a"
    path.write_bytes(b"fixture")
    result = inspect_audio(path, runner_success)
    assert result == {
        "path": str(path.resolve()),
        "duration_seconds": 12.5,
        "codec": "aac",
        "sample_rate_hz": 48000,
        "channels": 1,
        "mean_dbfs": -30.0,
        "peak_dbfs": -5.4,
        "clipping": False,
        "decodable": True,
    }
    assert "pronunciation" not in result


def test_missing_audio_stream_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.m4a"
    path.write_bytes(b"fixture")

    def no_audio(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(command, 0, '{"format": {}, "streams": []}', "")

    with pytest.raises(AudioInspectionError, match="audio stream"):
        inspect_audio(path, no_audio)
```

- [ ] **Step 2: Run and verify import failure**

Run: `python3 -m pytest tests/test_audio.py -v`

Expected: FAIL because `toefl_tracker.audio` does not exist.

- [ ] **Step 3: Implement ffprobe and volume parsing**

```python
# tools/toefl_tracker/audio.py
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path


class AudioInspectionError(RuntimeError):
    pass


def _run(runner: Callable, command: list[str]) -> subprocess.CompletedProcess[str]:
    result = runner(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AudioInspectionError(result.stderr.strip() or f"{command[0]} failed")
    return result


def inspect_audio(path: Path, runner: Callable = subprocess.run) -> dict:
    if not path.is_file():
        raise AudioInspectionError(f"audio file not found: {path}")
    probe = _run(runner, [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,sample_rate,channels",
        "-of", "json", str(path),
    ])
    payload = json.loads(probe.stdout)
    stream = next((row for row in payload.get("streams", []) if row.get("codec_type") == "audio"), None)
    if stream is None:
        raise AudioInspectionError("no decodable audio stream")
    volume = _run(runner, [
        "ffmpeg", "-nostdin", "-hide_banner", "-i", str(path),
        "-af", "volumedetect", "-f", "null", "-",
    ])
    diagnostics = volume.stderr + "\n" + volume.stdout
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", diagnostics)
    peak_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", diagnostics)
    if not mean_match or not peak_match:
        raise AudioInspectionError("ffmpeg did not return volume metrics")
    peak = float(peak_match.group(1))
    return {
        "path": str(path.resolve()),
        "duration_seconds": float(payload["format"]["duration"]),
        "codec": stream["codec_name"],
        "sample_rate_hz": int(stream["sample_rate"]),
        "channels": int(stream["channels"]),
        "mean_dbfs": float(mean_match.group(1)),
        "peak_dbfs": peak,
        "clipping": peak >= -0.1,
        "decodable": True,
    }
```

- [ ] **Step 4: Add the JSON CLI**

```python
# tools/inspect_audio.py
import argparse
import json
from pathlib import Path

from toefl_tracker.audio import inspect_audio


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(inspect_audio(args.audio), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run unit and real-file smoke tests**

Run: `python3 -m pytest tests/test_audio.py -v`

Expected: 2 tests pass.

Run:

```bash
python3 tools/inspect_audio.py "/Users/twinb00599242/Downloads/sss.m4a"
```

Expected when the sample remains available: decodable mono AAC audio, 48000 Hz, peak approximately `-5.4`, mean approximately `-30.0`, and `clipping: false`. Do not copy the file into the repository.

- [ ] **Step 6: Commit the audio inspector**

```bash
git add tools/toefl_tracker/audio.py tools/inspect_audio.py tests/test_audio.py
git commit -m "feat: inspect speaking audio quality"
```

### Task 4: Validate Speaking Sessions, Mapping, and Timestamp Evidence

**Files:**
- Create: `tools/toefl_tracker/speaking.py`
- Create: `tools/register_speaking_session.py`
- Create: `tests/test_speaking.py`

**Interfaces:**
- Consumes: attempt dict, `segments` list, event list, feedback Markdown.
- Produces:
  - `validate_speaking_assessment(attempt: dict, segments: list[dict], events: list[dict], feedback: str) -> None`
  - `register_speaking_session(root: Path, manifest: dict, attempt: dict, prompt: str, transcript: str, feedback: str, events: list[dict], segments: list[dict], inspection: dict) -> Path`

- [ ] **Step 1: Write failing session-gate tests**

```python
# tests/test_speaking.py
from pathlib import Path

import pytest
import yaml

from toefl_tracker.io import canonical_source_hash
from toefl_tracker.models import ValidationError
from toefl_tracker.speaking import register_speaking_session, validate_speaking_assessment


def session(task_type: str) -> dict:
    return {
        "modality": "speaking",
        "task_type": task_type,
        "record_type": "formal_original",
        "rubric_version": "ets-speaking-blueprint-2026-diagnostic",
        "result_type": "diagnostic_only",
        "audio_quality": {"decodable": True, "clipping": False},
    }


def segments(count: int, confidence: str = "high") -> list[dict]:
    rows = []
    for item in range(1, count + 1):
        rows.extend([
            {"item": item, "role": "examiner", "start": item * 10.0, "end": item * 10.0 + 2.0, "confidence": confidence},
            {"item": item, "role": "learner", "start": item * 10.0 + 2.2, "end": item * 10.0 + 7.0, "confidence": confidence},
        ])
    return rows


FEEDBACK = """# Result
Diagnostic only.
# Why this level
Evidence.
# Why not the next level
Evidence.
# Timestamp evidence
00:12–00:14 omission.
# Priorities
1. Preserve function words.
# Re-record task
Re-record items 2 and 4.
"""


def test_seven_repeat_items_form_one_session() -> None:
    validate_speaking_assessment(session("listen_and_repeat"), segments(7), [], FEEDBACK)


def test_four_interview_questions_form_one_session() -> None:
    validate_speaking_assessment(session("take_an_interview"), segments(4), [], FEEDBACK)


def test_incomplete_or_ambiguous_mapping_blocks_formal_assessment() -> None:
    with pytest.raises(ValidationError, match="mapping"):
        validate_speaking_assessment(session("listen_and_repeat"), segments(6), [], FEEDBACK)
    with pytest.raises(ValidationError, match="confirmation"):
        validate_speaking_assessment(session("take_an_interview"), segments(4, "low"), [], FEEDBACK)


def test_counted_event_requires_timestamp_in_feedback() -> None:
    event = {
        "event_id": "S-1",
        "level": "must_fix",
        "audio_timestamp": "00:22–00:24",
    }
    with pytest.raises(ValidationError, match="timestamp"):
        validate_speaking_assessment(session("listen_and_repeat"), segments(7), [event], FEEDBACK)


def test_registration_persists_audio_reference_inspection_and_segments(tmp_path: Path) -> None:
    manifest = yaml.safe_load(
        (Path(__file__).parents[1] / "standards/ets-2026/manifest.yaml").read_text()
    )
    prompt = "Seven source sentences"
    transcript = "Seven learner repetitions"
    attempt = {
        "schema_version": 1,
        "attempt_id": "S-LR-20260731-001",
        "modality": "speaking",
        "task_type": "listen_and_repeat",
        "record_type": "formal_original",
        "submitted_at": "2026-07-31T10:00:00+08:00",
        "practiced_at": "2026-07-31",
        "timed": True,
        "duration_seconds": 120,
        "assistance": {"spellcheck": None, "translation": None, "other": None},
        "rubric_version": "ets-speaking-blueprint-2026-diagnostic",
        "standard_verified_at": "2026-07-31",
        "result_type": "diagnostic_only",
        "audio_quality": {"decodable": True, "clipping": False},
        "task_metrics": {"reconstruction": "partial", "intelligibility": "adequate"},
        "source_hash": canonical_source_hash(prompt, transcript),
        "opportunities": {"LR-OMISSION": 7},
        "parent_attempt_id": None,
        "revision_outcomes": None,
    }
    inspection = {
        "path": "/private/source/practice.m4a",
        "duration_seconds": 120.0,
        "codec": "aac",
        "sample_rate_hz": 48000,
        "channels": 1,
        "mean_dbfs": -30.0,
        "peak_dbfs": -5.4,
        "clipping": False,
        "decodable": True,
    }
    path = register_speaking_session(
        tmp_path, manifest, attempt, prompt, transcript, FEEDBACK, [],
        segments(7), inspection,
    )
    assert (path / "audio-inspection.json").exists()
    assert (path / "segments.yaml").exists()
    assert (path / "source-reference.txt").read_text() == "/private/source/practice.m4a\n"
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m pytest tests/test_speaking.py -v`

Expected: FAIL because `toefl_tracker.speaking` does not exist.

- [ ] **Step 3: Implement the speaking gate**

```python
# tools/toefl_tracker/speaking.py
import json
import re
from pathlib import Path

import yaml

from toefl_tracker.io import atomic_write_text
from toefl_tracker.models import ValidationError
from toefl_tracker.register import register_attempt


ITEM_COUNTS = {"listen_and_repeat": 7, "take_an_interview": 4}
REQUIRED_HEADINGS = (
    "# Result", "# Why this level", "# Why not the next level",
    "# Timestamp evidence", "# Priorities", "# Re-record task",
)


def validate_speaking_assessment(
    attempt: dict,
    segments: list[dict],
    events: list[dict],
    feedback: str,
) -> None:
    if attempt.get("modality") != "speaking":
        raise ValidationError("speaking assessment requires speaking modality")
    expected = ITEM_COUNTS.get(attempt.get("task_type"))
    if expected is None:
        raise ValidationError("unknown speaking task")
    if attempt.get("rubric_version") != "ets-speaking-blueprint-2026-diagnostic":
        raise ValidationError("speaking rubric mismatch")
    if attempt.get("result_type") != "diagnostic_only":
        raise ValidationError("speaking session must be diagnostic_only")
    if not attempt.get("audio_quality", {}).get("decodable"):
        raise ValidationError("audio is not decodable")
    pairs = {
        item: {row["role"] for row in segments if row["item"] == item}
        for item in range(1, expected + 1)
    }
    if len(segments) != expected * 2 or any(roles != {"examiner", "learner"} for roles in pairs.values()):
        raise ValidationError("incomplete examiner/learner mapping")
    if any(row.get("confidence") != "high" and not row.get("confirmed_by_user") for row in segments):
        raise ValidationError("ambiguous mapping requires user confirmation")
    if any(heading not in feedback for heading in REQUIRED_HEADINGS):
        raise ValidationError("speaking feedback is missing required headings")
    priority_block = feedback.split("# Priorities", 1)[1].split("# Re-record task", 1)[0]
    if len(re.findall(r"(?m)^\d+\.\s", priority_block)) > 3:
        raise ValidationError("first-round feedback exceeds three priorities")
    for event in events:
        timestamp = str(event.get("audio_timestamp", "")).strip()
        if event.get("level") in {"must_fix", "should_fix"} and timestamp not in feedback:
            raise ValidationError(f"feedback omits timestamp: {event.get('event_id')}")


def register_speaking_session(
    root: Path,
    manifest: dict,
    attempt: dict,
    prompt: str,
    transcript: str,
    feedback: str,
    events: list[dict],
    segments: list[dict],
    inspection: dict,
) -> Path:
    validate_speaking_assessment(attempt, segments, events, feedback)
    if attempt.get("audio_quality") != {
        "decodable": inspection.get("decodable"),
        "clipping": inspection.get("clipping"),
    }:
        raise ValidationError("attempt audio_quality does not match inspection")
    destination = register_attempt(
        root, manifest, attempt, prompt, transcript, feedback, events
    )
    atomic_write_text(
        destination / "audio-inspection.json",
        json.dumps(inspection, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    atomic_write_text(
        destination / "segments.yaml",
        yaml.safe_dump(segments, allow_unicode=True, sort_keys=False),
    )
    atomic_write_text(
        destination / "source-reference.txt",
        str(inspection["path"]).rstrip() + "\n",
    )
    return destination
```

- [ ] **Step 4: Add the speaking registration CLI**

```python
# tools/register_speaking_session.py
import argparse
import json
from pathlib import Path

import yaml

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.speaking import register_speaking_session


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--inspection", type=Path, required=True)
    args = parser.parse_args()
    prompt = args.prompt.read_text()
    transcript = args.transcript.read_text()
    attempt = read_yaml(args.attempt)
    attempt["source_hash"] = canonical_source_hash(prompt, transcript)
    events = [json.loads(line) for line in args.events.read_text().splitlines() if line.strip()]
    segments = yaml.safe_load(args.segments.read_text())
    inspection = json.loads(args.inspection.read_text())
    destination = register_speaking_session(
        args.root,
        read_yaml(args.root / "standards/ets-2026/manifest.yaml"),
        attempt,
        prompt,
        transcript,
        args.feedback.read_text(),
        events,
        segments,
        inspection,
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run speaking tests**

Run: `python3 -m pytest tests/test_speaking.py -v`

Expected: 5 tests pass.

- [ ] **Step 6: Commit the speaking gate**

```bash
git add tools/toefl_tracker/speaking.py tools/register_speaking_session.py tests/test_speaking.py
git commit -m "feat: validate TOEFL speaking sessions"
```

### Task 5: Author the Initialized Speaking Coach Skill

**Files:**
- Create: `.agents/skills/toefl-speaking-coach/SKILL.md`
- Create via generator: `.agents/skills/toefl-speaking-coach/agents/openai.yaml`
- Create: `.agents/skills/toefl-speaking-coach/references/audio-intake.md`
- Create: `.agents/skills/toefl-speaking-coach/references/listen-and-repeat.md`
- Create: `.agents/skills/toefl-speaking-coach/references/take-an-interview.md`
- Modify: `tests/test_speaking_skill_contract.py`

**Interfaces:**
- Consumes: audio inspector, speaking validator, standards, taxonomy, and root `AGENTS.md`.
- Produces: discoverable skill `toefl-speaking-coach` with conditional route references.

- [ ] **Step 1: Extend the failing skill contract**

```python
def test_skill_requires_quality_and_mapping_before_assessment() -> None:
    text = (SKILL / "SKILL.md").read_text()
    assert len(text.splitlines()) < 200
    assert "references/audio-intake.md" in text
    assert "references/listen-and-repeat.md" in text
    assert "references/take-an-interview.md" in text
    assert "配對完成前不得正式評估" in text
    assert "diagnostic_only" in text
    assert "最多三個" in text
    assert "預設不複製原始音檔" in text


def test_routes_are_not_mixed() -> None:
    repeat = (SKILL / "references/listen-and-repeat.md").read_text()
    interview = (SKILL / "references/take-an-interview.md").read_text()
    assert "Source reconstruction" in repeat
    assert "Idea elaboration" not in repeat
    assert "Idea elaboration" in interview
    assert "Source reconstruction" not in interview
```

- [ ] **Step 2: Run and verify failure**

Run: `python3 -m pytest tests/test_speaking_skill_contract.py -v`

Expected: FAIL because the speaking skill and route references do not exist.

- [ ] **Step 3: Create `SKILL.md` with the core workflow**

```markdown
---
name: toefl-speaking-coach
description: Use when the learner provides TOEFL 2026 speaking audio, a continuous prompt-and-answer recording, Listen and Repeat practice, an Interview set, a re-recording, a speaking diagnosis request, or a speaking progress review.
---

# TOEFL Speaking Coach

## Core rule

Separate audio quality from English performance, and complete speaker mapping before formal assessment.

## Intake gate

1. Read `standards/ets-2026/manifest.yaml`, `score-policy.md`, and `references/audio-intake.md`.
2. Run `tools/inspect_audio.py` on the source file.
3. Segment alternating examiner and learner speech; retain timestamps and confidence.
4. Present only ambiguous mappings for confirmation.
5. 配對完成前不得正式評估。
6. State which dimensions remain reliable when audio quality is limited.

## Route

- Seven Listen and Repeat items: read `references/listen-and-repeat.md`.
- Four Take an Interview questions: read `references/take-an-interview.md`.
- Counted speaking issues: read `references/speaking-error-taxonomy.md`.
- Do not load or apply the other route.

## First-round output

Give these parts in order:

1. File quality and examiner/learner mapping status.
2. Result labeled `diagnostic_only`, with confidence and one-sentence verdict.
3. Why this level of performance.
4. Why not the next performance level.
5. Timestamp evidence split into must-fix, should-fix, and polish.
6. 最多三個 priorities.
7. A bounded re-recording task.

Do not convert the session to a Speaking section band. Do not provide complete model responses before the learner re-records.

## Revision

Compare the assigned segments and priorities only. Report resolved, partly resolved, unresolved, and newly introduced issues. A partial re-recording is a revision and never a new formal session.

## Persist

預設不複製原始音檔。Store the source reference, inspection JSON, confirmed segment map, transcript, assessment, and timestamp events through `tools/register_speaking_session.py`. Register only a complete 7-item or 4-question formal original. Rebuild reports and run `tools/validate_tracker.py`.
```

- [ ] **Step 4: Add the audio intake contract**

```markdown
# Audio Intake

## Technical inspection

Record absolute source reference, duration, codec, sample rate, channels, mean dBFS, peak dBFS, clipping, and decodability. These are recording facts, not language judgments.

## Segment map

For every required item, store one examiner segment and one learner segment with start, end, role, item number, and confidence. A low- or medium-confidence role requires explicit learner confirmation.

## Quality decisions

- Undecodable: stop content assessment.
- Missing prompt or answer: assess only identifiable material and do not register a complete formal session.
- Distortion or clipping: withhold affected pronunciation judgments.
- Low level but intelligible: state reduced confidence; do not count volume as a speaking error.
```

- [ ] **Step 5: Add the two route contracts**

```markdown
# Listen and Repeat

Use rubric ID `ets-speaking-blueprint-2026-diagnostic`.

## Required evidence

- Source reconstruction: omission, addition, substitution, and word order by item
- Word recognition and intelligibility
- Segmental pronunciation when recording quality supports it
- Stress, rhythm, and intonation
- Accurate items as positive control evidence

Treat 7 items as one formal session. Do not evaluate Idea elaboration, reasons, examples, or interview content development.

Assign re-recording only for the smallest set of items that demonstrates the top priorities.
```

```markdown
# Take an Interview

Use rubric ID `ets-speaking-blueprint-2026-diagnostic`.

## Required evidence

- Direct answer and relevance
- Idea elaboration through explanation, reason, example, or detail
- Coherence and organization
- Grammar and vocabulary
- Fluency, pausing, and repair
- Pronunciation, stress, intonation, prosody, and intelligibility

Treat 4 questions as one formal session. Do not use Source reconstruction or word-for-word matching as the primary content measure.

Assign a bounded re-recording of one or two answers targeting the top priorities.
```

- [ ] **Step 6: Generate final UI metadata**

Run:

```bash
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py .agents/skills/toefl-speaking-coach --interface display_name="TOEFL Speaking Coach" --interface short_description="Analyze and track TOEFL 2026 speaking practice" --interface default_prompt="Analyze this TOEFL 2026 speaking recording, confirm the speaker mapping, and give me a focused re-recording task."
```

Expected: creates `agents/openai.yaml` from the completed skill.

- [ ] **Step 7: Validate, test, and commit**

Run:

```bash
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-speaking-coach
```

Expected: validation passes.

Run: `python3 -m pytest tests/test_speaking_skill_contract.py tests/test_speaking.py -v`

Expected: all speaking contract and gate tests pass.

```bash
git add .agents/skills/toefl-speaking-coach tests/test_speaking_skill_contract.py
git commit -m "feat: add TOEFL speaking coach skill"
```

### Task 6: Forward-Test Continuous-Audio and Route Behavior

**Files:**
- Create: `tests/skill-evals/speaking/skill-results.md`
- Modify: the speaking skill or one direct reference only when a witnessed failure requires a minimal correction.

**Interfaces:**
- Consumes: Scenario A–C artifacts and the completed skill.
- Produces: fresh-agent evidence that mapping, route, score, and iteration rules hold.

- [ ] **Step 1: Forward-test ambiguous mapping**

Spawn a fresh agent with: `Use $toefl-speaking-coach at .agents/skills/toefl-speaking-coach to respond to Scenario A using the supplied segment candidates.`

Do not reveal the evaluation checklist. Verify that it stops before formal scoring and asks only about ambiguous segments.

- [ ] **Step 2: Forward-test Listen and Repeat**

Spawn another fresh agent with the seven-item raw transcripts and timestamps. Verify every Scenario B criterion and confirm the output contains no Interview elaboration scoring.

- [ ] **Step 3: Forward-test Take an Interview**

Spawn another fresh agent with the four-question raw transcripts and timestamps. Verify every Scenario C criterion and confirm the result is diagnostic only.

- [ ] **Step 4: Close only witnessed gaps**

Record each omission or rationalization verbatim in `skill-results.md`. Add the smallest required field or conditional rule to the relevant file and rerun only the affected fresh-agent scenario. Continue until every criterion passes.

- [ ] **Step 5: Validate and commit**

Run:

```bash
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-speaking-coach
```

Expected: validation passes.

Run: `python3 -m pytest -v`

Expected: all foundation, writing, audio, speaking, and skill-contract tests pass.

```bash
git add .agents/skills/toefl-speaking-coach tests/skill-evals/speaking/skill-results.md
git commit -m "test: forward-test TOEFL speaking coach"
```

### Task 7: Run End-to-End Cadence and Fresh-Context Acceptance

**Files:**
- Create: `tests/test_end_to_end.py`
- Generate only in pytest temporary directories: three writing attempts, three Listen and Repeat sessions, three Interview sessions, revisions, and a relapse sequence.

**Interfaces:**
- Consumes: both skills, shared tracker, validators, and report engine.
- Produces: final automated proof of counts, route isolation, report cadence, duplicate rejection, revision exclusion, and status transitions.

- [ ] **Step 1: Write the failing end-to-end test before fixture helpers**

```python
# tests/test_end_to_end.py
from pathlib import Path

from toefl_tracker.audit import audit_workspace
from toefl_tracker.reports import rebuild_modality


def test_full_practice_cadence_and_integrity(populated_workspace: Path) -> None:
    writing_reports = {path.name for path in rebuild_modality(populated_workspace, "writing")}
    speaking_reports = {path.name for path in rebuild_modality(populated_workspace, "speaking")}
    assert "writing-common-0003.md" in writing_reports
    assert "writing-academic-discussion-0003.md" in writing_reports
    assert "speaking-common-0006.md" in speaking_reports
    assert "speaking-listen-and-repeat-0003.md" in speaking_reports
    assert "speaking-take-an-interview-0003.md" in speaking_reports
    profile = (populated_workspace / "tracker/speaking/profile.md").read_text()
    assert "`SPK-FLUENCY`: relapsed" in profile
    assert audit_workspace(populated_workspace) == []
```

- [ ] **Step 2: Run and verify fixture failure**

Run: `python3 -m pytest tests/test_end_to_end.py -v`

Expected: ERROR because fixture `populated_workspace` does not exist.

- [ ] **Step 3: Add the fixture in `tests/conftest.py`**

```python
# tests/conftest.py
import shutil
from pathlib import Path

import pytest

from toefl_tracker.io import canonical_source_hash, read_yaml
from toefl_tracker.models import ValidationError
from toefl_tracker.register import register_attempt
from toefl_tracker.speaking import register_speaking_session


ROOT = Path(__file__).parents[1]


def make_attempt(
    modality: str,
    task_type: str,
    attempt_id: str,
    day: int,
    record_type: str = "formal_original",
    parent_attempt_id: str | None = None,
) -> tuple[dict, str, str]:
    prompt = f"Fixture prompt {attempt_id}"
    response = f"Fixture response {attempt_id}"
    rubric = (
        "ets-writing-discussion-2025-applicable-2026"
        if modality == "writing"
        else "ets-speaking-blueprint-2026-diagnostic"
    )
    attempt = {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "modality": modality,
        "task_type": task_type,
        "record_type": record_type,
        "submitted_at": f"2026-01-{day:02d}T10:00:00+08:00",
        "practiced_at": f"2026-01-{day:02d}",
        "timed": True,
        "duration_seconds": 600 if modality == "writing" else 120,
        "assistance": {"spellcheck": False, "translation": False, "other": None},
        "rubric_version": rubric,
        "standard_verified_at": "2026-07-31",
        "task_metrics": {},
        "source_hash": canonical_source_hash(prompt, response),
        "opportunities": (
            {"GRAM-ARTICLE": 1}
            if modality == "writing"
            else {"SPK-FLUENCY": 1}
        ),
        "parent_attempt_id": parent_attempt_id,
        "revision_outcomes": (
            {
                "assigned": 2,
                "resolved": 1,
                "partly_resolved": 1,
                "unresolved": 0,
                "new_errors": 0,
                "resolution_rate": 0.5,
            }
            if record_type == "revision"
            else None
        ),
    }
    if modality == "writing":
        attempt["word_count"] = 100
        attempt["task_score"] = {"scale": "0-5", "value": 3, "confidence": "medium"}
    else:
        attempt["result_type"] = "diagnostic_only"
        attempt["audio_quality"] = {"decodable": True, "clipping": False}
    return attempt, prompt, response


def fluency_event(attempt_id: str, event_id: str, status: str) -> dict:
    return {
        "event_id": event_id,
        "attempt_id": attempt_id,
        "taxonomy_version": 1,
        "code": "SPK-FLUENCY",
        "source_excerpt": "",
        "audio_timestamp": "00:10–00:12",
        "suggested_revision": "Repeat the answer with one planned pause.",
        "reason": "Repeated repairs interrupt connected speech.",
        "level": "should_fix",
        "severity": "clarity_reducing",
        "task_specific": False,
        "opportunity_present": True,
        "historical_status": status,
    }


def speaking_segments(task_type: str) -> list[dict]:
    count = 7 if task_type == "listen_and_repeat" else 4
    rows = []
    for item in range(1, count + 1):
        rows.extend([
            {
                "item": item,
                "role": "examiner",
                "start": item * 10.0,
                "end": item * 10.0 + 2.0,
                "confidence": "high",
            },
            {
                "item": item,
                "role": "learner",
                "start": item * 10.0 + 2.2,
                "end": item * 10.0 + 7.0,
                "confidence": "high",
            },
        ])
    return rows


SPEAKING_FEEDBACK = """# Result
Diagnostic only.
# Why this level
Fixture evidence.
# Why not the next level
Fixture evidence.
# Timestamp evidence
00:10–00:12 repeated repair.
# Priorities
1. Reduce repeated repair.
# Re-record task
Re-record the affected item.
"""


def inspection(attempt_id: str) -> dict:
    return {
        "path": f"/private/source/{attempt_id}.m4a",
        "duration_seconds": 120.0,
        "codec": "aac",
        "sample_rate_hz": 48000,
        "channels": 1,
        "mean_dbfs": -30.0,
        "peak_dbfs": -5.4,
        "clipping": False,
        "decodable": True,
    }


@pytest.fixture
def populated_workspace(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "standards", tmp_path / "standards")
    manifest = read_yaml(tmp_path / "standards/ets-2026/manifest.yaml")

    writing_rows = [
        make_attempt("writing", "academic_discussion", "W-AD-20260101-001", 1),
        make_attempt("writing", "academic_discussion", "W-AD-20260102-002", 2),
        make_attempt(
            "writing",
            "academic_discussion",
            "W-AD-20260102-002-R1",
            3,
            record_type="revision",
            parent_attempt_id="W-AD-20260102-002",
        ),
        make_attempt("writing", "academic_discussion", "W-AD-20260104-003", 4),
    ]
    for attempt, prompt, response in writing_rows:
        register_attempt(tmp_path, manifest, attempt, prompt, response, "Fixture feedback", [])

    speaking_rows = [
        make_attempt("speaking", "listen_and_repeat", "S-LR-20260105-001", 5),
        make_attempt("speaking", "listen_and_repeat", "S-LR-20260106-002", 6),
        make_attempt("speaking", "listen_and_repeat", "S-LR-20260107-003", 7),
        make_attempt("speaking", "take_an_interview", "S-INT-20260108-001", 8),
        make_attempt("speaking", "take_an_interview", "S-INT-20260109-002", 9),
        make_attempt("speaking", "take_an_interview", "S-INT-20260110-003", 10),
    ]
    for index, (attempt, prompt, response) in enumerate(speaking_rows):
        events = []
        if index == 0:
            events = [fluency_event(attempt["attempt_id"], "S-E-001", "new")]
        if index == 4:
            events = [fluency_event(attempt["attempt_id"], "S-E-002", "relapsed")]
        register_speaking_session(
            tmp_path,
            manifest,
            attempt,
            prompt,
            response,
            SPEAKING_FEEDBACK,
            events,
            speaking_segments(attempt["task_type"]),
            inspection(attempt["attempt_id"]),
        )

    duplicate, prompt, response = speaking_rows[0]
    with pytest.raises(ValidationError, match="attempt_id already exists"):
        register_speaking_session(
            tmp_path,
            manifest,
            duplicate,
            prompt,
            response,
            SPEAKING_FEEDBACK,
            [],
            speaking_segments(duplicate["task_type"]),
            inspection(duplicate["attempt_id"]),
        )

    return tmp_path
```

- [ ] **Step 4: Run the end-to-end and full suites**

Run: `python3 -m pytest tests/test_end_to_end.py -v`

Expected: 1 test passes.

Run: `python3 -m pytest -v`

Expected: the complete suite passes.

- [ ] **Step 5: Validate the real workspace**

Run: `python3 tools/rebuild_reports.py --root . --modality all`

Expected: derived files rebuild without changing formal counts.

Run: `python3 tools/validate_tracker.py --root .`

Expected: exit 0.

- [ ] **Step 6: Run a fresh Codex-context smoke test**

From the repository root, start a fresh Codex task and ask:

```text
Read the repository instructions and current tracker. Tell me which skill you would use for (1) a new Email response and (2) one continuous four-question Interview recording. Report the current formal writing and speaking counts without changing files.
```

Expected: it identifies the two correct skills, reports counts solely from tracker files, does not invent a section band, and makes no write.

- [ ] **Step 7: Commit final acceptance coverage**

```bash
git add tests/conftest.py tests/test_end_to_end.py
git commit -m "test: verify TOEFL coaching workflow end to end"
```

## Speaking and System Completion Check

- [ ] Run `quick_validate.py` separately on each skill.
- [ ] Run `python3 -m pytest -v` and record the exact pass count.
- [ ] Run `python3 tools/inspect_audio.py "/Users/twinb00599242/Downloads/sss.m4a"` without copying the audio.
- [ ] Run `python3 tools/rebuild_reports.py --root . --modality all`.
- [ ] Run `python3 tools/validate_tracker.py --root .` and confirm exit 0.
- [ ] Confirm both forward-test checklists are entirely passing.
- [ ] Run `git diff --check`.
- [ ] Confirm `git status --short` is empty after the final commit.
