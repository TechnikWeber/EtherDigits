"""Radio output without hardware: a fake sound card, a fake rigctld, pyserial's loop:// port."""

import asyncio
import logging
import socketserver
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

from etherdigits import radio
from etherdigits.radio import CatPTT, Meter, RadioError, Rig, SerialPTT, Transmitter, validate_output
from etherdigits.render import morse
from etherdigits.schedule import Schedule
from etherdigits.script import Format, Morse, Transmission, build_script, transcript
from etherdigits.station import SilentOutput, Station
from etherdigits.store import Store

from .helpers import make_pack

logging.getLogger("etherdigits").setLevel(logging.CRITICAL)


# --- fakes -------------------------------------------------------------------------

class FakeStream:
    def __init__(self, sd, device, samplerate, channels, dtype, blocksize, callback=None):
        self.sd, self.device, self.rate, self.channels, self.callback = sd, device, samplerate, channels, callback
        self.frames = 0
        self.events = []
        sd.streams.append(self)

    def start(self):
        self.events.append("start")
        self.sd.log.append(("start", self.device))

    def write(self, data):
        assert data.shape[1] == self.channels
        self.frames += len(data)
        self.sd.log.append(("write", self.device))
        if self.callback:
            raise AssertionError("callback streams are not written to")

    def pull(self, frames=1024):
        out = np.zeros((frames, self.channels), dtype=np.float32)
        self.callback(out, frames, None, None)
        self.frames += frames
        return out

    def stop(self):
        self.events.append("stop")

    def abort(self):
        self.events.append("abort")

    def close(self):
        self.events.append("close")


class FakeSD:
    DEVICES = [
        {"name": "USB Audio CODEC", "max_output_channels": 2, "hostapi": 0, "default_samplerate": 48000},
        {"name": "Built-in Speakers", "max_output_channels": 2, "hostapi": 0, "default_samplerate": 44100},
        {"name": "Microphone", "max_output_channels": 0, "hostapi": 0, "default_samplerate": 48000},
    ]

    class default:
        device = [2, 1]

    def __init__(self):
        self.streams, self.log = [], []

    def query_devices(self, device=None, kind=None):
        if device is None and kind is None:
            return self.DEVICES
        return self.DEVICES[1 if device is None else device]

    def query_hostapis(self, _i):
        return {"name": "ALSA"}

    def OutputStream(self, **kw):  # noqa: N802 - mimics sounddevice
        return FakeStream(self, **kw)


class FakeRigctld(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        self.commands, self.freq, self.ptt = [], 7045000, 0

        rig = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                line = self.rfile.readline().decode().strip()
                rig.commands.append(line)
                cmd, *args = line.split()
                if cmd == "f":
                    self.wfile.write(f"{rig.freq}\n".encode())
                elif cmd == "F":
                    rig.freq = int(args[0])
                    self.wfile.write(b"RPRT 0\n")
                elif cmd == "T":
                    rig.ptt = int(args[0])
                    self.wfile.write(b"RPRT 0\n")
                elif cmd == "M":
                    self.wfile.write(b"RPRT 0\n" if args[0] in ("AM", "USB") else b"RPRT -1\n")
                else:
                    self.wfile.write(b"RPRT -11\n")

        super().__init__(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def port(self):
        return self.server_address[1]


# --- tests ---------------------------------------------------------------------------

class Settings(unittest.TestCase):
    def test_defaults_are_valid(self):
        self.assertEqual(validate_output({})["mode"], "silent")

    def test_bad_settings(self):
        for bad in ({"mode": "laser"}, {"gain_db": 50}, {"ptt": "serial"}, {"ptt": "cat"}, {"rig_port": 0},
                    {"max_tx_seconds": 1}, {"monitor": "yes"}, {"nonsense": 1}, {"sample_rate": 100}):
            with self.assertRaises(RadioError, msg=bad):
                validate_output(bad)

    def test_merges_with_current(self):
        cfg = validate_output({"gain_db": -3}, {"mode": "soundcard"})
        self.assertEqual((cfg["mode"], cfg["gain_db"]), ("soundcard", -3.0))


class MeterTests(unittest.TestCase):
    def test_scale(self):
        m = Meter()
        m.update(np.full(100, 1.0, dtype=np.float32))
        self.assertEqual(m.snapshot()["level"], 1.0)
        m.update(np.full(100, 0.001, dtype=np.float32))  # -60 dBFS
        self.assertAlmostEqual(m.snapshot()["level"], 0.0, places=2)
        m.update(np.zeros(100, dtype=np.float32))
        self.assertEqual(m.snapshot()["peak"], 0.0)


class MorseTests(unittest.TestCase):
    def test_paris_timing(self):
        # "PARIS " is 50 units; at 20 wpm a unit is 60 ms. Without the final word gap: 43 units.
        audio = morse("PARIS", 20, 8000)
        self.assertAlmostEqual(len(audio) / 8000, 43 * 0.06, delta=0.01)

    def test_in_script(self):
        fmt = Format(interval="none", cw_ident="dl0xyz", end_tone=False)
        steps = build_script(Transmission(format=fmt))
        self.assertEqual(steps[-1], Morse("DL0XYZ", 20))
        self.assertTrue(transcript(steps, fmt).endswith("[CW DL0XYZ]"))
        with self.assertRaises(ValueError):
            Format.from_dict({"cw_ident": "DL#1"})


class RigTests(unittest.TestCase):
    def setUp(self):
        self.rig_server = FakeRigctld()
        self.rig = Rig("127.0.0.1", self.rig_server.port)

    def tearDown(self):
        self.rig_server.shutdown()
        self.rig_server.server_close()

    def test_commands(self):
        self.assertEqual(self.rig.frequency(), 7045000)
        self.rig.set_frequency(9330000)
        self.assertEqual(self.rig.frequency(), 9330000)
        self.rig.set_mode("AM")
        with self.assertRaises(RadioError):
            self.rig.set_mode("XYZ")

    def test_cat_ptt_is_released(self):
        with self.assertRaises(ZeroDivisionError):
            with CatPTT(self.rig):
                self.assertEqual(self.rig_server.ptt, 1)
                1 / 0
        self.assertEqual(self.rig_server.ptt, 0)

    def test_unreachable(self):
        with self.assertRaises(RadioError):
            Rig("127.0.0.1", 1, timeout=0.5).frequency()


class SerialTests(unittest.TestCase):
    def test_lines(self):
        ptt = SerialPTT("loop://", "both")
        with ptt:
            self.assertTrue(ptt._serial.rts and ptt._serial.dtr)
        self.assertIsNone(ptt._serial)

    def test_invert(self):
        ptt = SerialPTT("loop://", "rts", invert=True)
        with ptt:
            self.assertFalse(ptt._serial.rts)

    def test_missing_port(self):
        with self.assertRaises(RadioError):
            with SerialPTT("/dev/does-not-exist-etherdigits"):
                pass


class TransmitterTests(unittest.TestCase):
    def setUp(self):
        self.sd = FakeSD()
        self._orig = radio._sd
        radio._sd = lambda: self.sd
        self.audio = (0.5 * np.sin(np.arange(22050) / 5)).astype(np.float32)  # 1 s at 22050 Hz

    def tearDown(self):
        radio._sd = self._orig

    def play(self, cfg, stop=None):
        tx = Transmitter(cfg)
        return tx._play(self.audio, 22050, Meter(), stop or threading.Event())

    def test_soundcard_resamples_to_device(self):
        result = self.play({"mode": "soundcard", "device": "USB Audio CODEC", "ptt_lead_ms": 0, "ptt_tail_ms": 0})
        self.assertFalse(result.stopped)
        stream = self.sd.streams[0]
        self.assertEqual((stream.device, stream.rate), (0, 48000))
        self.assertAlmostEqual(stream.frames, 48000, delta=1024)
        self.assertEqual(stream.events[-2:], ["stop", "close"])

    def test_monitor_next_to_radio(self):
        self.play({"mode": "soundcard", "device": "USB", "monitor": True, "monitor_device": "Built-in Speakers",
                   "ptt_lead_ms": 0, "ptt_tail_ms": 0})
        side = next(st for st in self.sd.streams if st.callback)
        main = next(st for st in self.sd.streams if not st.callback)
        self.assertEqual((main.device, side.device, side.rate), (0, 1, 44100))
        self.assertIsNotNone(side.callback)
        self.assertEqual(side.events, ["start", "stop", "close"])

    def test_monitor_alone(self):
        # Silent mode plus monitor: only the speaker plays, and it keeps the time.
        self.play({"mode": "silent", "monitor": True, "monitor_device": "Built-in"})
        self.assertEqual(len(self.sd.streams), 1)
        self.assertEqual(self.sd.streams[0].device, 1)
        self.assertGreater(self.sd.streams[0].frames, 40000)

    def test_same_device_is_not_opened_twice(self):
        self.play({"mode": "soundcard", "device": "USB Audio CODEC", "monitor": True,
                   "monitor_device": "USB Audio CODEC", "ptt_lead_ms": 0, "ptt_tail_ms": 0})
        self.assertEqual(len(self.sd.streams), 1)

    def test_ptt_wraps_the_audio(self):
        order = []

        class RecordingPTT:
            def __enter__(self):
                order.append("ptt on")

            def __exit__(self, *exc):
                order.append("ptt off")

        orig = radio.make_ptt
        radio.make_ptt = lambda cfg: RecordingPTT()
        try:
            self.play({"mode": "soundcard", "ptt_lead_ms": 0, "ptt_tail_ms": 0})
        finally:
            radio.make_ptt = orig
        writes = [i for i, e in enumerate(self.sd.log) if e[0] == "write"]
        self.assertEqual(order, ["ptt on", "ptt off"])
        self.assertTrue(writes)

    def test_stop_aborts(self):
        stop = threading.Event()
        stop.set()
        result = self.play({"mode": "soundcard", "ptt_lead_ms": 0}, stop)
        self.assertTrue(result.stopped)
        self.assertIn("abort", self.sd.streams[0].events)

    def test_too_long(self):
        with self.assertRaises(RadioError):
            Transmitter({"max_tx_seconds": 10})._play(np.zeros(22050 * 11, dtype=np.float32), 22050, Meter(),
                                                      threading.Event())

    def test_missing_device(self):
        with self.assertRaises(RadioError):
            Transmitter({"mode": "soundcard", "device": "Nope"}).check()
        with self.assertRaises(RadioError):
            radio.find_device("i")  # matches several devices

    def test_silent_meter_moves(self):
        meter = Meter()
        seen = []
        real_update = meter.update
        meter.update = lambda block: (seen.append(1), real_update(block))
        Transmitter({}, realtime=False)._play(self.audio, 22050, meter, threading.Event())
        self.assertGreater(len(seen), 10)
        self.assertFalse(meter.snapshot()["on_air"])


class StationRadio(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        (self.data / "recordings").mkdir()
        self.voice = str(make_pack(self.data))
        self.store = Store(":memory:")
        self.sched = self.store.save_schedule(Schedule(name="A", voice=self.voice, format={"interval": "none"},
                                                       filler="null"))

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_blocked_sends_nothing(self):
        station = Station(self.store, self.data, output=SilentOutput(realtime=False), rate=8000)
        m = self.store.add_message("12345")
        self.store.set("tx_blocked", True)
        log = self.store.log_entry(await station.transmit(self.sched))
        self.assertEqual(log["status"], "blocked")
        self.assertEqual(self.store.message(m.id).status, "queued")

    async def test_emergency_stop_keeps_the_message(self):
        station = Station(self.store, self.data, output=SilentOutput(realtime=True), rate=8000)
        m = self.store.add_message("12345 67890")
        task = asyncio.create_task(station.transmit(self.sched))
        for _ in range(100):
            await asyncio.sleep(0.02)
            if station.meter.snapshot()["on_air"]:
                break
        station.emergency_stop()
        log = self.store.log_entry(await task)
        self.assertEqual(log["status"], "stopped")
        self.assertEqual(self.store.message(m.id).status, "queued")
        self.assertTrue(self.store.get("tx_blocked"))

    async def test_tunes_the_radio_first(self):
        rig = FakeRigctld()
        try:
            self.store.set("output", validate_output({"cat": True, "rig_port": rig.port}))
            self.sched.frequency_khz, self.sched.rig_mode = 6998.0, "USB"
            station = Station(self.store, self.data, rate=8000)
            station.fixed_output = None
            # The configured transmitter is silent and real time; make it fast for the test.
            original = station.transmitter
            station.transmitter = lambda: (lambda t: (setattr(t, "realtime", False), t)[1])(original())
            log = self.store.log_entry(await station.transmit(self.sched))
            self.assertEqual(log["status"], "ok")
            self.assertEqual(rig.freq, 6998000)
            self.assertEqual(rig.commands[:2], ["F 6998000", "M USB 0"])
        finally:
            rig.shutdown()
            rig.server_close()

    async def test_tuning_error_stops_the_transmission(self):
        self.store.set("output", validate_output({"cat": True, "rig_port": 1}))
        self.sched.frequency_khz = 7000.0
        station = Station(self.store, self.data, rate=8000)
        log = self.store.log_entry(await station.transmit(self.sched))
        self.assertEqual(log["status"], "error")
        self.assertIn("rigctld", log["error"])

    async def test_limit_checked_before_the_slot(self):
        self.store.set("output", validate_output({"max_tx_seconds": 10}))
        self.store.add_message(" ".join(["12345"] * 40))
        station = Station(self.store, self.data, rate=8000)
        started = time.monotonic()
        log = self.store.log_entry(await station.transmit(self.sched))
        self.assertEqual(log["status"], "error")
        self.assertIn("limit", log["error"])
        self.assertLess(time.monotonic() - started, 5)


if __name__ == "__main__":
    unittest.main()
