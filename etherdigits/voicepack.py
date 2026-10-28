"""Voice packs: one folder per voice with a pack.json and one WAV per word.

Layout:

    voices/de-kerstin/
        pack.json      {"id", "name", "language", "license", "source", "clips": {token: file}}
        0.wav ... 9.wav attention.wav groups.wav ...

Tokens are the same in every language, so a transmission script never
depends on the language. A pack must contain the digits; the words are
optional and are left out of the transmission when missing.
"""

from __future__ import annotations

import json
import os
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

DIGITS = [str(d) for d in range(10)]
# Words a transmission may use, besides the digits.
WORDS = ["attention", "groups", "repeat", "separator", "no_message", "end"]
TOKENS = DIGITS + WORDS

BUILTIN_DIR = Path(__file__).resolve().parent.parent / "voices"


class VoicePackError(Exception):
    pass


@dataclass
class VoicePack:
    id: str
    name: str
    language: str
    path: Path
    license: str = ""
    source: str = ""
    clips: dict[str, str] = field(default_factory=dict)
    _cache: dict[tuple[str, int], np.ndarray] = field(default_factory=dict, repr=False)

    def has(self, token: str) -> bool:
        return token in self.clips

    def clip(self, token: str, sample_rate: int) -> np.ndarray:
        """The clip for `token` as float32 mono at `sample_rate`."""
        key = (token, sample_rate)
        if key not in self._cache:
            if token not in self.clips:
                raise VoicePackError(f"voice pack {self.id!r} has no clip for {token!r}")
            audio, rate = read_wav(self.path / self.clips[token])
            self._cache[key] = resample(audio, rate, sample_rate)
        return self._cache[key]


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read a 16-bit PCM WAV as float32 mono in -1..1."""
    try:
        with wave.open(str(path), "rb") as w:
            if w.getsampwidth() != 2:
                raise VoicePackError(f"{path}: only 16-bit WAV files are supported")
            rate = w.getframerate()
            channels = w.getnchannels()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    except (wave.Error, EOFError) as exc:
        raise VoicePackError(f"{path}: not a readable WAV file ({exc})") from exc
    audio = data.astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, rate


def resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Linear resampling. Plenty for speech that ends up on shortwave."""
    if src_rate == dst_rate or len(audio) == 0:
        return audio.astype(np.float32, copy=False)
    n = max(1, round(len(audio) * dst_rate / src_rate))
    x_old = np.arange(len(audio), dtype=np.float64) / src_rate
    x_new = np.arange(n, dtype=np.float64) / dst_rate
    return np.interp(x_new, x_old, audio).astype(np.float32)


def load_pack(path: Path) -> VoicePack:
    path = Path(path)
    meta_file = path / "pack.json"
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VoicePackError(f"{path}: pack.json is missing") from exc
    except json.JSONDecodeError as exc:
        raise VoicePackError(f"{meta_file}: invalid JSON ({exc})") from exc
    clips = meta.get("clips") or {}
    missing = [d for d in DIGITS if d not in clips]
    if missing:
        raise VoicePackError(f"{path}: digits missing: {' '.join(missing)}")
    for token, file in clips.items():
        if not (path / file).is_file():
            raise VoicePackError(f"{path}: clip for {token!r} not found: {file}")
    return VoicePack(
        id=meta.get("id") or path.name,
        name=meta.get("name") or path.name,
        language=meta.get("language") or "",
        path=path,
        license=meta.get("license") or "",
        source=meta.get("source") or "",
        clips=dict(clips),
    )


def search_dirs() -> list[Path]:
    """Built-in voices first, then folders from ETHERDIGITS_VOICES (os.pathsep separated)."""
    dirs = [BUILTIN_DIR]
    extra = os.environ.get("ETHERDIGITS_VOICES", "")
    dirs += [Path(p).expanduser() for p in extra.split(os.pathsep) if p]
    return dirs


def list_packs(dirs: list[Path] | None = None) -> list[VoicePack]:
    """All valid packs. Broken ones are skipped; `find_pack` reports why."""
    packs: dict[str, VoicePack] = {}
    for base in dirs if dirs is not None else search_dirs():
        if not base.is_dir():
            continue
        for sub in sorted(base.iterdir()):
            if (sub / "pack.json").is_file():
                try:
                    pack = load_pack(sub)
                except VoicePackError:
                    continue
                packs.setdefault(pack.id, pack)
    return list(packs.values())


def find_pack(name: str, dirs: list[Path] | None = None) -> VoicePack:
    """Find a pack by id ("de-kerstin"), by language ("de") or by folder path."""
    candidate = Path(name).expanduser()
    if (candidate / "pack.json").is_file():
        return load_pack(candidate)
    packs = list_packs(dirs)
    for pack in packs:
        if pack.id == name:
            return pack
    for pack in packs:
        if pack.language == name:
            return pack
    known = ", ".join(p.id for p in packs) or "none"
    raise VoicePackError(f"voice {name!r} not found (available: {known})")
