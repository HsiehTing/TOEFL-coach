# Targeted drills and mastery

Use a targeted drill when the learner has a recurring code or a skill-family signal that needs focused practice before another full task.

- A drill is `record_type: targeted_drill`, not a formal attempt and not a revision.
- Keep the drill bounded: identify the target code/family, number of items, correct items, and the formal attempt(s) that supplied the evidence.
- Do not turn drill accuracy into a TOEFL task score or section band.
- Read `tracker/writing/mastery.md` as derived state. Keep atomic error events and their historical statuses unchanged.
- After two unresolved revision rounds, recommend a drill followed by a new-prompt transfer check. The learner supplies their own work; first-round coaching does not provide a complete model answer.
- Generate a stable evidence-linked pack with `generate_writing_drill.py`; the learner version never contains the answer key.
- A transfer must link `source formal → generated pack → targeted drill → new formal attempt`. The coach may suggest opportunities, but must record confirmed counts rather than infer transfer from a response alone.

Suggested progression: `identified` → `practised` → `provisional` → `transferred` → `controlled`; a new counted error after control is `relapsed`.
