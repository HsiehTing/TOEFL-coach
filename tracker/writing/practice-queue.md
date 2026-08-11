# Writing Practice Queue

Diagnostic planning artifact; drills and transfers are not TOEFL section-band estimates.

## `PQ-01-DRILL` — `targeted_drill`
- Plan: `PLAN-W-AD-20260809-002`
- Route: `academic_discussion`
- Targets: `GRAM-CLAUSE`, `GRAM-AGREEMENT`
- Generate an evidence-linked drill, complete it without viewing the answer key, then record the result as a targeted drill.
- Source: `W-AD-20260809-002`; 8 items; threshold: 80%
- Status: `blocked_by_pack_drift` — A prior drill uses a different target-code set; generate the current plan's pack.

## `PQ-02-TRANSFER` — `fresh_transfer_check`
- Plan: `PLAN-W-AD-20260809-002`
- Route: `academic_discussion`
- Targets: `GRAM-CLAUSE`, `GRAM-AGREEMENT`
- After meeting the drill threshold, complete one new formal prompt on this route. Confirm relevant opportunities; do not reuse the source prompt.
- Depends on: `PQ-01-DRILL`
- Status: `blocked_by_pack_drift` — A prior drill uses a different target-code set; generate the current plan's pack.

## `PQ-03-DRILL` — `targeted_drill`
- Plan: `PLAN-W-EM-20260808-001`
- Route: `email`
- Targets: `GRAM-CLAUSE`, `GRAM-AGREEMENT`
- Generate an evidence-linked drill, complete it without viewing the answer key, then record the result as a targeted drill.
- Source: `W-EM-20260808-001`; 8 items; threshold: 80%
- Status: `deferred_by_priority` — Finish or resolve the higher-priority plan `PLAN-W-AD-20260809-002` first.

## `PQ-04-TRANSFER` — `fresh_transfer_check`
- Plan: `PLAN-W-EM-20260808-001`
- Route: `email`
- Targets: `GRAM-CLAUSE`, `GRAM-AGREEMENT`
- After meeting the drill threshold, complete one new formal prompt on this route. Confirm relevant opportunities; do not reuse the source prompt.
- Depends on: `PQ-03-DRILL`
- Status: `deferred_by_priority` — Finish or resolve the higher-priority plan `PLAN-W-AD-20260809-002` first.

## `PQ-05-DRILL` — `targeted_drill`
- Plan: `PLAN-W-EM-20260805-002`
- Route: `email`
- Targets: `GRAM-CLAUSE`, `GRAM-AGREEMENT`
- Generate an evidence-linked drill, complete it without viewing the answer key, then record the result as a targeted drill.
- Source: `W-EM-20260805-002`; 8 items; threshold: 80%
- Status: `deferred_by_priority` — Finish or resolve the higher-priority plan `PLAN-W-AD-20260809-002` first.

## `PQ-06-TRANSFER` — `fresh_transfer_check`
- Plan: `PLAN-W-EM-20260805-002`
- Route: `email`
- Targets: `GRAM-CLAUSE`, `GRAM-AGREEMENT`
- After meeting the drill threshold, complete one new formal prompt on this route. Confirm relevant opportunities; do not reuse the source prompt.
- Depends on: `PQ-05-DRILL`
- Status: `deferred_by_priority` — Finish or resolve the higher-priority plan `PLAN-W-AD-20260809-002` first.
