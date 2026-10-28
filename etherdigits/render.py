"""Turn a transmission script into audio, and write it to WAV or MP3."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from .script import Melody, Pause, Say, Step, Tone
from .voicepack import VoicePack

DEFAULT_RATE = 22050

# Interval signals: (MIDI note, seconds). Original tunes written for EtherDigits.
MELODIES: dict[str, list[tuple[int, float]]] = {
    "ether": [(69, 0.32), (72, 0.32), (76, 0.32), (74, 0.5), (72, 0.32), (69, 0.32), (64, 0.32), (69, 0.9)],
}

EFFECTS = ("none", "radio")


def _fade(audio: np.ndarray, rate: int, seconds: float = 0.005) -> np.ndarray:
    n = min(len(audio) // 2, int(rate * seconds))
    if n:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        audio[:n] *= ramp
        audio[-n:] *= ramp[::-1]
    return audio


def tone(freq: float, seconds: float, rate: int, level: float = 0.45) -> np.ndarray:
    t = np.arange(int(rate * seconds), dtype=np.float32) / rate
    return _fade((level * np.sin(2 * np.pi * freq * t)).astype(np.float32), rate)


def chime(note: int, seconds: float, rate: int, level: float = 0.5) -> np.ndarray:
    """A soft music-box note: a few harmonics with a decaying envelope."""
    freq = 440.0 * 2 ** ((note - 69) / 12)
    t = np.arange(int(rate * seconds), dtype=np.float32) / rate
    wave_ = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t) + 0.1 * np.sin(6 * np.pi * freq * t)
    env = np.exp(-t / 0.35)
    return _fade((level / 1.4 * wave_ * env).astype(np.float32), rate)


def melody(name: str, rate: int) -> np.ndarray:
    if name not in MELODIES:
        raise ValueError(f"unknown melody {name!r} (available: {', '.join(MELODIES)})")
    return np.concatenate([chime(note, sec, rate) for note, sec in MELODIES[name]])


def render(steps: list[Step], pack: VoicePack, rate: int = DEFAULT_RATE, effect: str = "none") -> np.ndarray:
    """Audio for a script as float32 mono in -1..1."""
    if effect not in EFFECTS:
        raise ValueError(f"effect must be one of {', '.join(EFFECTS)}")
    edge = np.zeros(int(rate * 0.3), dtype=np.float32)
    parts: list[np.ndarray] = [edge]
    for step in steps:
        if isinstance(step, Say):
            if pack.has(step.token):
                parts.append(pack.clip(step.token, rate))
        elif isinstance(step, Pause):
            parts.append(np.zeros(int(rate * step.seconds), dtype=np.float32))
        elif isinstance(step, Tone):
            parts.append(tone(step.freq, step.seconds, rate))
        elif isinstance(step, Melody):
            parts.append(melody(step.name, rate))
    parts.append(edge)
    audio = np.concatenate(parts).astype(np.float32)
    if effect == "radio":
        audio = radio_effect(audio, rate)
    return normalize(audio)


def normalize(audio: np.ndarray, peak_db: float = -1.0) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak < 1e-6:
        return audio
    return (audio * (10 ** (peak_db / 20) / peak)).astype(np.float32)


def radio_effect(audio: np.ndarray, rate: int, seed: int | None = None) -> np.ndarray:
    """Sound like an AM shortwave broadcast: narrow band, a little drive, some noise."""
    n = len(audio)
    if n == 0:
        return audio
    spectrum = np.fft.rfft(audio)
    freqs = np.fft.rfftfreq(n, 1 / rate)
    # Smooth band-pass 300..2800 Hz.
    low = 1 / (1 + (300 / np.maximum(freqs, 1e-3)) ** 4)
    high = 1 / (1 + (freqs / 2800) ** 4)
    audio = np.fft.irfft(spectrum * low * high, n).astype(np.float32)
    audio = normalize(audio, -3.0)
    audio = (np.tanh(2.2 * audio) / np.tanh(2.2)).astype(np.float32)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n).astype(np.float32)
    # Slowly fading noise floor, like a real band.
    fading = 0.6 + 0.4 * np.sin(2 * np.pi * 0.13 * np.arange(n) / rate)
    return (audio + 0.025 * noise * fading.astype(np.float32)).astype(np.float32)


def to_pcm16(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def write_wav(path: Path, audio: np.ndarray, rate: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(to_pcm16(audio))


def mp3_encoder() -> list[str] | None:
    """Command prefix for an available MP3 encoder (ffmpeg or lame), or None."""
    if shutil.which("ffmpeg"):
        return ["ffmpeg", "-loglevel", "error", "-y", "-i"]
    if shutil.which("lame"):
        return ["lame", "--quiet"]
    return None


def write_audio(path: Path, audio: np.ndarray, rate: int) -> None:
    """Write WAV or MP3, chosen by the file extension."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".wav":
        write_wav(path, audio, rate)
        return
    if suffix != ".mp3":
        raise ValueError("output must end in .wav or .mp3")
    encoder = mp3_encoder()
    if not encoder:
        raise RuntimeError("MP3 needs ffmpeg or lame installed; write a .wav file instead")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_wav = Path(tmp) / "out.wav"
        write_wav(tmp_wav, audio, rate)
        cmd = encoder + [str(tmp_wav), str(path)]
        if encoder[0] == "ffmpeg":
            cmd = encoder + [str(tmp_wav), "-codec:a", "libmp3lame", "-q:a", "4", str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"MP3 encoding failed: {result.stderr.strip() or result.returncode}")
