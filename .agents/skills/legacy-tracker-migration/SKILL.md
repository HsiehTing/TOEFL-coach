---
name: legacy-tracker-migration
description: Plan, review, approve, and apply compatibility or event-sidecar migration for legacy TOEFL tracker records. Use when a user asks to inspect legacy tracker issues, prepare a migration plan, approve reviewed exceptions, or apply a confirmed migration; require explicit approval before any write.
---

# Legacy Tracker Migration

Use this skill only for legacy compatibility or sidecar migration. Preserve original attempts and events; do not use it for new learner records or ordinary tracker rebuilds.

## Read-only review

1. Run `python3 tools/plan_legacy_tracker_migration.py` for the requested modality.
2. Run `python3 tools/review_legacy_tracker.py`; use an explicit output path only when the user requested a saved review.
3. For sidecars, run `python3 tools/migrate_event_sidecars.py --dry-run` before any write.
4. Present the exact affected modalities, files, incompatibilities, and proposed metadata changes. Do not infer approval from a request to inspect or plan.

## Apply only with approval

1. Require the user's explicit approval, exact modality, and a non-empty review reason before `python3 tools/approve_legacy_tracker_review.py --apply`.
2. Run `python3 tools/apply_legacy_tracker_compatibility.py --apply` only after the reviewed exceptions are approved.
3. Run `python3 tools/migrate_event_sidecars.py --apply` only after a successful dry run and explicit user approval.
4. Run `python3 tools/validate_tracker.py` after every write. Report precisely what compatibility metadata or sidecars were added; do not claim original records changed unless the CLI reports it.

## Boundaries

- Never edit legacy attempts, events, compatibility files, or migration artifacts by hand.
- Stop on a review, dry-run, or validation failure; do not use a rebuild to conceal the failure.
- Do not commit or push migration results unless the user explicitly requests it.
