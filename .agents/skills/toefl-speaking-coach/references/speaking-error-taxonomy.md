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
| `UNCLASSIFIED` | Taxonomy review | Use only as `polish` with `taxonomy_review_required: true`; it never enters rates or status. |

Do not create pronunciation, stress, rhythm, intonation, fluency, or intelligibility events from transcript-only evidence. Every counted event requires an exact learner-transcript excerpt and `must_fix` or `should_fix`; optional refinement is `polish`.
