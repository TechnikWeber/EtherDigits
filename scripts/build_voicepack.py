#!/usr/bin/env python3
"""Build a voice pack from a Piper voice model.

    pip install 'piper-tts[alignment]==1.8.0'
    python scripts/build_voicepack.py --model de_DE-kerstin-low.onnx --lang de \
        --id de-kerstin --name "Kerstin (Deutsch)" --license CC0-1.0 \
        --source "Piper voice de_DE-kerstin-low, dataset rhasspy/dataset-voice-kerstin"

Piper is only needed here. EtherDigits itself plays the finished clips.
Pick voices whose licence allows sharing the generated audio.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etherdigits.voicepack import TOKENS  # noqa: E402

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

# Some voices collapse phoneme durations on isolated words. Speak the token
# inside a sentence, then use the model's actual alignments to remove context.
CONTEXT = {
    "de": ("Die Ansage lautet,", "und wird nun wiederholt."),
    "en": ("The announcement is,", "and will now be repeated."),
}
CONTEXT_MODELS = {"de_DE-kerstin-low"}


def extract_aligned_word(audio: np.ndarray, widths: np.ndarray, start_id: int,
                         end_id: int, rate: int, hop_length: int) -> np.ndarray:
    """Cut only the target word, retaining at most 20/40 ms of its delimiters."""
    widths = np.asarray(widths)
    if (widths.ndim != 1 or not np.isfinite(widths).all()
            or (widths < 0).any() or (widths != np.floor(widths)).any()
            or int(widths.sum()) != len(audio)
            or not 0 < start_id < end_id < len(widths)):
        raise ValueError("Invalid phoneme alignments; refusing to cut a voice clip")
    if np.max(widths[start_id:end_id]) <= hop_length:
        raise ValueError("Collapsed phoneme durations; this word needs a different voice or context")
    start = int(widths[:start_id].sum())
    end = int(widths[:end_id].sum())
    # Never extend beyond the adjacent delimiter (space/comma) into context words.
    before = min(int(0.02 * rate), int(widths[start_id - 1]))
    after = min(int(0.04 * rate), int(widths[end_id]))
    return audio[start - before:end + after].copy()


def contextual_audio(voice, text: str, lang: str, config) -> tuple[np.ndarray, int]:
    """Synthesize with surrounding context; return only the requested word(s)."""
    def phonemes(phrase: str) -> list[str]:
        sentences = voice.phonemize(phrase)
        if len(sentences) != 1:
            raise ValueError("Voice-pack phrases must contain exactly one sentence")
        result = sentences[0]
        missing = set(result) - voice.config.phoneme_id_map.keys()
        if missing:
            raise ValueError(f"Voice is missing phonemes: {sorted(missing)!r}")
        return result

    prefix_text, suffix_text = CONTEXT[lang]
    prefix = phonemes(prefix_text) + [" "]
    word = phonemes(text)
    while word and word[-1] in ".!?":
        word = word[:-1]
    if not word:
        raise ValueError("The voice-pack word is empty")
    suffix = [",", " "] + phonemes(suffix_text)
    eos_size = len(voice.config.phoneme_id_map["$"])
    start_id = len(voice.phonemes_to_ids(prefix)) - eos_size
    end_id = len(voice.phonemes_to_ids(prefix + word)) - eos_size
    ids = voice.phonemes_to_ids(prefix + word + suffix)
    result = voice.phoneme_ids_to_audio(ids, config, include_alignments=True)
    if not isinstance(result, tuple) or result[1] is None or len(result[1]) != len(ids):
        raise ValueError("Phoneme alignments unavailable; install piper-tts[alignment]==1.8.0")
    audio, widths = result
    rate = voice.config.sample_rate
    return extract_aligned_word(audio, widths, start_id, end_id, rate,
                                voice.config.hop_length), rate


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
    p.add_argument("--context", choices=("auto", "sentence", "none"), default="auto",
                   help="generate inside a sentence and cut by phoneme alignment (auto: Kerstin)")
    args = p.parse_args()

    from piper import PiperVoice, SynthesisConfig

    use_context = (args.context == "sentence" or
                   (args.context == "auto" and Path(args.model).stem in CONTEXT_MODELS))
    voice = PiperVoice.load(args.model, include_alignments=use_context)
    # Avoid random variation in the corrected pack's pronunciation and timing.
    config = SynthesisConfig(length_scale=args.length_scale,
                             noise_scale=0.0 if use_context else 0.5,
                             noise_w_scale=0.0 if use_context else 0.6)
    out = Path(args.out) if args.out else Path(__file__).resolve().parent.parent / "voices" / args.id
    out.mkdir(parents=True, exist_ok=True)

    # Finish synthesis before replacing any existing clips, so a failed alignment
    # or missing dependency does not leave a partly regenerated pack behind.
    generated = {}
    for token, text in TEXTS[args.lang].items():
        if use_context:
            audio, rate = contextual_audio(voice, text, args.lang, config)
        else:
            chunks = list(voice.synthesize(text, syn_config=config))
            audio = np.concatenate([chunk.audio_float_array for chunk in chunks])
            rate = voice.config.sample_rate
        generated[token] = (level_match(trim(audio, rate)), rate)
        print(f"{token:12} {text}")

    clips = {}
    for token, (audio, rate) in generated.items():
        write_wav(out / FILE_NAMES[token], audio, rate)
        clips[token] = FILE_NAMES[token]

    meta = {
        "id": args.id,
        "name": args.name,
        "language": args.lang,
        "license": args.license,
        "source": args.source,
        "generator": f"Piper ({Path(args.model).name}), scripts/build_voicepack.py",
        "generation": {
            "piper_version": version("piper-tts"),
            "model_sha256": hashlib.sha256(Path(args.model).read_bytes()).hexdigest(),
            "context": "sentence" if use_context else "none",
            "length_scale": args.length_scale,
            "noise_scale": config.noise_scale,
            "noise_w_scale": config.noise_w_scale,
        },
        "clips": clips,
    }
    (out / "pack.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"voice pack written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
