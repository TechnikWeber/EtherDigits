import asyncio
import logging
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer

from etherdigits.auth import Sessions, Throttle, hash_password, verify_password
from etherdigits.schedule import Schedule, ScheduleError, iso
from etherdigits.server import make_app
from etherdigits.station import SilentOutput, Station
from etherdigits.store import Store, StoreError

from .helpers import make_pack

UTC = timezone.utc
logging.getLogger("etherdigits").setLevel(logging.CRITICAL)  # expected failures stay quiet


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


class Schedules(unittest.TestCase):
    def test_fixed_times(self):
        s = Schedule(times=["18:00", "06:30"]).validate()
        self.assertEqual(s.next_run(at("2026-10-28 05:00")), at("2026-10-28 06:30"))
        self.assertEqual(s.next_run(at("2026-10-28 06:30")), at("2026-10-28 18:00"))  # strictly after
        self.assertEqual(s.next_run(at("2026-10-28 19:00")), at("2026-10-29 06:30"))

    def test_weekdays(self):
        s = Schedule(times=["12:00"], weekdays=[5]).validate()  # Saturdays only
        self.assertEqual(s.next_run(at("2026-10-28 13:00")), at("2026-10-31 12:00"))
        self.assertEqual(s.next_run(at("2026-10-31 12:00")), at("2026-11-07 12:00"))

    def test_interval(self):
        s = Schedule(kind="interval", interval_minutes=15, offset_minutes=5).validate()
        self.assertEqual(s.next_run(at("2026-10-28 10:00")), at("2026-10-28 10:05"))
        self.assertEqual(s.next_run(at("2026-10-28 10:05")), at("2026-10-28 10:20"))
        self.assertEqual(s.upcoming(at("2026-10-28 10:00"), 3),
                         [at("2026-10-28 10:05"), at("2026-10-28 10:20"), at("2026-10-28 10:35")])

    def test_interval_skips_days(self):
        s = Schedule(kind="interval", interval_minutes=60, weekdays=[0]).validate()  # Mondays
        self.assertEqual(s.next_run(at("2026-10-28 10:30")), at("2026-11-02 00:00"))

    def test_window(self):
        s = Schedule(kind="interval", interval_minutes=10, window_start="18:00", window_end="19:00",
                     weekdays=[0, 1, 2, 3, 4]).validate()
        runs = s.upcoming(at("2026-10-30 17:55"), 9)  # a Friday
        self.assertEqual(runs[:2], [at("2026-10-30 18:00"), at("2026-10-30 18:10")])
        self.assertEqual(runs[6], at("2026-10-30 19:00"))  # the end is included
        self.assertEqual(runs[7], at("2026-11-02 18:00"))  # then Monday

    def test_window_past_midnight(self):
        s = Schedule(kind="interval", interval_minutes=60, window_start="23:00", window_end="01:00",
                     weekdays=[4]).validate()  # starts on Fridays
        self.assertEqual(s.upcoming(at("2026-10-30 12:00"), 4),
                         [at("2026-10-30 23:00"), at("2026-10-31 00:00"), at("2026-10-31 01:00"), at("2026-11-06 23:00")])

    def test_time_zone_follows_daylight_saving(self):
        s = Schedule(times=["18:00"], timezone="Europe/Berlin").validate()
        self.assertEqual(s.upcoming(at("2026-03-28 12:00"), 2), [at("2026-03-28 17:00"), at("2026-03-29 16:00")])
        self.assertEqual(s.next_run(at("2026-10-25 12:00")), at("2026-10-25 17:00"))  # back to winter time

    def test_weekdays_in_the_zone(self):
        # 00:30 on a Saturday in Tokyo is still Friday in UTC.
        s = Schedule(times=["00:30"], weekdays=[5], timezone="Asia/Tokyo").validate()
        self.assertEqual(s.next_run(at("2026-10-28 00:00")), at("2026-10-30 15:30"))

    def test_disabled(self):
        self.assertIsNone(Schedule(enabled=False).validate().next_run(at("2026-10-28 10:00")))

    def test_validation(self):
        bad = [{"times": ["25:00"]}, {"times": []}, {"weekdays": []}, {"kind": "sometimes"},
               {"filler_min": 30, "filler_max": 10}, {"format": {"callsign": "abc"}}, {"name": " "},
               {"interval_minutes": 0}, {"colour": "red"}, {"timezone": "Mars/Olympus"},
               {"window_start": "18:00"}, {"window_start": "18:00", "window_end": "18:00"}]
        for data in bad:
            with self.assertRaises(ScheduleError, msg=data):
                Schedule.from_dict({"name": "x", **data})


class Queue(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.sched = self.store.save_schedule(Schedule(name="A"))

    def test_priority_then_age(self):
        a = self.store.add_message("11111")
        b = self.store.add_message("22222", priority=2)
        c = self.store.add_message("33333")
        due = self.store.due(self.sched.id, iso(datetime.now(UTC)), 3)
        self.assertEqual([m.id for m in due], [b.id, a.id, c.id])

    def test_transmissions_and_burn(self):
        m = self.store.add_message("12345 67890", transmissions=2, burn=True)
        now = iso(datetime.now(UTC))
        self.store.mark_sent([m.id], now)
        self.assertEqual(self.store.message(m.id).status, "queued")
        self.store.mark_sent([m.id], now)
        done = self.store.message(m.id)
        self.assertEqual((done.status, done.groups, done.group_count), ("done", None, 2))

    def test_keep_when_not_burning(self):
        m = self.store.add_message("12345", burn=False)
        self.store.mark_sent([m.id], iso(datetime.now(UTC)))
        self.assertEqual(self.store.message(m.id).groups, ["12345"])

    def test_not_before_and_expiry(self):
        now = datetime.now(UTC)
        later = self.store.add_message("11111", not_before=iso(now + timedelta(hours=1)))
        old = self.store.add_message("22222", expires=iso(now + timedelta(minutes=1)))
        self.assertEqual([m.id for m in self.store.due(self.sched.id, iso(now), 5)], [old.id])
        self.assertEqual(self.store.due(self.sched.id, iso(now + timedelta(minutes=5)), 5), [])
        self.assertEqual(self.store.message(old.id).status, "expired")
        self.assertEqual([m.id for m in self.store.due(self.sched.id, iso(now + timedelta(hours=2)), 5)], [later.id])

    def test_bound_to_schedule(self):
        other = self.store.save_schedule(Schedule(name="B"))
        m = self.store.add_message("11111", schedule_id=other.id)
        now = iso(datetime.now(UTC))
        self.assertEqual(self.store.due(self.sched.id, now, 5), [])
        self.assertEqual([x.id for x in self.store.due(other.id, now, 5)], [m.id])
        self.store.delete_schedule(other.id)
        self.assertEqual([x.id for x in self.store.due(self.sched.id, now, 5)], [m.id])

    def test_bad_messages(self):
        for kwargs in ({"groups": "1234"}, {"groups": "12345", "priority": 7}, {"groups": "12345", "transmissions": 0},
                       {"groups": "12345", "schedule_id": 999}, {"groups": "12345", "not_before": "gestern"}):
            with self.assertRaises(StoreError, msg=kwargs):
                self.store.add_message(**kwargs)

    def test_cancel(self):
        m = self.store.add_message("11111")
        self.assertFalse(self.store.delete_message(m.id))  # queued ones must be cancelled first
        self.assertTrue(self.store.cancel_message(m.id))
        self.assertIsNone(self.store.message(m.id).groups)
        self.assertTrue(self.store.delete_message(m.id))

    def test_tokens(self):
        tid, token = self.store.add_token("agent")
        self.assertTrue(token.startswith("ed_"))
        self.assertEqual(self.store.check_token(token)["id"], tid)
        self.assertIsNone(self.store.check_token("ed_wrong"))
        self.assertNotIn(token, str(self.store.tokens()))
        self.store.revoke_token(tid)
        self.assertIsNone(self.store.check_token(token))

    def test_password_hash_stays_private(self):
        self.store.set("admin_password", "secret-hash")
        self.assertNotIn("admin_password", self.store.settings())
        with self.assertRaises(StoreError):
            self.store.update_settings({"admin_password": "x"})


class Auth(unittest.TestCase):
    def test_password(self):
        stored = hash_password("correct horse")
        self.assertTrue(verify_password("correct horse", stored))
        self.assertFalse(verify_password("wrong", stored))
        self.assertFalse(verify_password("x", "garbage"))

    def test_sessions_expire(self):
        now = [0.0]
        sessions = Sessions(clock=lambda: now[0])
        token = sessions.create()
        self.assertTrue(sessions.valid(token))
        now[0] += 13 * 3600
        self.assertFalse(sessions.valid(token))

    def test_throttle(self):
        throttle = Throttle(limit=2, seconds=60, clock=lambda: 0)
        throttle.fail("a"); throttle.fail("a")
        self.assertTrue(throttle.blocked("a"))
        self.assertFalse(throttle.blocked("b"))


class Clock:
    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now


class StationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        (self.data / "recordings").mkdir()
        self.voice = str(make_pack(self.data))
        self.store = Store(":memory:")
        self.clock = Clock(at("2026-10-28 17:59:30"))
        self.station = Station(self.store, self.data, output=SilentOutput(realtime=False), clock=self.clock, rate=8000)
        fmt = {"interval": "none", "callsign_repeats": 1}
        self.sched = self.store.save_schedule(Schedule(name="A", times=["18:00"], voice=self.voice, format=fmt,
                                                       filler_min=3, filler_max=3))

    async def asyncTearDown(self):
        await self.station.stop()
        self.tmp.cleanup()

    async def test_message_goes_out_and_is_logged(self):
        m = self.store.add_message("12345 67890")
        entry = await self.station.transmit(self.sched)
        log = self.store.log_entry(entry)
        self.assertEqual((log["status"], log["kind"], log["message_ids"]), ("ok", "message", str(m.id)))
        self.assertIn("12345 67890", log["transcript"])
        self.assertTrue((self.data / "recordings" / log["recording"]).is_file())
        self.assertEqual(self.store.message(m.id).status, "done")

    async def test_filler_when_empty(self):
        log = self.store.log_entry(await self.station.transmit(self.sched))
        self.assertEqual(log["kind"], "filler")
        groups_line = log["transcript"].splitlines()[2]  # ATTENTION…, GROUPS 3 3, then the groups
        self.assertEqual(len(groups_line.split()), 3)

    async def test_null_and_skip(self):
        self.sched.filler = "null"
        self.assertEqual(self.store.log_entry(await self.station.transmit(self.sched))["kind"], "null")
        self.sched.filler = "skip"
        self.assertIsNone(await self.station.transmit(self.sched))

    async def test_discreet_log(self):
        self.store.set("discreet", True)
        self.store.add_message("12345")
        log = self.store.log_entry(await self.station.transmit(self.sched))
        self.assertEqual((log["kind"], log["message_ids"], log["transcript"], log["recording"]), ("", "", "", ""))

    async def test_scheduler_starts_ahead_and_waits(self):
        self.store.set("lead_seconds", 20)
        self.station.replan(self.clock())
        self.assertEqual(self.station.tick(self.clock()), [])  # 30 s ahead: too early
        self.clock.now = at("2026-10-28 17:59:45")
        tasks = self.station.tick(self.clock())
        self.assertEqual(len(tasks), 1)
        await asyncio.sleep(0)  # the transmission waits for its slot (simulated clock does not move)
        self.clock.now = at("2026-10-28 18:00:00")
        await asyncio.gather(*tasks)
        self.assertEqual(self.store.log()[0]["started"], "2026-10-28T18:00:00Z")
        self.assertEqual(self.station.next_runs[self.sched.id], at("2026-10-29 18:00"))

    async def test_never_late(self):
        self.station.replan(at("2026-10-28 17:00"))
        self.clock.now = at("2026-10-28 18:10")  # the machine slept
        self.assertEqual(self.station.tick(self.clock()), [])
        self.assertEqual(self.store.log(), [])

    async def test_errors_are_logged(self):
        self.sched.voice = "no-such-voice"
        log = self.store.log_entry(await self.station.transmit(self.sched))
        self.assertEqual(log["status"], "error")
        self.assertIn("not found", log["error"])

    async def test_old_recordings_go(self):
        await self.station.transmit(self.sched)
        rec = self.store.log()[0]["recording"]
        self.store.set("keep_recordings_days", 1)
        self.station.housekeeping(self.clock() + timedelta(days=2))
        self.assertFalse((self.data / "recordings" / rec).exists())
        self.assertEqual(self.store.log()[0]["recording"], "")


class Api(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        for sub in ("recordings", "pads"):
            (self.data / sub).mkdir()
        self.voice = str(make_pack(self.data))
        self.store = Store(":memory:")
        self.station = Station(self.store, self.data, output=SilentOutput(realtime=False), rate=8000)
        app = make_app(self.store, self.station, self.data, run_station=False)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.h = {"X-EtherDigits": "1"}

    async def asyncTearDown(self):
        await self.client.close()
        await self.station.stop()
        self.tmp.cleanup()

    async def test_local_access_without_password(self):
        r = await self.client.get("/api/session")
        self.assertEqual((await r.json())["logged_in"], True)
        r = await self.client.get("/api/status", headers={"X-Forwarded-For": "203.0.113.9"})
        self.assertEqual(r.status, 401)  # behind a proxy nobody counts as local

    async def test_changes_need_the_header(self):
        r = await self.client.post("/api/messages", json={"groups": "12345"})
        self.assertEqual(r.status, 403)
        r = await self.client.post("/api/messages", json={"groups": "12345"}, headers=self.h)
        self.assertEqual(r.status, 201)

    async def test_password_and_login(self):
        r = await self.client.post("/api/password", json={"new": "short"}, headers=self.h)
        self.assertEqual(r.status, 400)
        r = await self.client.post("/api/password", json={"new": "a long passphrase"}, headers=self.h)
        self.assertEqual(r.status, 200)
        self.client.session.cookie_jar.clear()
        self.assertEqual((await self.client.get("/api/status")).status, 401)
        r = await self.client.post("/api/login", json={"password": "wrong one"})
        self.assertEqual(r.status, 401)
        r = await self.client.post("/api/login", json={"password": "a long passphrase"})
        self.assertEqual(r.status, 200)
        self.assertEqual((await self.client.get("/api/status")).status, 200)

    async def test_login_brake(self):
        self.store.set("admin_password", hash_password("a long passphrase"))
        for _ in range(5):
            await self.client.post("/api/login", json={"password": "nope"})
        r = await self.client.post("/api/login", json={"password": "a long passphrase"})
        self.assertEqual(r.status, 429)

    async def test_token_can_only_submit(self):
        _, token = self.store.add_token("agent")
        auth = {"Authorization": f"Bearer {token}"}
        r = await self.client.post("/api/submit", json={"groups": "12345 67890", "priority": 1}, headers=auth)
        self.assertEqual(r.status, 201)
        self.assertEqual(set(await r.json()), {"id", "groups"})
        self.assertEqual(self.store.messages("queued")[0].source, "api:agent")
        self.store.set("admin_password", hash_password("a long passphrase"))
        self.assertEqual((await self.client.get("/api/messages", headers=auth)).status, 401)
        r = await self.client.post("/api/submit", json={"groups": "12345"}, headers={"Authorization": "Bearer nope"})
        self.assertEqual(r.status, 401)

    async def test_schedule_crud_and_preview(self):
        data = {"name": "Nacht", "times": ["22:00"], "voice": self.voice, "format": {"interval": "none"}}
        r = await self.client.post("/api/schedules", json=data, headers=self.h)
        self.assertEqual(r.status, 201)
        sched = await r.json()
        self.assertEqual(len(sched["upcoming"]), 3)
        r = await self.client.post(f"/api/schedules/{sched['id']}/preview", json={}, headers=self.h)
        self.assertEqual((r.status, r.content_type), (200, "audio/wav"))
        self.assertIn("ATTENTION", r.headers["X-Transcript"])
        bad = dict(data, times=["99:99"])
        r = await self.client.put(f"/api/schedules/{sched['id']}", json=bad, headers=self.h)
        self.assertEqual(r.status, 400)
        r = await self.client.post("/api/schedules", json=dict(data, voice="klingon"), headers=self.h)
        self.assertEqual(r.status, 400)

    async def test_saved_previews_reload_replaced_clips_for_language_and_id(self):
        with patch("etherdigits.voicepack.BUILTIN_DIR", self.data):
            routes = []
            originals = []
            for voice in ("xx", "test-xx"):
                r = await self.client.post("/api/schedules", headers=self.h, json={
                    "name": voice, "enabled": False, "voice": voice,
                    "filler": "null", "format": {"interval": "none"},
                })
                self.assertEqual(r.status, 201)
                route = f"/api/schedules/{(await r.json())['id']}/preview"
                routes.append(route)
                r = await self.client.post(route, json={}, headers=self.h)
                self.assertEqual(r.status, 200)
                originals.append(await r.read())
            self.assertEqual(originals[0], originals[1])

            # Replace a clip with different sound but the same size, without
            # touching pack.json or restarting the station.
            folder = Path(self.voice)
            (folder / "attention.wav").write_bytes((folder / "4.wav").read_bytes())
            updated = []
            for route, original in zip(routes, originals):
                r = await self.client.post(route, json={}, headers=self.h)
                self.assertEqual(r.status, 200)
                audio = await r.read()
                self.assertNotEqual(audio, original)
                updated.append(audio)
            self.assertEqual(updated[0], updated[1])
            self.assertEqual(self.store.log(), [])
            self.assertEqual(self.store.queue_size(), 0)

    async def test_station_encryption_off_by_default(self):
        r = await self.client.post("/api/messages", json={"text": "hallo", "pad": "p"}, headers=self.h)
        self.assertEqual(r.status, 403)

    async def test_station_encryption(self):
        from etherdigits import otp
        pad = otp.new_pad(pages=2, groups_per_page=10)
        r = await self.client.post("/api/pads", json={"name": "p1", "pad": pad.to_json()}, headers=self.h)
        self.assertEqual(r.status, 201)
        self.store.set("station_encryption", True)
        r = await self.client.post("/api/messages", json={"text": "Heute sofort", "pad": "p1"}, headers=self.h)
        self.assertEqual(r.status, 201)
        groups = (await r.json())["groups"]
        stored = otp.load_pad(self.data / "pads" / "p1.json")
        self.assertEqual(stored.used, [groups[0]])
        self.assertEqual(otp.decrypt(groups, otp.Pad.from_json(pad.to_json())), "HEUTE SOFORT")
        r = await self.client.post("/api/pads", json={"name": "../evil", "pad": pad.to_json()}, headers=self.h)
        self.assertEqual(r.status, 400)

    async def test_bad_json(self):
        r = await self.client.post("/api/messages", data="nope", headers=dict(self.h, **{"Content-Type": "application/json"}))
        self.assertEqual(r.status, 400)

    async def test_pad_tool_download(self):
        r = await self.client.get("/pad_tool.html")
        self.assertEqual(r.status, 200)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertIn('<script id="engine">', await r.text())

    async def test_index_and_headers(self):
        r = await self.client.get("/")
        self.assertEqual(r.status, 200)
        self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
