#!/usr/bin/env python3
"""Build a voice pack from a Piper voice model.

    pip install piper-tts
    python scripts/build_voicepack.py --model de_DE-kerstin-low.onnx --lang de \
        --id de-kerstin --name "Kerstin (Deutsch)" --license CC0-1.0 \
        --source "Piper voice de_DE-kerstin-low, dataset rhasspy/dataset-voice-kerstin"

Piper is only needed here. EtherDigits itself plays the finished clips.
Pick voices whose licence allows sharing the generated audio.
"""

from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etherdigits.voicepack import TOKENS, read_wav  # noqa: E402

# What each token sounds like. "zwo" instead of "zwei" is how German radio
# keeps 2 and 3 apart; numbers stations did the same.
TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "0": "Null.", "1": "Eins.", "2": "Zwo.", "3": "Drei.", "4": "Vier.",
        "5": "Fünf.", "6": "Sechs.", "7": "Sieben.", "8": "Acht.", "9": "Neun.",
        "attention": "Achtung!", "groups": "Gruppen.", "repeat": "Wiederholung.",
        "separator": "Trennung.", "no_message": "Keine Meldung.", "end": "Ende.",
    },
    "en": {
        "0": "Zero.", "1": "One.", "2": "Two.", "3": "Three.", "4": "Four.",
        "5": "Five.", "6": "Six.", "7": "Seven.", "8": "Eight.", "9": "Nine.",
        "attention": "Attention!", "groups": "Groups.", "repeat": "I repeat.",
        "separator": "Break.", "no_message": "No message.", "end": "End of transmission.",
    },
}

FILE_NAMES = {t: f"{t}.wav" for t in TOKENS}


def trim(audio: np.ndarray, rate: int, threshold: float = 0.02) -> np.ndarray:
    """Cut silence at both ends, keep a short margin, fade the edges."""
    level = np.abs(audio)
    peak = float(level.max()) if len(level) else 0.0
    if peak <= 0:
        return audio
    loud = np.nonzero(level > peak * threshold)[0]
    start = max(0, loud[0] - int(0.02 * rate))
    end = min(len(audio), loud[-1] + int(0.05 * rate))
    out = audio[start:end].copy()
    n = min(len(out) // 2, int(0.01 * rate))
    if n:
        ramp = np.linspace(0, 1, n, dtype=np.float32)
        out[:n] *= ramp
        out[-n:] *= ramp[::-1]
    return out


def level_match(audio: np.ndarray, rms_db: float = -18.0, peak_db: float = -1.0) -> np.ndarray:
    """Same loudness for every clip, without clipping."""
    rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
    if rms <= 0:
        return audio
    gain = 10 ** (rms_db / 20) / rms
    peak = float(np.max(np.abs(audio))) * gain
    limit = 10 ** (peak_db / 20)
    if peak > limit:
        gain *= limit / peak
    return (audio * gain).astype(np.float32)


def write_wav(path: Path, audio: np.ndarray, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True, help="Piper .onnx model (the .onnx.json must sit next to it)")
    p.add_argument("--lang", required=True, choices=sorted(TEXTS))
    p.add_argument("--id", required=True, help="pack id, e.g. de-kerstin")
    p.add_argument("--name", required=True)
    p.add_argument("--license", required=True, help="licence of the voice, e.g. CC0-1.0")
    p.add_argument("--source", required=True, help="where the voice comes from")
    p.add_argument("--out", help="output folder (default: voices/<id>)")
    p.add_argument("--length-scale", type=float, default=1.15, help="above 1 speaks slower (default: 1.15)")
    args = p.parse_args()

    from piper import PiperVoice, SynthesisConfig

    voice = PiperVoice.load(args.model)
    config = SynthesisConfig(length_scale=args.length_scale, noise_scale=0.5, noise_w_scale=0.6)
    out = Path(args.out) if args.out else Path(__file__).resolve().parent.parent / "voices" / args.id
    out.mkdir(parents=True, exist_ok=True)

    clips = {}
    for token, text in TEXTS[args.lang].items():
        raw = out / f".raw-{token}.wav"
        with wave.open(str(raw), "wb") as w:
            voice.synthesize_wav(text, w, syn_config=config)
        audio, rate = read_wav(raw)
        raw.unlink()
        write_wav(out / FILE_NAMES[token], level_match(trim(audio, rate)), rate)
        clips[token] = FILE_NAMES[token]
        print(f"{token:12} {text}")

    meta = {
        "id": args.id,
        "name": args.name,
        "language": args.lang,
        "license": args.license,
        "source": args.source,
        "generator": f"Piper ({Path(args.model).name}), scripts/build_voicepack.py",
        "clips": clips,
    }
    (out / "pack.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"voice pack written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
