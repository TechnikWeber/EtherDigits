# EtherDigits

<p>
  <img alt="Status: alpha" src="https://img.shields.io/badge/status-alpha-orange">
  <img alt="Platform: Linux | Windows | macOS" src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-blue">
  <img alt="Voices: Deutsch | English" src="https://img.shields.io/badge/voices-Deutsch%20%7C%20English-informational">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"></a>
</p>

**Run your own numbers station.** EtherDigits reads out groups of digits in the
format shortwave numbers stations have used for decades: an interval signal, the
station's callsign, the number of groups, the message, a repeat, and the end.

```
[interval signal]
ATTENTION 472 472 472
GROUPS 3 3
21347 47890 11203
REPEAT 21347 47890 11203
END
```

> Version 0.1 is the core: voices, transmission format and audio files. The
> scheduler, web interface, radio control and the offline pad tool follow; see
> [docs/plan.md](docs/plan.md).

## Install

Python 3.10 or newer.

```sh
git clone https://github.com/TechnikWeber/EtherDigits.git
cd EtherDigits
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
```

For MP3 output, install `ffmpeg` or `lame`. WAV works without either.

## Use

```sh
python -m etherdigits voices                                   # list voices
python -m etherdigits render -m "21347 47890 11203" -o tx.wav  # German, default voice
python -m etherdigits render --voice en --random 10 --effect radio -o tx.mp3
python -m etherdigits render -o null.wav                       # "no message"
python -m etherdigits render -m "21347 47890"                  # transcript only
```

| Option | What it does |
|---|---|
| `-m GROUPS` | a message; repeat `-m` for several messages in one transmission |
| `--random N` | a test message of N random groups |
| `--voice` | voice id (`de-kerstin`, `de-thorsten`, `en-ljspeech`), language (`de`, `en`) or a folder |
| `--callsign` | station callsign, digits (default `472`) |
| `--repeats` | how often each message is read (default 2) |
| `--interval` | `melody`, `beeps` or `none` |
| `--group-twice` | read every group twice |
| `--pad random\|zero` | fill a short last group instead of failing |
| `--effect radio` | narrow band, a little drive and noise, like AM on shortwave |
| `--format-file` | all format settings from JSON, see [examples/format.json](examples/format.json) |

## How numbers stations keep messages secret

Not with a lookup table: replacing each letter by a number is broken in minutes
by counting how often each number appears. Numbers stations use a **one-time
pad**:

1. Letters become digits with a *straddling checkerboard*: frequent letters get one
   digit, rare ones two. This table is not secret, it only keeps the message short.
2. A random key of the same length is added digit by digit, without carry:
   `3+8=1`, `7+2=9`. Sender and receiver hold identical pads of key pages.
3. The result is read out in groups of five.

Without the pad page every message of that length is equally likely, so the
transmission cannot be broken, not even in principle. The rules are strict: the
key must be truly random, as long as the message, used once and then destroyed.
Reusing pages is how the Soviet traffic in the VENONA project was read.

EtherDigits will ship the pad tool separately (stage 2 of the plan), so the
station itself never holds keys.

## Voices

Three voices come with EtherDigits: two German, one English, all free to share. You can
add your own recordings; see [voices/README.md](voices/README.md).

## Legal

Encrypted or obscured content is not allowed on amateur radio bands. Use an
internet stream, a dummy load, local playback, or a service licensed for it.

## Development

```sh
.venv/bin/python -m unittest
```

New voice packs are built from Piper models with `scripts/build_voicepack.py`
(needs `pip install piper-tts`).

## License

[MIT](LICENSE). The voice packs are CC0 or public domain, see [voices/README.md](voices/README.md).
