# Audio Intake

## Technical inspection

Record absolute source reference, duration, codec, sample rate, channels, mean dBFS, peak dBFS, clipping, and decodability. These are recording facts, not language judgments.

## Segment map

First create a local transcript with `tools/prepare_speaking_session.py`, then map the TOEFL prompt/answer structure. For every required item, store one examiner segment and one learner segment with start, end, role, item number, and confidence. Ask only ambiguous rows for confirmation; clear rows do not require confirmation. A low- or medium-confidence role requires explicit learner confirmation.

This is transcript-first structure mapping, not voiceprint identification or general-purpose diarization. Keep raw audio at its original path and store only the source reference plus derived artifacts. An incomplete map cannot be registered as a formal session.

## Quality decisions

- Undecodable: stop content assessment.
- Missing prompt or answer: assess only identifiable material and do not register a complete formal session.
- Distortion or clipping: withhold affected pronunciation judgments.
- Low level but intelligible: state reduced confidence; do not count volume as a speaking error.
