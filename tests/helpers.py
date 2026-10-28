"""A tiny synthetic voice pack, so tests do not depend on the shipped voices."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

from etherdigits.voicepack import DIGITS, WORDS

RATE = 8000
CLIP_SECONDS = 0.1


def make_pack(base: Path, words: bool = True, rate: int = RATE, pack_id: str = "test-xx") -> Path:
    path = base / pack_id
    path.mkdir(parents=True)
    clips = {}
    for i, token in enumerate(DIGITS + (WORDS if words else [])):
        t = np.arange(int(rate * CLIP_SECONDS)) / rate
        audio = 0.5 * np.sin(2 * np.pi * (300 + 20 * i) * t)
        with wave.open(str(path / f"{token}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes((audio * 32767).astype("<i2").tobytes())
        clips[token] = f"{token}.wav"
    meta = {"id": pack_id, "name": "Test", "language": "xx", "license": "CC0-1.0", "clips": clips}
    (path / "pack.json").write_text(json.dumps(meta), encoding="utf-8")
    return path
