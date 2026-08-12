---
name: tracker-maintenance
description: Validate and rebuild derived TOEFL tracker reports, plans, queues, progress views, and calibration checks. Use when a user asks to inspect tracker integrity, regenerate derived coaching views, rebuild reports, or run a maintainer calibration check; do not use to create learner attempts or alter immutable records.
---

# Tracker Maintenance

Use this skill for derived tracker maintenance only. It may rebuild reports and views, but it must not create, overwrite, or hand-edit learner attempts, revisions, transcripts, events, or bug records.

## Scope and preflight

1. Identify the requested modality or derived view. If the user did not name one, report the full maintenance scope before rebuilding.
2. Run `python3 tools/validate_tracker.py` first. Stop and report any integrity failure; do not rebuild to hide invalid source data.
3. Treat `tools/register_attempt.py` as an internal compatibility entry point. Use the Writing or Speaking coach skills for any learner record registration.

## Derived rebuilds

- Reports: `python3 tools/rebuild_reports.py --modality writing|speaking|all`.
- Training plan: `python3 tools/rebuild_training_plan.py`.
- Practice queue: `python3 tools/rebuild_practice_queue.py`.
- Writing progress and revision learning: `python3 tools/rebuild_progress_overview.py` and `python3 tools/rebuild_revision_learning.py`.
- Speaking progress: `python3 tools/rebuild_speaking_progress_overview.py`.
- Writing calibration audit: `python3 tools/validate_writing_calibration.py`; report its output without changing learner assessment history.

Run only the requested rebuilds. After writes, run `python3 tools/validate_tracker.py` again and report which derived files were refreshed.

## Boundaries

- Do not use this skill for legacy conversion; use `legacy-tracker-migration`.
- Do not use it for bug capture or bug resolution.
- If a rebuild would overwrite a user-maintained derived artifact outside the standard tracker paths, stop and request explicit approval.
