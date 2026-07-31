# Task 3 Report: Attempt and Error-Event Validation

## Change Summary

- Added tracker constants and `ValidationError` in `tools/toefl_tracker/models.py`.
- Added deterministic YAML, atomic-write, and canonical source-hash helpers in `tools/toefl_tracker/io.py`.
- Added strict attempt and error-event validation in `tools/toefl_tracker/validation.py`.
- Added the seven brief-specified validation tests in `tests/test_validation.py`.

## RED / GREEN Evidence

- RED: `python3 -m pytest tests/test_validation.py -v` failed during collection with `ModuleNotFoundError: No module named 'toefl_tracker.io'`, because the Task 3 modules did not yet exist.
- GREEN: `python3 -m pytest tests/test_validation.py -v` completed with `7 passed in 0.02s`.
- Full suite: `python3 -m pytest -v` completed with `11 passed in 0.02s`.
- Hygiene: `git diff --check` exited successfully with no output.

## Commit

- Pending creation: `feat: validate TOEFL attempt records`

## Self-Review

- Date handling uses `datetime.fromisoformat` for submissions and `date.fromisoformat` for nullable practice/verification dates, rejecting YAML-native date values where the persistent schema requires ISO strings.
- YAML reads must produce a mapping; atomic writes fsync the temporary file before replacement.
- Rubric IDs must exist in the manifest and must match either the exact task type or the speaking modality route.
- Source hashes must use the `sha256:` prefix and exactly 64 lowercase hexadecimal characters; the canonical helper normalizes CRLF and trims both source sections.
- Revision outcomes are revision-only, have an exact key set, reconcile counts, and validate their exact resolution rate.
- Counted (`must_fix`/`should_fix`) error events require a nonblank source excerpt or audio timestamp.

## Concerns

- No concerns. The implementation follows the Task 3 brief verbatim; this task intentionally does not add tracker registration or persistence workflows.
