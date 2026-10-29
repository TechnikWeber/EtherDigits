# Voice packs

Each folder is one voice: a `pack.json` and one 16-bit mono WAV per word.

| Pack | Language | Voice | Licence |
|---|---|---|---|
| `de-kerstin` | German | Piper `de_DE-kerstin-low`, dataset [rhasspy/dataset-voice-kerstin](https://github.com/rhasspy/dataset-voice-kerstin) | CC0 1.0 |
| `de-thorsten` | German | Piper `de_DE-thorsten-medium`, dataset [Thorsten-Voice](https://github.com/thorstenMueller/Thorsten-Voice) | CC0 1.0 |
| `en-ljspeech` | English | Piper `en_US-ljspeech-high`, dataset [LJ Speech](https://keithito.com/LJ-Speech-Dataset/) | public domain |

The clips were generated with [Piper](https://github.com/OHF-Voice/piper1-gpl)
using `scripts/build_voicepack.py`. Piper is not part of EtherDigits.

## Rebuilding Kerstin

Kerstin must be generated with sentence context. Isolated words cause this
model's duration predictor to collapse most phoneme IDs to a single 16 ms
frame, producing unintelligible digits. The builder automatically uses context
for `de_DE-kerstin-low.onnx`: it speaks each token between “Die Ansage lautet,”
and “und wird nun wiederholt.” and extracts only the token using the model's
phoneme alignments. It rejects missing alignments and collapsed durations.
Neither surrounding phrase is included in the shipped clips.

```sh
pip install 'piper-tts[alignment]==1.8.0'
python scripts/build_voicepack.py --model /path/to/de_DE-kerstin-low.onnx \
  --lang de --id de-kerstin --name 'Kerstin (Deutsch)' --license CC0-1.0 \
  --source 'Piper voice de_DE-kerstin-low; dataset https://github.com/rhasspy/dataset-voice-kerstin (CC0)' \
  --length-scale 1.3
```

The matching `.onnx.json` must be beside the model. Generation settings and the
model's SHA-256 are recorded in `pack.json`. Other models can opt into the same
method with `--context sentence`. The application still only plays WAV files;
Piper, ONNX and recognition tools are build/verification tools, not runtime
dependencies.

See [the diagnosis and validation](../docs/voice-quality.md). File-format and
alignment tests cannot establish intelligibility: always listen to all digits,
all announcement words, the callsign and mixed digit groups before a release.

## Tokens

| Token | German | English |
|---|---|---|
| `0` … `9` | Null … Neun ("zwo" for 2) | Zero … Nine |
| `attention` | Achtung | Attention |
| `groups` | Gruppen | Groups |
| `repeat` | Wiederholung | I repeat |
| `separator` | Trennung | Break |
| `no_message` | Keine Meldung | No message |
| `end` | Ende | End of transmission |

Only the digits are required. Missing words are left out of the transmission.

## Your own voice

Record the clips yourself (mono WAV, 16 bit, any sample rate), put them in a
folder with a `pack.json` like the ones here, and point EtherDigits at it:
`--voice path/to/folder`, or add the parent folder to `ETHERDIGITS_VOICES`.
