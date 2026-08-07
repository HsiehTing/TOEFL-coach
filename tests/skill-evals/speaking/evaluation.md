# Speaking Skill Evaluation Contract

## Scenario A

- Does not formally score before examiner/learner mapping is complete.
- Identifies the ambiguous segments and asks only for their confirmation.
- Uses transcript-first TOEFL structure mapping and does not require voiceprint or general speaker diarization.
- Preserves clear rows while awaiting confirmation for one ambiguous row.
- Does not label distortion, low volume, or clipping as pronunciation errors.

## Scenario 0

- Runs `tools/prepare_speaking_session.py` and maps all four clear Interview pairs without unnecessary confirmation.
- Keeps raw audio external and uses only derived transcript, segment, inspection, and source-reference artifacts.

## Scenario B

- Treats all seven items as one formal session.
- Measures sentence reconstruction accuracy and intelligibility.
- Uses omission, addition, substitution, word order, stress, rhythm, and intonation evidence.
- Does not score idea development or Interview elaboration.

## Scenario C

- Treats all four questions as one formal session.
- Labels the result diagnostic rather than official task or section score.
- Evaluates directness, relevance, elaboration, coherence, grammar, vocabulary, fluency, prosody, and intelligibility.
- Gives no more than three priorities.
- Does not provide four complete model answers before the learner re-records.
