# Bug Capture decision scenarios

## 1. Complete normal-use defect — capture

The learner states the intended outcome, expected and observed behavior, a preceding operation, and the affected flow. The workflow must create the immutable capture before any diagnosis or code change.

## 2. Incomplete report — ask

The learner says only that “the drill is broken.” The workflow must ask for the intended outcome, expected/observed behavior, and at least one operation. It must not create a Bug ID.

## 3. Implementation-time test failure — do not capture

A developer sees a failing regression test while changing code. This is development evidence, not a learner normal-use defect, so it must not create a Bug ID.

## 4. Intended fail-closed capability gap — do not capture

A new Email source context has no approved context-safe drill template. The queue must show `blocked_by_template`; this is intentional and must not create a Bug ID.
