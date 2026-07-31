# Writing Error Taxonomy

| Code | Scope | Count when |
|---|---|---|
| `GRAM-ARTICLE` | Shared | Article selection or omission is incorrect. |
| `GRAM-NEGATION` | Shared | Negation changes or obscures intended meaning. |
| `GRAM-CLAUSE` | Shared | Clause connection, fragment, run-on, or paired `although` + `but` is incorrect. |
| `GRAM-AGREEMENT` | Shared | Subject–verb or noun agreement is incorrect. |
| `LEX-WORDFORM` | Shared | The selected part of speech or derived form is incorrect. |
| `LEX-COLLOCATION` | Shared | Word combination is unnatural or changes clarity. |
| `MECH-SPELLING` | Shared | Spelling error is not a harmless timed typo. |
| `MECH-PUNCTUATION` | Shared | Punctuation damages sentence boundaries or meaning. |
| `EMAIL-PURPOSE` | Email | The communicative purpose is missing or unclear. |
| `EMAIL-MISSING-POINT` | Email | A required prompt point is absent. |
| `EMAIL-REGISTER` | Email | Tone does not fit the relationship or context. |
| `EMAIL-POLITENESS` | Email | Social convention makes the request or response inappropriate. |
| `EMAIL-ORGANIZATION` | Email | Information order obstructs the communicative goal. |
| `EMAIL-ACTION` | Email | A request, proposal, refusal, or criticism is formulated ineffectively. |
| `DISCUSSION-ALIGNMENT` | Discussion | The response answers a materially altered question. |
| `DISCUSSION-POSITION` | Discussion | The writer's position is absent or internally inconsistent. |
| `DISCUSSION-BORROWING` | Discussion | Language or reasoning relies excessively on the stimulus. |
| `DISCUSSION-CONTRIBUTION` | Discussion | The post adds no meaningful original contribution. |
| `DISCUSSION-ELABORATION` | Discussion | An explanation or example is incomplete or unclear. |
| `DISCUSSION-SUPPORT` | Discussion | A claim lacks relevant reasons, details, or causal connection. |

Use `must_fix` for meaning/task-completion failures, `should_fix` for recurring clarity or control problems, and `polish` for optional sophistication. Only the first two levels enter rates.
