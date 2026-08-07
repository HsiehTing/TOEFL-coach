# TOEFL Integrity Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make each attempt directory the atomic source of truth, enforce modality and evidence integrity, rebuild trustworthy three-practice reports, and add private transcript-first TOEFL speaking intake.

**Architecture:** Publish a fully validated attempt directory containing its own event sidecar with one atomic rename, then derive the aggregate ledger and all reports from those canonical directories. Writing and Speaking construct typed validated registration bundles through separate gates. Speaking uses local `ffmpeg`/`ffprobe` plus `whisper.cpp` transcription; the coach assigns roles from TOEFL transcript structure and deterministic validators confirm the four- or seven-item mapping.

**Tech Stack:** Python 3.11+, PyYAML 6.x, pytest 8.x, Homebrew `ffmpeg`, Homebrew `whisper-cpp`, `ggml-small.en.bin`, Markdown/YAML/JSONL/CSV tracker artifacts.

## Global Constraints

- The approved design is `docs/superpowers/specs/2026-08-01-toefl-integrity-hardening-design.md`; its data model and acceptance criteria are binding.
- Preserve the existing real record exactly: Writing formal count 1, attempt `W-AD-20260731-001`, word count 183, counted events 7; Speaking formal count 0.
- Never overwrite an original response, transcript, feedback, or prior rubric evaluation.
- A published attempt directory is canonical; `error-events.jsonl`, dashboard, profile, and cadence reports are derived.
- Writing and Speaking formal registration must pass their own modality gates. Speaking cannot enter through the generic CLI.
- Common reports contain only common taxonomy codes; route reports contain common plus matching route codes.
- Do not create a Speaking section band or any unofficial aggregate AI score.
- Raw audio stays outside the repository. Tracked files may contain only an opaque source ID, inspection facts, transcript, mapping, metrics, and feedback.
- Local audio transcription uses `ffmpeg`, `ffprobe`, `whisper-cli`, and the model selected by `TOEFL_WHISPER_MODEL`; no audio is uploaded.
- Every production behavior change follows RED → GREEN → REFACTOR. Preserve the failing-test and passing-test commands in each task report.
- Run the full test suite, both skill validators, deterministic rebuild, tracker audit, and `git diff --check` before final review.

---

### Task 1: Canonical Event Sidecars and Migration API

**Files:**
- Create: `tools/toefl_tracker/canonical.py`
- Create: `tools/migrate_event_sidecars.py`
- Modify: `tools/toefl_tracker/models.py`
- Modify: `tools/toefl_tracker/register.py`
- Modify: `tools/toefl_tracker/io.py`
- Test: `tests/test_canonical.py`
- Test: `tests/test_register.py`

**Interfaces:**
- Produces: `ValidatedPracticeRegistration`, `ValidatedReevaluationRegistration`, `canonical_jsonl(events: Iterable[Mapping]) -> str`, `load_canonical_events(root: Path, modality: str) -> list[dict]`, `render_aggregate_events(root: Path, modality: str) -> str`, `write_aggregate_events(root: Path, modality: str) -> Path`, `migrate_event_sidecars(root: Path, apply: bool) -> MigrationResult`, and `publish_registration(root: Path, manifest: dict, registration: ValidatedPracticeRegistration | ValidatedReevaluationRegistration, failpoint: Callable[[str], None] | None = None) -> Path`.
- Preserves temporarily: the existing `register_attempt` function as a deprecated compatibility wrapper until Task 4 removes direct callers.
- Later tasks consume canonical event loading rather than reading the aggregate ledger as source data.

- [ ] **Step 1: Add failing canonical and migration tests**

```python
def test_published_attempt_contains_its_own_event_sidecar(tmp_path, manifest, valid_registration):
    destination = publish_registration(tmp_path, manifest, valid_registration)
    assert (destination / "events.jsonl").read_text(encoding="utf-8") == canonical_jsonl(valid_registration.events)

def test_aggregate_ledger_is_rendered_from_attempt_sidecars(tmp_path, populated_canonical_attempts):
    expected = "".join(populated_canonical_attempts.expected_jsonl)
    assert render_aggregate_events(tmp_path, "writing") == expected

def test_migration_dry_run_is_non_mutating_and_apply_is_idempotent(tmp_path, legacy_tracker):
    before = tree_digest(tmp_path)
    result = migrate_event_sidecars(tmp_path, apply=False)
    assert result.created == ("W-AD-20260731-001",)
    assert tree_digest(tmp_path) == before
    migrate_event_sidecars(tmp_path, apply=True)
    after_first = tree_digest(tmp_path)
    migrate_event_sidecars(tmp_path, apply=True)
    assert tree_digest(tmp_path) == after_first

def test_migration_stops_on_existing_conflicting_sidecar(tmp_path, legacy_tracker):
    sidecar = legacy_tracker / "attempts/W-AD-20260731-001/events.jsonl"
    sidecar.write_text('{"event_id":"CONFLICT"}\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="conflicting canonical event sidecar"):
        migrate_event_sidecars(tmp_path, apply=True)
```

- [ ] **Step 2: Run the focused tests and record the expected RED**

Run: `python3 -m pytest tests/test_canonical.py tests/test_register.py -q`

Expected: collection fails because `toefl_tracker.canonical`, bundle dataclasses, and `publish_registration` do not exist.

- [ ] **Step 3: Implement typed bundles, canonical serialization, and sidecar migration**

```python
@dataclass(frozen=True)
class ValidatedPracticeRegistration:
    attempt: dict
    prompt: str
    response: str
    feedback: str
    events: tuple[dict, ...]
    extra_files: Mapping[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class ValidatedReevaluationRegistration:
    attempt: dict
    feedback: str

def canonical_jsonl(events: Iterable[Mapping]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in events)
```

`publish_registration` must write the sidecar inside staging and rename the completed directory without writing the aggregate ledger inside the transaction. `migrate_event_sidecars` groups the legacy ledger by `attempt_id`, rejects orphan/duplicate/conflicting events, and uses `atomic_write_text` only when `apply=True`. The CLI must require exactly one of `--dry-run` or `--apply` and print counts without exposing learner evidence.

- [ ] **Step 4: Run focused and regression tests**

Run: `python3 -m pytest tests/test_canonical.py tests/test_register.py -q`

Expected: all focused tests pass; existing duplicate source and rollback behaviors remain green.

- [ ] **Step 5: Commit Task 1**

```bash
git add tools/toefl_tracker/canonical.py tools/migrate_event_sidecars.py tools/toefl_tracker/models.py tools/toefl_tracker/register.py tools/toefl_tracker/io.py tests/test_canonical.py tests/test_register.py
git commit -m "refactor: make attempt events canonical"
```

---

### Task 2: Kill-Safe Atomic Directory Publication

**Files:**
- Modify: `tools/toefl_tracker/io.py`
- Modify: `tools/toefl_tracker/register.py`
- Create: `tests/helpers/register_subprocess.py`
- Create: `tests/test_crash_recovery.py`

**Interfaces:**
- Consumes: `publish_registration` with its optional named failpoint callback from Task 1.
- Produces: `fsync_directory(path: Path) -> None`, `recover_registration_state(root: Path, modality: str) -> None`, named failpoints `after_attempt`, `after_events`, `after_staging_fsync`, `before_rename`, and `after_rename`, plus safe abandoned-staging cleanup.

- [ ] **Step 1: Write subprocess kill-boundary tests before durability code**

```python
@pytest.mark.parametrize("point", [
    "after_attempt", "after_events", "after_staging_fsync", "before_rename", "after_rename",
])
def test_process_death_never_separates_attempt_and_events(tmp_path, point):
    completed = subprocess.run(
        [sys.executable, str(HELPER), str(tmp_path), point],
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT / "tools")},
    )
    assert completed.returncode == 91
    recover_registration_state(tmp_path)
    attempts = published_attempt_ids(tmp_path, "writing")
    events = load_canonical_events(tmp_path, "writing")
    if "W-AD-KILL-001" in attempts:
        assert {row["attempt_id"] for row in events} == {"W-AD-KILL-001"}
    else:
        assert events == []
```

The helper passes a callback that calls `os._exit(91)` at the requested named failpoint; production code must not read a kill-test environment variable.

- [ ] **Step 2: Verify every kill case is RED for the expected durability/recovery reason**

Run: `python3 -m pytest tests/test_crash_recovery.py -q`

Expected: at least `after_rename` or pre-rename cleanup assertions fail because directory fsync and the new recovery contract are absent.

- [ ] **Step 3: Add file and directory durability without a WAL**

```python
def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
```

Call the injected failpoint only after the named durable boundary. Flush/fsync every staged file through `atomic_write_text`, fsync staging, rename once, then fsync the attempts directory. Recovery deletes only directories matching `_STAGING_PREFIX`; it never promotes `.ready` state and never touches a published attempt.

- [ ] **Step 4: Run crash, concurrency, and registration suites**

Run: `python3 -m pytest tests/test_crash_recovery.py tests/test_register.py -q`

Expected: every kill boundary and existing concurrent registration test passes.

- [ ] **Step 5: Commit Task 2**

```bash
git add tools/toefl_tracker/io.py tools/toefl_tracker/register.py tests/helpers/register_subprocess.py tests/test_crash_recovery.py
git commit -m "fix: make TOEFL attempt publication kill-safe"
```

---

### Task 3: Versioned Taxonomy and Contextual Event Validation

**Files:**
- Create: `standards/ets-2026/taxonomy.yaml`
- Create: `tools/toefl_tracker/taxonomy.py`
- Create: `tools/toefl_tracker/event_validation.py`
- Modify: `tools/toefl_tracker/validation.py`
- Modify: `tools/toefl_tracker/status.py`
- Modify: `.agents/skills/toefl-writing-coach/references/writing-error-taxonomy.md`
- Modify: `.agents/skills/toefl-speaking-coach/references/speaking-error-taxonomy.md`
- Create: `tests/test_event_integrity.py`
- Modify: `tests/test_status.py`
- Modify: `tests/test_standards.py`

**Interfaces:**
- Produces: `load_taxonomy(root: Path) -> dict[str, TaxonomyEntry]`, `validate_event_context(root: Path, attempt: dict, response: str, event: dict, current_events: Sequence[dict], historical_attempts: Sequence[dict], historical_events: Sequence[dict], speaking_context: SpeakingEvidenceContext | None = None) -> None`, and `expected_historical_status(code: str, current_attempt: dict, current_events: Sequence[dict], attempts: Sequence[dict], events: Sequence[dict]) -> str | None`.
- Taxonomy entries contain exact `taxonomy_version`, `modality`, `scope`, `task_types`, and `dimension` fields.
- Task 4 calls contextual validation inside the registration lock; Task 5 reuses it during audit.

- [ ] **Step 1: Read and apply `superpowers:writing-skills` before changing taxonomy reference files**

The implementer must read that skill completely. Machine-readable YAML remains authoritative, while both coach-facing Markdown tables stay concise and synchronized.

- [ ] **Step 2: Add failing taxonomy scope and evidence tests**

```python
def test_writing_excerpt_must_occur_in_immutable_response(context):
    event = context.event(source_excerpt="fabricated evidence")
    with pytest.raises(ValidationError, match="excerpt is not present"):
        validate_event_context(**context.args(event))

def test_event_requires_positive_code_opportunity(context):
    context.attempt["opportunities"]["GRAM-ARTICLE"] = 0
    with pytest.raises(ValidationError, match="positive opportunity"):
        validate_event_context(**context.args(context.event()))

def test_route_specific_code_cannot_cross_routes(context):
    event = context.event(code="EMAIL-REGISTER", task_specific=True)
    with pytest.raises(ValidationError, match="does not apply to academic_discussion"):
        validate_event_context(**context.args(event))

def test_duplicate_event_id_is_rejected(context):
    with pytest.raises(ValidationError, match="event_id already exists"):
        validate_event_context(**context.args(context.event(event_id="EXISTING")))

def test_stored_status_must_equal_recomputed_status(context):
    event = context.event(historical_status="controlled")
    with pytest.raises(ValidationError, match="historical_status"):
        validate_event_context(**context.args(event))

def test_unclassified_never_advances_status(unclassified_history):
    assert classify_code("UNCLASSIFIED", *unclassified_history) is None
```

- [ ] **Step 3: Run focused tests and verify RED**

Run: `python3 -m pytest tests/test_event_integrity.py tests/test_status.py tests/test_standards.py -q`

Expected: imports fail for taxonomy/context APIs and current validation accepts fabricated or cross-route events.

- [ ] **Step 4: Add the complete machine-readable taxonomy and one shared validator**

Populate these exact codes:

- Writing common: `GRAM-ARTICLE`, `GRAM-NEGATION`, `GRAM-CLAUSE`, `GRAM-AGREEMENT`, `LEX-WORDFORM`, `LEX-COLLOCATION`, `MECH-SPELLING`, `MECH-PUNCTUATION`.
- Email route: `EMAIL-PURPOSE`, `EMAIL-MISSING-POINT`, `EMAIL-REGISTER`, `EMAIL-POLITENESS`, `EMAIL-ORGANIZATION`, `EMAIL-ACTION`.
- Academic Discussion route: `DISCUSSION-ALIGNMENT`, `DISCUSSION-POSITION`, `DISCUSSION-BORROWING`, `DISCUSSION-CONTRIBUTION`, `DISCUSSION-ELABORATION`, `DISCUSSION-SUPPORT`.
- Speaking common: `SPK-INTELLIGIBILITY`, `SPK-PRONUNCIATION`, `SPK-STRESS`, `SPK-RHYTHM`, `SPK-INTONATION`, `SPK-FLUENCY`, `SPK-GRAMMAR`, `SPK-VOCABULARY`.
- Listen and Repeat route: `LR-OMISSION`, `LR-ADDITION`, `LR-SUBSTITUTION`, `LR-WORD-ORDER`.
- Interview route: `INTERVIEW-DIRECTNESS`, `INTERVIEW-RELEVANCE`, `INTERVIEW-ELABORATION`, `INTERVIEW-COHERENCE`.

Shared codes use `scope: common`; prefixed route codes use `scope: route` and only their named task type. Add `UNCLASSIFIED` with `dimension: taxonomy_review`, require `taxonomy_review_required: true`, and exclude it from rates/status/focus selection.

```python
def normalized_contains(response: str, excerpt: str) -> bool:
    return unicodedata.normalize("NFC", excerpt.strip()) in unicodedata.normalize("NFC", response)

def expected_historical_status(code, current_attempt, current_events, attempts, events):
    return classify_code(code, [*attempts, current_attempt], [*events, *current_events])
```

Validate strings before set membership so unhashable YAML values always raise `ValidationError`, never raw `TypeError`.

- [ ] **Step 5: Keep human-readable taxonomy tables synchronized**

Add a contract test that parses every backticked code in both Markdown tables and asserts exact equality with the corresponding YAML modality codes. The Markdown remains the coach-facing explanation; YAML is the scope/dimension authority.

- [ ] **Step 6: Run focused and validation suites**

Run: `python3 -m pytest tests/test_event_integrity.py tests/test_status.py tests/test_standards.py tests/test_validation.py -q`

Expected: all contextual, status, type-safety, and taxonomy synchronization tests pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add standards/ets-2026/taxonomy.yaml tools/toefl_tracker/taxonomy.py tools/toefl_tracker/event_validation.py tools/toefl_tracker/validation.py tools/toefl_tracker/status.py .agents/skills/toefl-writing-coach/references/writing-error-taxonomy.md .agents/skills/toefl-speaking-coach/references/speaking-error-taxonomy.md tests/test_event_integrity.py tests/test_status.py tests/test_standards.py
git commit -m "feat: validate TOEFL event evidence and scope"
```

---

### Task 4: Modality Gates and Versioned Re-evaluation

**Files:**
- Create: `tools/register_writing_attempt.py`
- Modify: `tools/register_attempt.py`
- Modify: `tools/register_speaking_session.py`
- Modify: `tools/toefl_tracker/writing.py`
- Modify: `tools/toefl_tracker/speaking.py`
- Modify: `tools/toefl_tracker/register.py`
- Modify: `tools/toefl_tracker/validation.py`
- Create: `tests/test_registration_gates.py`
- Create: `tests/test_reevaluation.py`
- Modify: `tests/test_writing.py`
- Modify: `tests/test_speaking.py`

**Interfaces:**
- Produces: `build_writing_registration(root: Path, manifest: dict, attempt: dict, prompt: str, response: str, feedback: str, events: Sequence[dict]) -> ValidatedPracticeRegistration | ValidatedReevaluationRegistration`, `build_speaking_registration(root: Path, manifest: dict, attempt: dict, prompt: str, transcript: str, feedback: str, events: Sequence[dict], segments: Sequence[dict], inspection: dict, transcript_segments: Sequence[dict]) -> ValidatedPracticeRegistration`, `build_reevaluation_registration(root: Path, manifest: dict, attempt: dict, feedback: str) -> ValidatedReevaluationRegistration`, and the dedicated Writing CLI.
- Consumes: typed bundles from Task 1 and contextual validation from Task 3.
- Removes: public dict-based `register_attempt` use from production CLIs.

- [ ] **Step 1: Write CLI bypass and schema-v2 re-evaluation tests**

```python
def test_generic_cli_rejects_speaking_with_dedicated_command(tmp_path, speaking_inputs, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", speaking_inputs.generic_argv)
    with pytest.raises(SystemExit):
        register_attempt_main()
    assert "register_speaking_session.py" in capsys.readouterr().err

def test_writing_cli_runs_feedback_gate_before_publication(tmp_path, writing_inputs):
    writing_inputs.feedback.write_text("unstructured feedback", encoding="utf-8")
    assert run_writing_cli(writing_inputs) != 0
    assert not any((tmp_path / "tracker/writing/attempts").glob("*"))

def test_schema_two_reevaluation_links_without_copying_source(tmp_path, published_original, reevaluation):
    destination = publish_reevaluation(tmp_path, reevaluation)
    assert not (destination / "prompt.md").exists()
    assert not (destination / "response-original.md").exists()
    assert (destination / "events.jsonl").read_text(encoding="utf-8") == ""
    assert read_yaml(destination / "attempt.yaml")["source_hash"] == published_original.source_hash
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/test_registration_gates.py tests/test_reevaluation.py -q`

Expected: Writing CLI and builder APIs are missing; generic CLI still accepts Speaking; schema-v2 fields are unsupported.

- [ ] **Step 3: Build gate-specific registrations under the lock**

Writing must call `validate_attempt`, `validate_writing_assessment`, then contextual validation before creating `ValidatedPracticeRegistration`. Speaking must call its technical/mapping/feedback gate and contextual validation. Re-evaluation must require schema 2, `evaluated_at`, stable `supersedes_evaluation_id`, matching formal parent/source hash, and an empty sidecar.

The generic CLI may delegate Writing to the same builder, but for any Speaking modality it must terminate with an argparse error naming the dedicated CLI. Direct public publisher imports in CLI modules are forbidden by a contract test.

- [ ] **Step 4: Run modality, re-evaluation, and existing route tests**

Run: `python3 -m pytest tests/test_registration_gates.py tests/test_reevaluation.py tests/test_writing.py tests/test_speaking.py tests/test_validation.py -q`

Expected: all gate, parent, source, feedback, and mapping tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add tools/register_writing_attempt.py tools/register_attempt.py tools/register_speaking_session.py tools/toefl_tracker/writing.py tools/toefl_tracker/speaking.py tools/toefl_tracker/register.py tools/toefl_tracker/validation.py tests/test_registration_gates.py tests/test_reevaluation.py tests/test_writing.py tests/test_speaking.py
git commit -m "feat: enforce TOEFL modality registration gates"
```

---

### Task 5: Deterministic Reports and Resilient Audit

**Files:**
- Modify: `tools/toefl_tracker/reports.py`
- Modify: `tools/toefl_tracker/audit.py`
- Modify: `tools/rebuild_reports.py`
- Modify: `tools/validate_tracker.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_reports.py`
- Modify: `tests/test_audit.py`
- Modify: `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: canonical sidecars and taxonomy APIs.
- Produces: exact derived ledger/dashboard/profile/report set for both modalities, including zero-record artifacts.
- Reuses: the same attempt, contextual event, re-evaluation, and Speaking assessment validators used at registration.

- [ ] **Step 1: Add report-content, stale-reconciliation, and corruption tests**

```python
def test_common_report_has_contract_fields_and_excludes_route_codes(populated_workspace):
    rebuild_modality(populated_workspace, "writing")
    report = read_report(populated_workspace, "writing-common-0003.md")
    assert "Formal records: 3" in report
    assert "`W-EMAIL-001` | timed | simulated_task_score" in report
    assert "rubric: `ets-writing-email-2025-applicable-2026`" in report
    assert "## Severe-event trend\n2 → 1 → 0" in report
    assert "EMAIL-REGISTER" not in report

def test_route_report_contains_common_and_only_matching_route_codes(populated_workspace):
    report = rebuild_and_read(populated_workspace, "writing-email-0003.md")
    assert "GRAM-ARTICLE" in report
    assert "EMAIL-REGISTER" in report
    assert "DISCUSSION-ELABORATION" not in report

def test_rebuild_removes_only_stale_generated_reports(tmp_path, canonical_workspace):
    stale = generated_report(tmp_path, "writing-common-9999.md")
    personal = generated_report(tmp_path, "my-notes.md")
    rebuild_modality(tmp_path, "writing")
    assert not stale.exists()
    assert personal.exists()

def test_invalid_utf8_becomes_audit_finding(tmp_path, canonical_workspace):
    target = tmp_path / "tracker/writing/attempts/W-1/response-original.md"
    target.write_bytes(b"\xff\xfe")
    problems = audit_workspace(tmp_path)
    assert any(str(target) in row and "UTF-8" in row for row in problems)

def test_reevaluation_is_shown_beside_original_without_advancing_cadence(workspace_with_reevaluation):
    generated = rebuild_modality(workspace_with_reevaluation, "writing")
    report = read_report(workspace_with_reevaluation, "writing-common-0003.md")
    assert "Original evaluation:" in report
    assert "Re-evaluation:" in report
    assert not any(path.name.endswith("0004.md") for path in generated)

def test_malformed_speaking_artifacts_are_semantic_audit_findings(speaking_workspace):
    segments = speaking_workspace / "tracker/speaking/attempts/S-1/segments.yaml"
    segments.write_text("- role: learner\n  item: 99\n", encoding="utf-8")
    assert any("speaking segment item" in row for row in audit_workspace(speaking_workspace))

def test_zero_speaking_records_still_have_derived_artifacts(tmp_path, standards):
    rebuild_modality(tmp_path, "speaking")
    assert (tmp_path / "tracker/speaking/dashboard.csv").read_text().startswith("attempt_id,")
    assert "Formal records: 0" in (tmp_path / "tracker/speaking/profile.md").read_text()
```

- [ ] **Step 2: Run report/audit tests and verify semantic RED**

Run: `python3 -m pytest tests/test_reports.py tests/test_audit.py tests/test_end_to_end.py -q`

Expected: missing report fields, route pollution, stale files, UTF-8 traceback, or absent zero-modality artifacts fail.

- [ ] **Step 3: Rebuild every derived artifact from canonical data**

Refactor report loading to use `load_canonical_events`. Write aggregate ledger first, then dashboard/profile/reports. Common windows filter `scope == "common"`; route windows filter common plus the selected route. The report row format must include attempt ID, timing label, result label, score/diagnostic, rubric ID, and verification date. Severe-event trend is one count per formal in chronological order.

Use this stable report structure:

```markdown
# <Writing|Speaking> <Common|Route> Report — boundary <0003>

Formal records: <integer>
Attempt IDs: `<id-1>`, `<id-2>`, `<id-3>`

## Record timeline
- `<id>` | <timed|untimed|unknown> | <official_basis|simulated_task_score|diagnostic_only> | result: <value> | rubric: `<id>` | verified: <date>

## Severe-event trend
<count> → <count> → <count>

## Recurring patterns
- `<code>`: <status>, <event count> events in <attempt count> records

## Revision resolution
<percentage or "No comparable revisions">

## Version boundary
<single-rubric statement or explicit cross-version warning>

## Next two focuses
1. `<code>`
2. `<code>`
```

Omit a numbered focus line when fewer than two eligible codes exist; never emit a synthetic placeholder focus.

Focus selection is deterministic: `relapsed`, then `persistent`, then recent-three counted event count descending, then code ascending; emit at most two and exclude `UNCLASSIFIED`.

- [ ] **Step 4: Make audit accumulate parse and semantic findings**

Catch `UnicodeDecodeError`, `yaml.YAMLError`, `json.JSONDecodeError`, `csv.Error`, `OSError`, and `ValidationError` at each file boundary. Rebuild both modalities in a temporary directory, then compare bytes and exact generated-report filename sets. Audit parent type/modality/task relationships and re-run Speaking artifact validation rather than checking existence only.

- [ ] **Step 5: Run focused and complete suites**

Run: `python3 -m pytest tests/test_reports.py tests/test_audit.py tests/test_end_to_end.py -q`

Run: `python3 -m pytest -q`

Expected: focused and complete suites pass with deterministic LF output.

- [ ] **Step 6: Commit Task 5**

```bash
git add tools/toefl_tracker/reports.py tools/toefl_tracker/audit.py tools/rebuild_reports.py tools/validate_tracker.py tests/conftest.py tests/test_reports.py tests/test_audit.py tests/test_end_to_end.py
git commit -m "feat: rebuild trustworthy TOEFL progress reports"
```

---

### Task 6: Offline Audio Preflight, Transcription, and Quality Policy

**Files:**
- Create: `standards/ets-2026/audio-quality-policy.yaml`
- Create: `tools/toefl_tracker/transcription.py`
- Create: `tools/toefl_tracker/quality.py`
- Create: `tools/transcribe_audio.py`
- Modify: `tools/toefl_tracker/audio.py`
- Modify: `tools/inspect_audio.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Test: `tests/test_transcription.py`
- Modify: `tests/test_audio.py`

**Interfaces:**
- Produces: `AudioDependencies`, `preflight_audio_tools(model_path=None)`, `transcribe_audio(path, dependencies, runner=subprocess.run)`, `inspect_segment_quality(path, segments, runner)`, and versioned `quality_decision(metrics)`.
- Consumes: `TOEFL_WHISPER_MODEL`; requires basename `ggml-small.en.bin` outside the repository.
- Task 7 consumes normalized transcript rows `{start: float, end: float, text: str}` and reliable dimensions.

- [ ] **Step 1: Add failing preflight, cleanup, and threshold tests**

```python
@pytest.mark.parametrize("missing", ["ffmpeg", "ffprobe", "whisper-cli", "model"])
def test_preflight_names_each_missing_dependency(missing, dependency_probe):
    dependency_probe.remove(missing)
    with pytest.raises(AudioInspectionError, match=missing):
        preflight_audio_tools(which=dependency_probe.which, environ=dependency_probe.environ)

def test_transcription_converts_to_temporary_wav_and_always_cleans_up(tmp_path, fake_tools):
    rows = transcribe_audio(tmp_path / "input.m4a", fake_tools.dependencies, runner=fake_tools.runner)
    assert rows == [{"start": 0.0, "end": 3.8, "text": "Please describe a place."}]
    assert fake_tools.temporary_paths_remaining() == []

@pytest.mark.parametrize("mean,peak,usable,dimensions", [
    (-30.0, -5.0, True, "all"),
    (-36.0, -10.0, True, "text_only"),
    (-30.0, -21.0, True, "text_only"),
    (-46.0, -10.0, False, "none"),
    (-30.0, -35.0, False, "none"),
    (-30.0, -0.1, False, "none"),
])
def test_quality_policy_boundaries(mean, peak, usable, dimensions):
    decision = quality_decision({"mean_dbfs": mean, "peak_dbfs": peak})
    assert (decision.usable, decision.dimension_set) == (usable, dimensions)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/test_transcription.py tests/test_audio.py -q`

Expected: transcription/quality modules are absent and inspection lacks tool/model preflight.

- [ ] **Step 3: Implement dependency and local transcription wrappers**

Use `shutil.which` for executables and `TOEFL_WHISPER_MODEL` for the model. Convert with:

```text
ffmpeg -nostdin -y -i INPUT -ar 16000 -ac 1 -c:a pcm_s16le TEMP.wav
whisper-cli -m MODEL -f TEMP.wav -oj -of TEMP/output
```

Parse `output.json` into normalized timestamp rows. Use `TemporaryDirectory` so the WAV and ASR output disappear on success and failure. Persist executable versions and model identifier only, never absolute tool/model/audio paths.

Extend `.gitignore` with `*.m4a`, `*.wav`, `tracker/.local/`, and `models/` so raw or converted audio, private local configuration, and downloaded models cannot be staged accidentally.

- [ ] **Step 4: Implement centralized quality policy**

Store exact version-1 thresholds from the approved design in YAML. `quality_decision` must distinguish `all`, `text_only`, and `none`; Task 7 maps these to route-specific dimensions. Mark these values `diagnostic_internal`, not ETS standards.

- [ ] **Step 5: Install and preflight authorized local dependencies**

Run: `brew install ffmpeg whisper-cpp`

Download the official model outside Git:

```bash
mkdir -p "/Users/twinb00599242/Library/Application Support/TOEFL/models"
curl -L -o "/Users/twinb00599242/Library/Application Support/TOEFL/models/ggml-small.en.bin" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin"
shasum -a 256 "/Users/twinb00599242/Library/Application Support/TOEFL/models/ggml-small.en.bin"
```

Then run:

```bash
TOEFL_WHISPER_MODEL="/Users/twinb00599242/Library/Application Support/TOEFL/models/ggml-small.en.bin" python3 tools/transcribe_audio.py --preflight
```

Expected: prints executable versions and model identifier without printing private absolute paths.

- [ ] **Step 6: Run focused tests and commit Task 6**

Run: `python3 -m pytest tests/test_transcription.py tests/test_audio.py -q`

```bash
git add standards/ets-2026/audio-quality-policy.yaml tools/toefl_tracker/transcription.py tools/toefl_tracker/quality.py tools/transcribe_audio.py tools/toefl_tracker/audio.py tools/inspect_audio.py pyproject.toml .gitignore tests/test_transcription.py tests/test_audio.py
git commit -m "feat: add private local TOEFL transcription"
```

---

### Task 7: TOEFL Transcript Role Mapping and Reliable Speaking Evidence

**Files:**
- Create: `tools/toefl_tracker/role_mapping.py`
- Create: `tools/prepare_speaking_session.py`
- Modify: `tools/toefl_tracker/speaking.py`
- Modify: `tools/register_speaking_session.py`
- Create: `tests/test_role_mapping.py`
- Modify: `tests/test_speaking.py`
- Test: `tests/fixtures/audio/listen-repeat-transcript.json`
- Test: `tests/fixtures/audio/interview-transcript.json`

**Interfaces:**
- Produces: `infer_toefl_role_map(task_type: str, transcript_rows: Sequence[Mapping]) -> RoleMapResult`, where every mapped row stores item, role, start, end, text, confidence, and `role_reason`.
- `prepare_speaking_session.py` accepts `--audio`, `--task-type`, and `--output-dir`; it writes `audio-inspection.json`, `transcript-segments.yaml`, `segments.yaml`, and `source-reference.txt` for coach review without registering a formal session.
- Speaking registration requires `usable: true`, a complete confirmed mapping, and event dimensions contained in `reliable_dimensions`.

- [ ] **Step 1: Add failing four-question, seven-repeat, and ambiguity tests**

```python
def test_seven_repeat_pairs_are_inferred_without_voice_biometrics(lr_transcript):
    result = infer_toefl_role_map("listen_and_repeat", lr_transcript)
    assert [(row.item, row.role) for row in result.rows] == expected_pairs(7)
    assert all(row.role_reason in {"expected_item_order", "repeat_similarity"} for row in result.rows)
    assert result.requires_confirmation is False

def test_four_interview_pairs_use_question_answer_structure(interview_transcript):
    result = infer_toefl_role_map("take_an_interview", interview_transcript)
    assert [(row.item, row.role) for row in result.rows] == expected_pairs(4)
    assert result.requires_confirmation is False

def test_missing_or_overlapping_turns_return_only_ambiguous_rows(interview_transcript):
    result = infer_toefl_role_map("take_an_interview", remove_answer(interview_transcript, item=2))
    assert result.requires_confirmation is True
    assert {row.item for row in result.ambiguous_rows} == {2}

def test_unreliable_dimension_blocks_counted_event(speaking_context):
    speaking_context.attempt["reliable_dimensions"] = ["content", "grammar"]
    event = speaking_context.event(code="SPK-PRONUNCIATION")
    with pytest.raises(ValidationError, match="reliable dimension"):
        validate_speaking_assessment(**speaking_context.args(event))
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/test_role_mapping.py tests/test_speaking.py -q`

Expected: role-mapping APIs and reliable-dimension checks are absent.

- [ ] **Step 3: Implement transcript-first mapping**

The mapper uses only chronological transcript text, task type, expected item count, question form, relative answer length, and normalized token similarity. It must not inspect pitch, gender, or stored voice identity. Exact seven/four structure with supported pair evidence returns high confidence. Missing turns, overlaps, extra speakers, wrong item count, or unsupported structure return medium/low confidence and only those rows require confirmation.

The preparation CLI writes artifacts but never creates a formal attempt. It hashes the source path into an opaque reference and never copies the source media.

- [ ] **Step 4: Enforce reliability at formal registration**

Map `all` to the route-relevant dimensions and `text_only` to `content`, `grammar`, `vocabulary`, plus `reconstruction` for Listen and Repeat. Reject `usable: false`. Every counted timestamp must be fully inside a confirmed learner row and the taxonomy dimension must be reliable.

- [ ] **Step 5: Run focused tests and commit Task 7**

Run: `python3 -m pytest tests/test_role_mapping.py tests/test_speaking.py tests/test_transcription.py -q`

```bash
git add tools/toefl_tracker/role_mapping.py tools/prepare_speaking_session.py tools/toefl_tracker/speaking.py tools/register_speaking_session.py tests/test_role_mapping.py tests/test_speaking.py tests/fixtures/audio/listen-repeat-transcript.json tests/fixtures/audio/interview-transcript.json
git commit -m "feat: infer TOEFL speakers from transcript structure"
```

---

### Task 8: Update Coach Skills and Workflow Contracts

**Files:**
- Modify: `AGENTS.md`
- Modify: `.agents/skills/toefl-writing-coach/SKILL.md`
- Modify: `.agents/skills/toefl-speaking-coach/SKILL.md`
- Modify: `.agents/skills/toefl-speaking-coach/references/audio-intake.md`
- Modify: `.agents/skills/toefl-speaking-coach/references/listen-and-repeat.md`
- Modify: `.agents/skills/toefl-speaking-coach/references/take-an-interview.md`
- Modify: `tests/test_agents_contract.py`
- Modify: `tests/test_writing_skill_contract.py`
- Modify: `tests/test_speaking_skill_contract.py`
- Modify: `tests/skill-evals/speaking/scenarios.md`
- Modify: `tests/skill-evals/speaking/evaluation.md`

**Interfaces:**
- Consumes: Writing CLI, preparation CLI, registration CLI, taxonomy, and rebuild/audit commands from Tasks 3–7.
- Produces: coach instructions that use transcript-first mapping, ask only about ambiguous rows, and persist through canonical registration.

- [ ] **Step 1: Read and apply `superpowers:writing-skills` before editing skill files**

The task implementer must read that skill completely and preserve concise progressive disclosure.

- [ ] **Step 2: Add failing contract tests for the new workflow**

```python
def test_writing_skill_uses_dedicated_registration_gate():
    text = WRITING_SKILL.read_text(encoding="utf-8")
    assert "tools/register_writing_attempt.py" in text

def test_speaking_skill_is_transcript_first_without_voice_biometrics():
    text = SPEAKING_SKILL.read_text(encoding="utf-8")
    assert "tools/prepare_speaking_session.py" in text
    assert "逐字稿" in text or "transcript" in text
    assert "voiceprint" not in text.lower()

def test_audio_intake_asks_only_for_ambiguous_mapping_confirmation():
    text = AUDIO_INTAKE.read_text(encoding="utf-8")
    assert "only ambiguous" in text.lower()
```

- [ ] **Step 3: Verify RED**

Run: `python3 -m pytest tests/test_agents_contract.py tests/test_writing_skill_contract.py tests/test_speaking_skill_contract.py -q`

Expected: dedicated Writing CLI and transcript-preparation instructions are missing.

- [ ] **Step 4: Update the skills and fresh-context evaluation contract**

The Speaking workflow must read: inspect → local transcript → TOEFL structure mapping → ask only ambiguous rows → assess reliable dimensions → register. It must state that no voiceprint/general diarization is required, raw audio stays external, and a partial/incomplete mapping is not a formal session. Writing must register only through the dedicated gate. Keep first-round feedback and no-section-band constraints unchanged.

Add a fresh scenario containing a clear continuous four-question transcript that should map without confirmation and an interrupted scenario that should ask only about one ambiguous item.

- [ ] **Step 5: Validate both skills and run contract tests**

Run:

```bash
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-writing-coach
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-speaking-coach
python3 -m pytest tests/test_agents_contract.py tests/test_writing_skill_contract.py tests/test_speaking_skill_contract.py -q
```

- [ ] **Step 6: Commit Task 8**

```bash
git add AGENTS.md .agents/skills/toefl-writing-coach/SKILL.md .agents/skills/toefl-speaking-coach/SKILL.md .agents/skills/toefl-speaking-coach/references/audio-intake.md .agents/skills/toefl-speaking-coach/references/listen-and-repeat.md .agents/skills/toefl-speaking-coach/references/take-an-interview.md tests/test_agents_contract.py tests/test_writing_skill_contract.py tests/test_speaking_skill_contract.py tests/skill-evals/speaking/scenarios.md tests/skill-evals/speaking/evaluation.md
git commit -m "docs: route TOEFL coaching through hardened intake"
```

---

### Task 9: Migrate Real Tracker and Verify the Complete Workflow

**Files:**
- Create: `tracker/writing/attempts/W-AD-20260731-001/events.jsonl`
- Create: `tracker/speaking/dashboard.csv`
- Create: `tracker/speaking/profile.md`
- Modify: `tracker/writing/error-events.jsonl`
- Modify: `tracker/writing/dashboard.csv`
- Modify: `tracker/writing/profile.md`
- Modify: `tests/test_end_to_end.py`
- Create: `tests/test_real_tracker.py`
- Create: `.superpowers/sdd/2026-08-02-toefl-integrity-hardening/audio-smoke-report.md` (ignored process artifact, not committed)

**Interfaces:**
- Consumes: migration, rebuild, audit, transcription, role mapping, and skill workflow from all earlier tasks.
- Produces: migrated real canonical data, clean derived artifacts, and final end-to-end evidence.

- [ ] **Step 1: Add invariant tests before migrating real data**

```python
def test_real_tracker_preserves_the_historical_writing_record():
    attempt = read_yaml(ROOT / "tracker/writing/attempts/W-AD-20260731-001/attempt.yaml")
    events = read_jsonl(ROOT / "tracker/writing/attempts/W-AD-20260731-001/events.jsonl")
    assert attempt["word_count"] == 183
    assert len(events) == 7
    assert {row["attempt_id"] for row in events} == {"W-AD-20260731-001"}
    assert formal_count(ROOT, "writing") == 1
    assert formal_count(ROOT, "speaking") == 0
```

- [ ] **Step 2: Verify RED because the canonical sidecar is not yet present**

Run: `python3 -m pytest tests/test_real_tracker.py -q`

Expected: fails because the historical attempt lacks `events.jsonl`.

- [ ] **Step 3: Dry-run, apply, rebuild, and audit the real tracker**

Run:

```bash
python3 tools/migrate_event_sidecars.py --root . --dry-run
python3 tools/migrate_event_sidecars.py --root . --apply
python3 tools/rebuild_reports.py --root . --modality all
python3 tools/validate_tracker.py --root .
```

Expected dry-run: one Writing sidecar, seven events, no orphan/duplicate/conflict. Expected audit: exit 0. Run rebuild a second time and assert `git diff` is unchanged to prove idempotency.

- [ ] **Step 4: Run the authorized real `.m4a` private smoke**

With `TOEFL_WHISPER_MODEL` set, select the clearer available user file, preferring `/Users/twinb00599242/Downloads/sss.m4a`. Run preparation into a temporary directory outside the repository:

```bash
python3 tools/prepare_speaking_session.py --audio /Users/twinb00599242/Downloads/sss.m4a --task-type take_an_interview --output-dir /private/tmp/toefl-audio-smoke
```

Inspect transcript and mapping, record whether the file actually contains a complete four-question Interview, and write the result to the ignored audio smoke report. If it is not the correct TOEFL structure, do not fabricate a formal session: mark Task 9 BLOCKED and request a complete seven-item Listen and Repeat or four-question Interview recording from the user. Confirm no `.m4a`, `.wav`, private absolute path, or model path appears in tracked files.

- [ ] **Step 5: Run final automated verification for the task**

Run:

```bash
python3 -m pytest -q
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-writing-coach
python3 /Users/twinb00599242/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/toefl-speaking-coach
python3 tools/rebuild_reports.py --root . --modality all
python3 tools/validate_tracker.py --root .
git diff --check
git status --short
```

Expected: all tests and validators pass; the second rebuild is idempotent; only intended tracker migrations and tests are changed before commit.

- [ ] **Step 6: Commit Task 9**

```bash
git add tracker tests/test_end_to_end.py tests/test_real_tracker.py
git commit -m "test: migrate and verify TOEFL coaching tracker"
```

---

## Plan Completion Checks

After all nine task reviews pass, the controller must:

1. Generate a whole-branch review package from `174efb3` to `HEAD`.
2. Dispatch the final reviewer on the most capable available model, pointing it at every deferred minor in this plan's SDD ledger.
3. If findings remain, perform the single final-review fix wave and one scoped re-review allowed by Subagent-Driven Development.
4. Re-run the full verification commands from Task 9 with fresh output.
5. Confirm the real tracker remains Writing 1 / 183 words / 7 events and Speaking 0.
6. Use `superpowers:finishing-a-development-branch` only after the final review is clean or all non-load-bearing residuals have explicit rulings.
