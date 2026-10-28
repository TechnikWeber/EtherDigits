"""Internet stream: the station as an Icecast source, around the clock.

ffmpeg encodes MP3 and sends it to an Icecast server. The stream never
stops: between transmissions it carries silence, so listeners stay
connected and hear the next transmission the moment it starts, like a
receiver left on the frequency. If the server goes away, the stream
reconnects, waiting longer after every failure.

Note: ffmpeg gets the source password on its command line, which other
users of the same computer could read. Run the station on a machine of
its own, or use a source password that guards nothing else.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from collections import deque
from urllib.parse import quote

import numpy as np

from .schedule import iso, utcnow

log = logging.getLogger("etherdigits.stream")

RATE = 22050
CHUNK = RATE // 10  # 100 ms
KEYS = ("stream", "stream_host", "stream_port", "stream_mount", "stream_user", "stream_password",
        "stream_bitrate", "stream_name")


def stream_url(cfg: dict) -> str:
    user = quote(cfg["stream_user"] or "source", safe="")
    password = quote(cfg["stream_password"], safe="")
    host = cfg["stream_host"]
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"  # IPv6
    return f"icecast://{user}:{password}@{host}:{cfg['stream_port']}{cfg['stream_mount']}"


def ffmpeg_command(cfg: dict, ffmpeg: str = "ffmpeg") -> list[str]:
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "f32le", "-ar", str(RATE), "-ac", "1", "-i", "pipe:0",
            "-c:a", "libmp3lame", "-b:a", f"{cfg['stream_bitrate']}k", "-ar", "44100",
            "-content_type", "audio/mpeg", "-ice_name", cfg["stream_name"] or "EtherDigits",
            "-f", "mp3", stream_url(cfg)]


class StreamSink:
    def __init__(self, rate: int = RATE):
        self.rate = rate
        self.cfg: dict = {}
        self.state = {"enabled": False, "connected": False, "error": "", "since": None}
        self._pending: deque[np.ndarray] = deque()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def configure(self, cfg: dict) -> None:
        wanted = {k: cfg.get(k) for k in KEYS}
        if wanted == self.cfg and (self._thread is not None) == bool(wanted["stream"]):
            return
        self.close()
        self.cfg = wanted
        self.state = {"enabled": bool(wanted["stream"]), "connected": False, "error": "", "since": None}
        if wanted["stream"]:
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, name="etherdigits-stream", daemon=True)
            self._thread.start()

    def push(self, audio: np.ndarray) -> None:
        """Queue a transmission; it goes out as soon as the current one is through."""
        if self._thread is None:
            return
        with self._lock:
            for i in range(0, len(audio), CHUNK):
                self._pending.append(audio[i:i + CHUNK].astype(np.float32))

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None
        with self._lock:
            self._pending.clear()

    def _next_chunk(self) -> np.ndarray:
        with self._lock:
            chunk = self._pending.popleft() if self._pending else None
        if chunk is None:
            return np.zeros(CHUNK, dtype=np.float32)
        if len(chunk) < CHUNK:
            chunk = np.concatenate([chunk, np.zeros(CHUNK - len(chunk), dtype=np.float32)])
        return chunk

    def _run(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        delay = 5.0
        while not self._stop.is_set():
            if not ffmpeg:
                self.state.update(connected=False, error="the stream needs ffmpeg installed")
                self._stop.wait(30)
                ffmpeg = shutil.which("ffmpeg")
                continue
            started = time.monotonic()
            try:
                proc = subprocess.Popen(ffmpeg_command(self.cfg, ffmpeg), stdin=subprocess.PIPE,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            except OSError as exc:
                self.state.update(connected=False, error=f"ffmpeg did not start: {exc}")
                self._stop.wait(delay)
                continue
            error = self._feed(proc, started)
            if self._stop.is_set():
                break
            # A connection that lasted a while earns a quick retry; quick failures back off.
            delay = 5.0 if time.monotonic() - started > 60 else min(delay * 2, 300.0)
            self.state.update(connected=False, error=error or "the stream ended", since=None)
            log.warning("stream to %s ended (%s); retrying in %.0f s", self.cfg["stream_host"], error, delay)
            self._stop.wait(delay)
        self.state.update(connected=False)

    def _feed(self, proc: subprocess.Popen, started: float) -> str:
        """Write audio in real time until ffmpeg exits or the sink is closed. Returns ffmpeg's complaint."""
        sent = 0
        try:
            while not self._stop.is_set():
                if proc.poll() is not None:
                    break
                proc.stdin.write(self._next_chunk().tobytes())
                proc.stdin.flush()
                sent += CHUNK
                if not self.state["connected"] and time.monotonic() - started > 3:
                    self.state.update(connected=True, error="", since=iso(utcnow()))
                # Keep real time: never run ahead of the clock by more than half a second.
                ahead = started + sent / self.rate - time.monotonic() - 0.5
                if ahead > 0:
                    self._stop.wait(ahead)
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        err = []
        if proc.stderr:
            err = proc.stderr.read().decode(errors="replace").strip().splitlines()
            proc.stderr.close()
        # Never show the password, even if ffmpeg repeats the URL.
        text = (err[-1] if err else "")[:300]
        if self.cfg.get("stream_password"):
            text = text.replace(self.cfg["stream_password"], "***").replace(quote(self.cfg["stream_password"], safe=""), "***")
        return text
