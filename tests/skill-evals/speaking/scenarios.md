# Speaking Coach Scenarios

## Scenario 0 — Clear transcript-first mapping

A continuous four-question Interview transcript has clear alternating prompt and learner turns. The coach should map all four pairs without asking the learner to identify speakers and should proceed to quality-gated diagnostic assessment.

| Question | Transcript pattern | Confidence |
|---|---|---|
| 1 | Examiner prompt, then a developed learner answer | high |
| 2 | Examiner prompt, then a developed learner answer | high |
| 3 | Examiner prompt, then a developed learner answer | high |
| 4 | Examiner prompt, then a developed learner answer | high |

The coach uses `tools/prepare_speaking_session.py`, not voiceprint or general speaker diarization.

## Scenario 0b — One interrupted ambiguous item

The same four-question structure is clear except for one interrupted middle answer whose role is uncertain. The coach asks for confirmation of that one item only, preserves the three clear pairs, and does not request confirmation for the rest.

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
