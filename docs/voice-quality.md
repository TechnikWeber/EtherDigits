# Kerstin pronunciation repair

Investigated on 2026-10-29 after the German female voice produced unintelligible
sounds after the interval signal. The intended opening is “Achtung” followed
by the callsign, normally “vier sieben zwo”.

## Reproduced cause

`scripts/build_voicepack.py` originally synthesized each token in isolation.
With the official `de_DE-kerstin-low` model, the duration output for “Vier.”
assigns exactly 256 samples to every input ID: 15 IDs yield only 0.240 seconds
at 16 kHz. This includes padding and sentence markers, leaving very little
speech. Most other digits exhibit the same collapse. Changing length scale
from 1.0 to 2.0 does not repair “Vier.”. This occurs in raw synthesis, before
trimming, normalization, resampling or playback. Disabling ONNX optimization
does not change the result. The phoneme mapping and German language setting
are correct; the model SHA-256 matches the upstream download:

`d352a7641892cebf2903859af94e9ba81a141110215fe3943bcda7f7da401b7a`

Adding context on both sides of each token restores varied, longer phoneme
durations. The final clips are cut at the model's phoneme boundaries, with
small margins limited to the adjoining delimiters, then trimmed and levelled.
The model and speaker are unchanged. Timing and acoustic noise are disabled
during this contextual build to avoid random variation.

This is consistent with a training-data limitation, rather than a playback
bug: the published Kerstin metadata contains 1,374 utterances, zero one-word
utterances, and only seven with at most three words (median: eleven words).
Piper's maintainer describes lack of short utterances as a cause of this type
of failure. That explains the likely training origin; it is not a controlled
retraining experiment proving the contribution of each training choice.

- [Kerstin training metadata](https://github.com/rhasspy/dataset-voice-kerstin/blob/master/metadata.csv)
- [Piper discussion of unintelligible short phrases](https://github.com/OHF-Voice/piper1-gpl/issues/79)
- [Official Kerstin model](https://huggingface.co/rhasspy/piper-voices/tree/main/de/de_DE/kerstin/low)

## Validation and limits

- The alignment regression tests reject collapsed, invalid or missing word
  boundaries and verify that extraction excludes surrounding context speech.
- An independent local Vosk recognizer (`vosk-model-small-de-0.15`, unrestricted
  vocabulary, no expected transcript supplied) was run on all ten digits and
  all six announcement clips, with 350 ms gaps. The corrected pack produced:
  “null eins zwei drei vier fünf sechs sieben acht neun achtung gruppen
  wiederholung trennung keine meldung ende”. The original pack failed this
  comparison badly. Vosk normalizes spoken “zwo” to “zwei”.
- A second sequence, `472 098 365 182 690 537 426 809`, was also recognized in
  order; the last “neun” was transcribed as “neuen”. This is a recognition aid,
  not a claim of perfect human intelligibility or perfect ASR accuracy.
- Ramona and Eva were evaluated as alternative German female Piper voices.
  These builds also had recognition/pronunciation problems, so neither was
  added to the shipped voice selection in this repair.

The automated checks do not replace listening. Review every token and a full
transmission before publication, particularly distinctions between zero/nine,
two/three and five/six. Local before/after WAV previews are generated in the
ignored `out/voice-review/` directory during this investigation.
