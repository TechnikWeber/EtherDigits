# Voice packs

Each folder is one voice: a `pack.json` and one 16-bit mono WAV per word.

| Pack | Language | Voice | Licence |
|---|---|---|---|
| `de-kerstin` | German | Piper `de_DE-kerstin-low`, dataset [rhasspy/dataset-voice-kerstin](https://github.com/rhasspy/dataset-voice-kerstin) | CC0 1.0 |
| `de-thorsten` | German | Piper `de_DE-thorsten-medium`, dataset [Thorsten-Voice](https://github.com/thorstenMueller/Thorsten-Voice) | CC0 1.0 |
| `en-ljspeech` | English | Piper `en_US-ljspeech-high`, dataset [LJ Speech](https://keithito.com/LJ-Speech-Dataset/) | public domain |

The clips were generated with [Piper](https://github.com/OHF-Voice/piper1-gpl)
using `scripts/build_voicepack.py`. Piper is not part of EtherDigits.

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
