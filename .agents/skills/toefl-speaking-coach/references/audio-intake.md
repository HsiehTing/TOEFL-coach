# Audio Intake

## Technical inspection

Record absolute source reference, duration, codec, sample rate, channels, mean dBFS, peak dBFS, clipping, and decodability. These are recording facts, not language judgments.

## Segment map

For every required item, store one examiner segment and one learner segment with start, end, role, item number, and confidence. A low- or medium-confidence role requires explicit learner confirmation.

## Quality decisions

- Undecodable: stop content assessment.
- Missing prompt or answer: assess only identifiable material and do not register a complete formal session.
- Distortion or clipping: withhold affected pronunciation judgments.
- Low level but intelligible: state reduced confidence; do not count volume as a speaking error.
