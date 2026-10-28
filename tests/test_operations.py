"""Running unattended: clock check, two-factor login, health, service files, internet stream."""

import base64
import logging
import plistlib
import shutil
import socket
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np
from aiohttp.test_utils import TestClient, TestServer

from etherdigits import service
from etherdigits.auth import hash_password, totp, verify_totp
from etherdigits.clock import NTP_EPOCH, ClockError, sntp_offset
from etherdigits.radio import RadioError, validate_output
from etherdigits.server import make_app
from etherdigits.station import SilentOutput, Station
from etherdigits.store import Store, StoreError
from etherdigits.stream import StreamSink, stream_url

logging.getLogger("etherdigits").setLevel(logging.CRITICAL)


class FakeNtp:
    """Answers like a time server whose clock is `skew` seconds ahead."""

    def __init__(self, skew: float = 0.0, mode: int = 4):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.skew, self.mode = skew, mode
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        data, addr = self.sock.recvfrom(512)
        now = time.time() + self.skew + NTP_EPOCH
        ts = struct.pack("!II", int(now), int((now % 1) * 2 ** 32))
        reply = bytes([0x20 | self.mode, 2]) + b"\0" * 30 + ts + ts
        self.sock.sendto(reply, addr)

    def close(self):
        self.sock.close()


class Clock(unittest.TestCase):
    def test_offset(self):
        server = FakeNtp(skew=12.5)
        try:
            self.assertAlmostEqual(sntp_offset("127.0.0.1", server.port), 12.5, delta=0.2)
        finally:
            server.close()

    def test_bad_answer(self):
        server = FakeNtp(mode=3)
        try:
            with self.assertRaises(ClockError):
                sntp_offset("127.0.0.1", server.port)
        finally:
            server.close()

    def test_no_answer(self):
        with self.assertRaises(ClockError):
            sntp_offset("127.0.0.1", 9, timeout=0.3)

    def test_station_follows_the_server(self):
        server = FakeNtp(skew=30)
        store = Store(":memory:")
        try:
            store.set("ntp_server", "127.0.0.1")
            station = Station(store, Path(tempfile.gettempdir()))
            import etherdigits.station as st
            original = st.sntp_offset
            st.sntp_offset = lambda host: original(host, server.port)
            try:
                status = station.check_clock()
            finally:
                st.sntp_offset = original
            self.assertAlmostEqual(status["offset"], 30, delta=0.5)
            self.assertAlmostEqual(station.clock_offset, 30, delta=0.5)
            self.assertAlmostEqual((station.corrected_now() - st.utcnow()).total_seconds(), 30, delta=0.5)
        finally:
            server.close()

    def test_server_setting(self):
        store = Store(":memory:")
        store.update_settings({"ntp_server": "ptbtime1.ptb.de"})
        with self.assertRaises(StoreError):
            store.update_settings({"ntp_server": "evil; rm -rf /"})


class Totp(unittest.TestCase):
    SECRET = base64.b32encode(b"12345678901234567890").decode()

    def test_rfc_vectors(self):
        self.assertEqual(totp(self.SECRET, 59 // 30, 8), "94287082")
        self.assertEqual(totp(self.SECRET, 1111111109 // 30, 8), "07081804")

    def test_window_and_replay(self):
        now = 1_800_000_000
        code = totp(self.SECRET, now // 30)
        counter = verify_totp(self.SECRET, code, now=now)
        self.assertEqual(counter, now // 30)
        self.assertEqual(verify_totp(self.SECRET, code, now=now + 30), now // 30)  # 30 s of drift is fine
        self.assertIsNone(verify_totp(self.SECRET, code, now=now + 90))
        self.assertIsNone(verify_totp(self.SECRET, code, now=now, last_counter=counter))  # used already
        self.assertIsNone(verify_totp(self.SECRET, "12345", now=now))


class ServiceFiles(unittest.TestCase):
    def test_systemd(self):
        unit = service.systemd_unit(["/opt/py", "-m", "etherdigits", "serve", "--data", "/a b"], "/home/x")
        self.assertIn("ExecStart=/opt/py -m etherdigits serve --data '/a b'", unit)
        self.assertIn("Restart=always", unit)

    def test_launchd(self):
        plist = plistlib.loads(service.launchd_plist(["/py", "serve", "--data", "/a&b"], "/Users/x", "/Users/x/L").encode())
        self.assertEqual(plist["ProgramArguments"], ["/py", "serve", "--data", "/a&b"])
        self.assertTrue(plist["KeepAlive"])

    def test_windows(self):
        text = service.windows_cmd(["C:\\Py\\python.exe", "-m", "etherdigits", "service", "run", "--data", "C:\\A B"])
        self.assertIn('"C:\\A B"', text)
        self.assertIn("service run", text)

    def test_supervised_command(self):
        cmd = service.supervised_command("127.0.0.1", 8472, None)
        self.assertEqual(cmd[-6:], ["service", "run", "--host", "127.0.0.1", "--port", "8472"])


class FakeIcecast:
    def __init__(self):
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.port = self.srv.getsockname()[1]
        self.head, self.bytes = b"", 0
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        conn, _ = self.srv.accept()
        conn.settimeout(10)
        data = b""
        while b"\r\n\r\n" not in data:
            data += conn.recv(4096)
        self.head, rest = data.split(b"\r\n\r\n", 1)
        self.conn = conn
        conn.sendall(b"HTTP/1.1 100 Continue\r\n\r\n" if b"100-continue" in self.head.lower() else b"HTTP/1.1 200 OK\r\n\r\n")
        self.bytes += len(rest)
        try:
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                self.bytes += len(chunk)
        except OSError:
            pass

    def close(self):
        self.srv.close()
        if getattr(self, "conn", None):
            self.conn.close()


class Stream(unittest.TestCase):
    def cfg(self, **kw):
        return validate_output(dict({"stream": True, "stream_host": "127.0.0.1", "stream_password": "p@ss word"}, **kw))

    def test_settings(self):
        with self.assertRaises(RadioError):
            validate_output({"stream": True})  # no server
        with self.assertRaises(RadioError):
            validate_output({"stream_mount": "no-slash"})
        self.assertIn("source:p%40ss%20word@127.0.0.1:8000/etherdigits.mp3", stream_url(self.cfg()))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_streams_in_real_time(self):
        server = FakeIcecast()
        sink = StreamSink()
        try:
            sink.configure(self.cfg(stream_port=server.port))
            sink.push((0.3 * np.sin(np.arange(22050) / 3)).astype(np.float32))
            time.sleep(4.5)
            self.assertTrue(sink.state["connected"])
        finally:
            sink.close()
            server.close()
        self.assertTrue(server.head.startswith(b"PUT /etherdigits.mp3 "))
        self.assertIn(base64.b64encode(b"source:p@ss word"), server.head)
        # 64 kbit/s for about 4 s, give or take the start: real time, not as fast as possible.
        self.assertTrue(15_000 < server.bytes < 60_000, server.bytes)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_reports_a_missing_server(self):
        sink = StreamSink()
        try:
            sink.configure(self.cfg(stream_port=9))
            for _ in range(50):
                time.sleep(0.2)
                if sink.state["error"]:
                    break
            self.assertFalse(sink.state["connected"])
            self.assertTrue(sink.state["error"])
            self.assertNotIn("p@ss", sink.state["error"])
        finally:
            sink.close()


class Api(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.store = Store(":memory:")
        self.store.set("admin_password", hash_password("a long passphrase"))
        self.station = Station(self.store, self.data, output=SilentOutput(realtime=False), rate=8000)
        self.client = TestClient(TestServer(make_app(self.store, self.station, self.data, run_station=False)))
        await self.client.start_server()
        self.h = {"X-EtherDigits": "1"}
        r = await self.client.post("/api/login", json={"password": "a long passphrase"})
        self.assertEqual(r.status, 200)

    async def asyncTearDown(self):
        await self.client.close()
        await self.station.stop()
        self.tmp.cleanup()

    async def test_totp_flow(self):
        r = await self.client.post("/api/totp/setup", json={"password": "wrong"}, headers=self.h)
        self.assertEqual(r.status, 401)
        r = await self.client.post("/api/totp/setup", json={"password": "a long passphrase"}, headers=self.h)
        secret = (await r.json())["secret"]
        r = await self.client.post("/api/totp/enable", json={"code": "000000"}, headers=self.h)
        self.assertEqual(r.status, 400)
        step = int(time.time() // 30)
        r = await self.client.post("/api/totp/enable", json={"code": totp(secret, step)}, headers=self.h)
        self.assertEqual(r.status, 200)
        self.client.session.cookie_jar.clear()
        r = await self.client.post("/api/login", json={"password": "a long passphrase"})
        self.assertEqual((r.status, (await r.json())["error"]), (401, "code required"))
        # The code used for enabling cannot log in again (replay).
        r = await self.client.post("/api/login", json={"password": "a long passphrase", "code": totp(secret, step)})
        self.assertEqual((r.status, (await r.json())["error"]), (401, "wrong code"))
        # The next step's code is accepted (one step of drift allowed).
        r = await self.client.post("/api/login", json={"password": "a long passphrase", "code": totp(secret, step + 1)})
        self.assertEqual(r.status, 200)
        r = await self.client.get("/api/session")
        self.assertTrue((await r.json())["totp"])

    async def test_health(self):
        r = await self.client.get("/api/health")
        self.assertEqual(r.status, 503)  # the scheduler has not ticked yet
        self.station.tick(self.station.clock())
        self.client.session.cookie_jar.clear()
        r = await self.client.get("/api/health")
        self.assertEqual(r.status, 200)
        self.assertEqual(set(await r.json()), {"ok", "scheduler", "clock", "version"})

    async def test_stream_password_stays_on_the_station(self):
        r = await self.client.put("/api/output", json={"stream_host": "example.org", "stream_password": "secret!"},
                                  headers=self.h)
        out = await r.json()
        self.assertNotIn("stream_password", out)
        self.assertTrue(out["stream_password_set"])
        r = await self.client.put("/api/output", json={"stream_bitrate": 96, "stream_password": ""}, headers=self.h)
        self.assertEqual(self.store.get("output")["stream_password"], "secret!")  # empty field keeps it
        self.assertNotIn("secret!", await r.text())


if __name__ == "__main__":
    unittest.main()
