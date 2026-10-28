"""Getting the audio out: sound card, monitor speaker, PTT, CAT via Hamlib.

The transmitter:
- plays a transmission on the radio's sound card (mode "soundcard"),
- or keeps real time without any sound (mode "silent"),
- and, if switched on, plays the same audio on a second device on the
  station computer ("monitor"), so you can hear what goes out.
Either way it measures the level while playing, for the meter in the web
interface.

PTT keys the radio: by VOX (nothing to do), by a serial line (RTS/DTR,
for interfaces like the Digirig), or by CAT through Hamlib's rigctld,
which can also set frequency and mode per schedule. PTT is always
released, whatever goes wrong.
"""

from __future__ import annotations

import asyncio
import logging
import math
import queue
import socket
import threading
import time
from dataclasses import dataclass

import numpy as np

from .voicepack import resample

log = logging.getLogger("etherdigits.radio")

MODES = ("silent", "soundcard")
PTTS = ("none", "serial", "cat")
SERIAL_LINES = ("rts", "dtr", "both")
RIG_MODES = ("", "AM", "USB", "LSB", "FM", "CW", "PKTUSB", "PKTLSB")
BLOCK = 1024

OUTPUT_DEFAULTS: dict = {
    "mode": "silent",          # silent | soundcard
    "device": "",              # sound card name; "" = system default
    "gain_db": 0.0,
    "sample_rate": 0,          # 0 = what the device prefers
    "monitor": False,          # also play on the station computer
    "monitor_device": "",
    "monitor_gain_db": -6.0,
    "ptt": "none",             # none (VOX) | serial | cat
    "serial_port": "",
    "serial_line": "rts",
    "serial_invert": False,
    "cat": False,              # set frequency and mode through rigctld
    "rig_host": "127.0.0.1",
    "rig_port": 4532,
    "ptt_lead_ms": 300,        # key the radio this long before the audio
    "ptt_tail_ms": 200,        # and release it this long after
    "max_tx_seconds": 900,     # never transmit longer than this
}


class RadioError(Exception):
    pass


def validate_output(changes: dict, current: dict | None = None) -> dict:
    cfg = dict(OUTPUT_DEFAULTS)
    cfg.update(current or {})
    for key, value in changes.items():
        if key not in OUTPUT_DEFAULTS:
            raise RadioError(f"unknown output setting {key!r}")
        default = OUTPUT_DEFAULTS[key]
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise RadioError(f"{key} must be true or false")
        elif isinstance(default, float):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RadioError(f"{key} must be a number")
            value = float(value)
        elif isinstance(default, int):
            if isinstance(value, bool) or not isinstance(value, int):
                raise RadioError(f"{key} must be a whole number")
        elif not isinstance(value, str):
            raise RadioError(f"{key} must be text")
        else:
            value = value.strip()[:200]
        cfg[key] = value
    checks = [
        (cfg["mode"] in MODES, f"mode must be one of {', '.join(MODES)}"),
        (cfg["ptt"] in PTTS, f"ptt must be one of {', '.join(PTTS)}"),
        (cfg["serial_line"] in SERIAL_LINES, f"serial_line must be one of {', '.join(SERIAL_LINES)}"),
        (-40 <= cfg["gain_db"] <= 12, "gain must be between -40 and +12 dB"),
        (-40 <= cfg["monitor_gain_db"] <= 12, "monitor gain must be between -40 and +12 dB"),
        (cfg["sample_rate"] == 0 or 8000 <= cfg["sample_rate"] <= 192000, "sample rate: 0 (automatic) or 8000 to 192000"),
        (1 <= cfg["rig_port"] <= 65535, "rigctld port must be between 1 and 65535"),
        (0 <= cfg["ptt_lead_ms"] <= 5000 and 0 <= cfg["ptt_tail_ms"] <= 5000, "PTT delays: 0 to 5000 ms"),
        (10 <= cfg["max_tx_seconds"] <= 7200, "transmit limit: 10 to 7200 seconds"),
        (cfg["ptt"] != "serial" or cfg["serial_port"], "serial PTT needs a serial port"),
        (cfg["ptt"] != "cat" or cfg["cat"], "PTT via CAT needs CAT switched on"),
    ]
    for ok, message in checks:
        if not ok:
            raise RadioError(message)
    return cfg


# --- level meter ---------------------------------------------------------------

class Meter:
    """What the web interface shows: on air or not, and how loud right now."""

    def __init__(self):
        self.on_air = False
        self.level = 0.0   # 0..1 on a -60..0 dBFS scale, RMS of the last block
        self.peak = 0.0    # same scale, peak of the last block
        self._lock = threading.Lock()

    @staticmethod
    def scale(value: float) -> float:
        if value <= 1e-6:
            return 0.0
        return max(0.0, min(1.0, (20 * math.log10(value) + 60) / 60))

    def update(self, block: np.ndarray) -> None:
        if len(block) == 0:
            return
        rms = float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))
        with self._lock:
            self.level, self.peak = self.scale(rms), self.scale(float(np.max(np.abs(block))))

    def start(self) -> None:
        with self._lock:
            self.on_air, self.level, self.peak = True, 0.0, 0.0

    def stop(self) -> None:
        with self._lock:
            self.on_air, self.level, self.peak = False, 0.0, 0.0

    def snapshot(self) -> dict:
        with self._lock:
            return {"on_air": self.on_air, "level": round(self.level, 3), "peak": round(self.peak, 3)}


# --- rigctld ---------------------------------------------------------------------

class Rig:
    """A tiny client for Hamlib's rigctld (start it with: rigctld -m <model> -r <port>)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4532, timeout: float = 3.0):
        self.host, self.port, self.timeout = host, port, timeout

    def command(self, line: str) -> list[str]:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall((line + "\n").encode())
                data = b""
                # Set commands answer "RPRT n", get commands answer value lines.
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if line[:1].isupper() and b"RPRT" in data:
                        break
                    if line[:1].islower() and data.endswith(b"\n"):
                        break
        except OSError as exc:
            raise RadioError(f"rigctld at {self.host}:{self.port} not reachable ({exc})") from exc
        lines = data.decode(errors="replace").strip().splitlines()
        for item in lines:
            if item.startswith("RPRT") and item.split()[-1] != "0":
                raise RadioError(f"rigctld refused {line.split()[0]!r} (error {item.split()[-1]})")
        return lines

    def set_frequency(self, hz: int) -> None:
        self.command(f"F {int(hz)}")

    def set_mode(self, mode: str, passband: int = 0) -> None:
        self.command(f"M {mode} {passband}")

    def frequency(self) -> int:
        lines = self.command("f")
        try:
            return int(float(lines[0]))
        except (IndexError, ValueError) as exc:
            raise RadioError(f"unexpected answer from rigctld: {lines!r}") from exc

    def ptt(self, on: bool) -> None:
        self.command(f"T {1 if on else 0}")


# --- PTT ---------------------------------------------------------------------------

class NoPTT:
    """VOX: the radio keys itself when it hears audio."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class SerialPTT:
    """Keys the radio with RTS and/or DTR on a serial port."""

    def __init__(self, port: str, line: str = "rts", invert: bool = False):
        self.port, self.line, self.invert = port, line, invert
        self._serial = None

    def _set(self, on: bool) -> None:
        level = on != self.invert
        if self.line in ("rts", "both"):
            self._serial.rts = level
        if self.line in ("dtr", "both"):
            self._serial.dtr = level

    def __enter__(self):
        try:
            import serial
        except ImportError as exc:
            raise RadioError("serial PTT needs pyserial: pip install pyserial") from exc
        try:
            s = serial.serial_for_url(self.port, do_not_open=True)
            # Set the idle level before opening, so the radio is not keyed by accident.
            s.rts = s.dtr = self.invert
            s.open()
        except (serial.SerialException, OSError) as exc:
            raise RadioError(f"serial port {self.port}: {exc}") from exc
        self._serial = s
        self._set(True)
        return self

    def __exit__(self, *exc):
        if self._serial is not None:
            try:
                self._set(False)
            finally:
                self._serial.close()
                self._serial = None
        return False


class CatPTT:
    def __init__(self, rig: Rig):
        self.rig = rig

    def __enter__(self):
        self.rig.ptt(True)
        return self

    def __exit__(self, *exc):
        # Releasing matters more than anything else: try a few times.
        for attempt in range(3):
            try:
                self.rig.ptt(False)
                break
            except RadioError:
                if attempt == 2:
                    log.error("could not release PTT via rigctld")
                time.sleep(0.3)
        return False


def make_ptt(cfg: dict):
    if cfg["ptt"] == "serial":
        return SerialPTT(cfg["serial_port"], cfg["serial_line"], cfg["serial_invert"])
    if cfg["ptt"] == "cat":
        return CatPTT(Rig(cfg["rig_host"], cfg["rig_port"]))
    return NoPTT()


# --- sound devices ---------------------------------------------------------------

def _sd():
    try:
        import sounddevice
    except (ImportError, OSError) as exc:
        raise RadioError("sound output needs the sounddevice package and PortAudio "
                         "(pip install sounddevice; on Linux also the portaudio package)") from exc
    return sounddevice


def list_devices() -> list[dict]:
    sd = _sd()
    try:
        default_out = sd.default.device[1]
        out = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] > 0:
                out.append({"name": d["name"], "hostapi": sd.query_hostapis(d["hostapi"])["name"],
                            "rate": int(d["default_samplerate"]), "channels": d["max_output_channels"],
                            "default": i == default_out})
        return out
    except Exception as exc:  # PortAudio errors have their own class
        raise RadioError(f"cannot list sound devices: {exc}") from exc


def find_device(name: str) -> int | None:
    """Device index by exact name, or by a unique part of the name; None = system default."""
    if not name:
        return None
    sd = _sd()
    devices = [(i, d["name"]) for i, d in enumerate(sd.query_devices()) if d["max_output_channels"] > 0]
    for i, n in devices:
        if n == name:
            return i
    matches = [i for i, n in devices if name.lower() in n.lower()]
    if len(matches) == 1:
        return matches[0]
    raise RadioError(f"sound device {name!r} not found" if not matches else f"sound device {name!r} is ambiguous")


def serial_ports() -> list[dict]:
    """Serial ports with real hardware behind them (Linux lists 32 empty ttyS ports otherwise)."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    ports = [p for p in list_ports.comports() if p.hwid and p.hwid != "n/a"]
    return [{"device": p.device, "description": p.description if p.description != "n/a" else ""}
            for p in sorted(ports, key=lambda p: p.device)]


# --- the transmitter -------------------------------------------------------------

@dataclass
class Result:
    seconds: float
    stopped: bool = False


def db(gain_db: float) -> float:
    return 10 ** (gain_db / 20)


class Transmitter:
    """Plays one transmission. Built fresh from the settings for every transmission."""

    def __init__(self, cfg: dict, realtime: bool = True):
        self.cfg = validate_output({}, cfg)
        self.realtime = realtime

    @property
    def name(self) -> str:
        return self.cfg["mode"]

    def check(self) -> None:
        """Fail early, before the slot, when the configured devices are missing."""
        if self.cfg["mode"] == "soundcard":
            find_device(self.cfg["device"])
        if self.cfg["monitor"]:
            find_device(self.cfg["monitor_device"])

    async def play(self, audio: np.ndarray, rate: int, meter: Meter, stop: threading.Event) -> Result:
        return await asyncio.to_thread(self._play, audio, rate, meter, stop)

    def _open(self, sd, device: int | None, rate: int, callback=None):
        info = sd.query_devices(device, "output")
        channels = 1 if info["max_output_channels"] >= 1 else 2
        try:
            stream = sd.OutputStream(device=device, samplerate=rate, channels=channels, dtype="float32",
                                     blocksize=BLOCK, callback=callback)
        except Exception:
            # Some devices refuse mono; then play the same signal on two channels.
            channels = 2
            stream = sd.OutputStream(device=device, samplerate=rate, channels=channels, dtype="float32",
                                     blocksize=BLOCK, callback=callback)
        return stream, channels

    def _play(self, audio: np.ndarray, rate: int, meter: Meter, stop: threading.Event) -> Result:
        cfg = self.cfg
        radio = cfg["mode"] == "soundcard"
        monitor = cfg["monitor"]
        if monitor and radio and cfg["monitor_device"] == cfg["device"]:
            monitor = False  # the same device twice would only fight over it
        limit = cfg["max_tx_seconds"]
        seconds = len(audio) / rate
        if seconds > limit:
            raise RadioError(f"the transmission would last {seconds:.0f} s, the limit is {limit} s")

        if not radio and not monitor:
            return self._silent(audio, rate, meter, stop)

        sd = _sd()
        main_dev = find_device(cfg["device"]) if radio else find_device(cfg["monitor_device"])
        main_rate = cfg["sample_rate"] or int(sd.query_devices(main_dev, "output")["default_samplerate"])
        main_audio = resample(audio, rate, main_rate) * db(cfg["gain_db"] if radio else cfg["monitor_gain_db"])
        main_audio = np.clip(main_audio, -1, 1).astype(np.float32)

        side = None
        if radio and monitor:
            side = _Side(sd, self, find_device(cfg["monitor_device"]), audio, rate, db(cfg["monitor_gain_db"]))

        ptt = make_ptt(cfg) if radio else NoPTT()
        stream, channels = self._open(sd, main_dev, main_rate)
        started = time.monotonic()
        stopped = False
        meter.start()
        try:
            with ptt:
                if radio and cfg["ptt_lead_ms"]:
                    stop.wait(cfg["ptt_lead_ms"] / 1000)
                stream.start()
                if side:
                    side.start()
                for i in range(0, len(main_audio), BLOCK):
                    if stop.is_set():
                        stopped = True
                        break
                    if time.monotonic() - started > limit + 5:
                        raise RadioError("transmit time limit reached")
                    block = main_audio[i:i + BLOCK]
                    meter.update(block)
                    if side:
                        side.feed(i / main_rate)
                    stream.write(np.repeat(block[:, None], channels, axis=1))
                if stopped:
                    stream.abort()
                else:
                    stream.stop()  # waits until the buffer is played
                if radio and cfg["ptt_tail_ms"] and not stopped:
                    time.sleep(cfg["ptt_tail_ms"] / 1000)
        finally:
            meter.stop()
            stream.close()
            if side:
                side.close()
        return Result(seconds=time.monotonic() - started, stopped=stopped)

    def _silent(self, audio: np.ndarray, rate: int, meter: Meter, stop: threading.Event) -> Result:
        """No sound at all, but real time and a moving meter."""
        meter.start()
        started = time.monotonic()
        step = int(rate * 0.05)
        try:
            for i in range(0, len(audio), step):
                if stop.is_set():
                    return Result(time.monotonic() - started, stopped=True)
                meter.update(audio[i:i + step])
                if self.realtime:
                    delay = started + (i + step) / rate - time.monotonic()
                    if delay > 0:
                        stop.wait(delay)
        finally:
            meter.stop()
        return Result(time.monotonic() - started if self.realtime else len(audio) / rate)


class _Side:
    """The monitor next to the radio: fed from the same audio, never allowed to hold up the radio."""

    def __init__(self, sd, tx: Transmitter, device: int | None, audio: np.ndarray, rate: int, gain: float):
        self.rate = tx.cfg["sample_rate"] or int(sd.query_devices(device, "output")["default_samplerate"])
        self.audio = np.clip(resample(audio, rate, self.rate) * gain, -1, 1).astype(np.float32)
        self.queue: queue.Queue = queue.Queue(maxsize=64)
        self.pos = 0
        self.stream, self.channels = tx._open(sd, device, self.rate, callback=self._callback)

    def start(self) -> None:
        self.stream.start()

    def feed(self, until_seconds: float) -> None:
        """Queue monitor audio up to where the radio is now (plus a little ahead)."""
        end = min(len(self.audio), int((until_seconds + 0.2) * self.rate))
        while self.pos < end:
            block = self.audio[self.pos:self.pos + BLOCK]
            self.pos += BLOCK
            try:
                self.queue.put_nowait(block)
            except queue.Full:
                break  # the monitor fell behind; drop rather than wait

    def _callback(self, outdata, frames, _time, _status):
        try:
            block = self.queue.get_nowait()
        except queue.Empty:
            block = np.zeros(0, dtype=np.float32)
        out = np.zeros(frames, dtype=np.float32)
        out[:min(frames, len(block))] = block[:frames]
        outdata[:] = np.repeat(out[:, None], self.channels, axis=1)

    def close(self) -> None:
        try:
            self.stream.stop()
        finally:
            self.stream.close()
