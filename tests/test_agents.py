"""Independent agent queues, schedules, migration and multi-recipient submission."""

import asyncio
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer

from etherdigits import otp
from etherdigits.schedule import Schedule, ScheduleError, schedule_conflicts
from etherdigits.server import make_app
from etherdigits.station import SilentOutput, Station
from etherdigits.store import SCHEMA, Store, StoreError

from .helpers import make_pack
from .test_service import Clock, at


class AgentQueue(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.a = self.store.save_agent("Agent A")["id"]
        self.b = self.store.save_agent("Agent B")["id"]
        self.sa = self.store.save_schedule(Schedule(name="Afternoon", agent_id=self.a))
        self.sb = self.store.save_schedule(Schedule(name="Evening", agent_id=self.b))
        self.general = self.store.save_schedule(Schedule(name="General"))
        self.now = "2026-10-28T12:00:00Z"

    def due_ids(self, schedule):
        return [m.id for m in self.store.due(schedule.id, self.now, 20)]

    def test_recipient_queues_and_repeats_are_independent(self):
        a, b = self.store.add_messages("12345 67890", agent_ids=[self.a, self.b], transmissions=2)
        general = self.store.add_message("11111", priority=2)
        self.assertEqual(self.due_ids(self.sa), [a.id])
        self.assertEqual(self.due_ids(self.sb), [b.id])
        self.assertEqual(self.due_ids(self.general), [general.id])
        self.store.mark_sent([a.id], self.now)
        self.assertEqual(self.store.message(a.id).sent_count, 1)
        self.assertEqual(self.store.message(b.id).sent_count, 0)
        self.store.mark_sent([a.id], self.now)
        self.assertIsNone(self.store.message(a.id).groups)
        self.assertEqual(self.store.message(b.id).groups, ["12345", "67890"])
        self.assertEqual(self.due_ids(self.sa), [])
        self.assertEqual(self.due_ids(self.sb), [b.id])

    def test_schedule_binding_infers_agent_and_keeps_recipient_on_delete(self):
        second = self.store.save_schedule(Schedule(name="A late", agent_id=self.a))
        message = self.store.add_message("12345", schedule_id=self.sa.id)
        self.assertEqual(message.agent_id, self.a)
        self.assertEqual(self.due_ids(second), [])
        self.store.delete_schedule(self.sa.id)
        self.assertEqual(self.due_ids(second), [message.id])
        self.assertEqual(self.due_ids(self.sb), [])
        self.assertEqual(self.due_ids(self.general), [])

    def test_cannot_assign_waiting_messages_to_another_agent(self):
        self.store.add_message("12345", schedule_id=self.sa.id)
        with self.assertRaises(StoreError):
            self.store.save_schedule(replace(self.sa, agent_id=self.b))
        for schedule in (self.sb, self.general):
            with self.assertRaises(StoreError):
                self.store.add_message("12345", schedule_id=schedule.id, agent_id=self.a)

    def test_agent_deletion_cancels_only_their_deliveries(self):
        a, b = self.store.add_messages("12345", agent_ids=[self.a, self.b])
        kept = self.store.add_message("22222", agent_id=self.a, burn=False)
        self.assertTrue(self.store.delete_agent(self.a))
        self.assertIsNone(self.store.schedule(self.sa.id))
        self.assertEqual(self.store.message(a.id).status, "cancelled")
        self.assertIsNone(self.store.message(a.id).groups)
        self.assertEqual(self.store.message(kept.id).groups, ["22222"])
        self.assertEqual(self.due_ids(self.sb), [b.id])
        self.assertEqual(self.due_ids(self.general), [])
        self.assertGreater(self.store.save_agent("New agent")["id"], self.b)

    def test_batch_is_atomic_and_deduplicates_recipients(self):
        self.assertEqual(len(self.store.add_messages("12345", agent_ids=[self.a, self.a])), 1)
        before = self.store.queue_size()
        real_add = self.store.add_message
        def failing_add(*args, **kwargs):
            if kwargs["agent_id"] == self.b:
                raise StoreError("simulated storage failure")
            return real_add(*args, **kwargs)
        with patch.object(self.store, "add_message", side_effect=failing_add):
            with self.assertRaises(StoreError):
                self.store.add_messages("22222", agent_ids=[self.a, self.b])
        self.assertEqual(self.store.queue_size(), before)

    def test_validation(self):
        for ids in ([], None, "1", [True], [1.5], ["1"], [0], [self.a, 999], [self.a] * 101):
            with self.subTest(ids=ids), self.assertRaises(StoreError):
                self.store.add_messages("12345", agent_ids=ids)
        for name in ("", " ", None, [], "x" * 61):
            with self.subTest(name=name), self.assertRaises(StoreError):
                self.store.save_agent(name)
        with self.assertRaises(StoreError):
            self.store.save_schedule(Schedule(agent_id=999))
        with self.assertRaises(ScheduleError):
            Schedule(agent_id=True).validate()
        self.assertEqual(self.store.queue_size(), 0)

    def test_migration_preserves_old_messages_and_schedules(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "old.sqlite"
            db = sqlite3.connect(path)
            old_schema = "\n".join(line for line in SCHEMA.splitlines()
                                   if "agent_id INTEGER" not in line and "CREATE TABLE IF NOT EXISTS agents" not in line)
            old_schema = old_schema.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "INTEGER PRIMARY KEY")
            db.executescript(old_schema)
            db.execute("INSERT INTO schedules (id, data) VALUES (1, ?)", (json.dumps({"name": "Old"}),))
            db.execute("INSERT INTO messages (created, groups, group_count, schedule_id) VALUES (?, '12345', 1, 1)",
                       (self.now,))
            db.commit()
            db.close()
            for _ in range(2):  # migration is idempotent
                store = Store(path)
                try:
                    self.assertIsNone(store.schedule(1).agent_id)
                    self.assertIsNone(store.message(1).agent_id)
                    self.assertEqual(store.due(1, self.now, 1)[0].groups, ["12345"])
                    self.assertEqual(store.agents(), [])
                finally:
                    store.close()
            store = Store(path)
            try:
                store.cancel_message(1)
                store.delete_message(1)
            finally:
                store.close()
            store = Store(path)
            try:
                self.assertGreater(store.add_message("22222").id, 1)
                self.assertEqual(store._q("PRAGMA integrity_check")[0][0], "ok")
            finally:
                store.close()

    def test_late_completion_preserves_cancelled_and_finished_state(self):
        cancelled = self.store.add_message("12345", agent_id=self.a)
        self.store.cancel_message(cancelled.id)
        self.store.mark_sent([cancelled.id], self.now)
        self.assertEqual(self.store.message(cancelled.id).status, "cancelled")
        self.assertEqual(self.store.message(cancelled.id).sent_count, 0)
        done = self.store.add_message("22222", agent_id=self.b)
        self.store.mark_sent([done.id], self.now)
        self.store.mark_sent([done.id], self.now)
        self.assertEqual(self.store.message(done.id).sent_count, 1)

    def test_conflict_detection_uses_timezones_weekdays_and_enabled_state(self):
        berlin = replace(self.sa, times=["13:00"], timezone="Europe/Berlin", weekdays=[0])
        utc = replace(self.sb, times=["12:00"], timezone="UTC", weekdays=[0])
        conflicts = schedule_conflicts([berlin, utc], at("2026-10-28 00:00"))
        self.assertEqual(conflicts[berlin.id][0]["at"], "2026-11-02T12:00:00Z")
        self.assertEqual(schedule_conflicts([berlin, replace(utc, weekdays=[1])], at("2026-10-28")), {})
        self.assertEqual(schedule_conflicts([berlin, replace(utc, enabled=False)], at("2026-10-28")), {})

    def test_conflicts_include_windows_past_midnight(self):
        overnight = replace(self.sa, kind="interval", window_start="23:00", window_end="01:00",
                            interval_minutes=60, weekdays=[4])
        saturday = replace(self.sb, times=["00:00"], weekdays=[5])
        conflicts = schedule_conflicts([overnight, saturday], at("2026-10-28"))
        self.assertEqual(conflicts[self.sa.id][0]["at"], "2026-10-31T00:00:00Z")


class AgentApi(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        (self.data / "pads").mkdir()
        self.voice = str(make_pack(self.data))
        self.store = Store(":memory:")
        self.clock = Clock(at("2026-10-28 11:59:30"))
        self.output = SilentOutput(realtime=False)
        self.station = Station(self.store, self.data, output=self.output, clock=self.clock, rate=8000)
        self.client = TestClient(TestServer(make_app(self.store, self.station, self.data, run_station=False)))
        await self.client.start_server()
        self.h = {"X-EtherDigits": "1"}

    async def asyncTearDown(self):
        await self.client.close()
        await self.station.stop()
        self.store.close()
        self.tmp.cleanup()

    async def agent(self, name):
        response = await self.client.post("/api/agents", json={"name": name}, headers=self.h)
        self.assertEqual(response.status, 201)
        return (await response.json())["id"]

    async def schedule(self, aid, start, end, interval, frequency):
        response = await self.client.post("/api/schedules", headers=self.h, json={
            "name": f"Agent {aid}", "agent_id": aid, "kind": "interval", "window_start": start,
            "window_end": end, "interval_minutes": interval, "frequency_khz": frequency,
            "rig_mode": "AM", "timezone": "Europe/Berlin", "voice": self.voice,
            "format": {"interval": "none", "message_repeats": 1}, "filler": "skip",
        })
        self.assertEqual(response.status, 201, await response.text())
        return self.store.schedule((await response.json())["id"])

    async def test_agent_crud_and_access(self):
        response = await self.client.post("/api/agents", json={"name": "A"})
        self.assertEqual(response.status, 403)
        aid = await self.agent("A")
        response = await self.client.put(f"/api/agents/{aid}", json={"name": "Renamed"}, headers=self.h)
        self.assertEqual((await response.json())["name"], "Renamed")
        response = await self.client.get("/api/agents")
        self.assertEqual(await response.json(), [{"id": aid, "name": "Renamed"}])
        response = await self.client.delete(f"/api/agents/{aid}", headers=self.h)
        self.assertEqual(response.status, 200)
        response = await self.client.delete(f"/api/agents/{aid}", headers=self.h)
        self.assertEqual(response.status, 404)

    async def test_two_agents_transmit_in_their_own_windows_and_frequencies(self):
        a, b = await self.agent("A"), await self.agent("B")
        sa = await self.schedule(a, "13:00", "14:00", 15, 6000)
        sb = await self.schedule(b, "18:00", "19:00", 30, 7200)
        response = await self.client.post("/api/messages", headers=self.h, json={
            "groups": "12345 67890", "agent_ids": [a, b], "transmissions": 2,
        })
        self.assertEqual(response.status, 201)
        ma, mb = (await response.json())["messages"]
        self.station.replan(self.clock())
        self.assertEqual(self.station.next_runs, {sa.id: at("2026-10-28 12:00"), sb.id: at("2026-10-28 17:00")})
        self.output.cfg["cat"] = True
        with patch("etherdigits.station.Rig") as rig:
            for time in ("12:00", "12:15", "17:00", "17:30"):
                self.clock.now = at(f"2026-10-28 {time}")
                await asyncio.gather(*self.station.tick(self.clock()))
                if time == "12:15":
                    self.assertIsNone(self.store.message(ma["id"]).groups)
                    self.assertEqual(self.store.message(mb["id"]).sent_count, 0)
            self.assertEqual([call.args[0] for call in rig.return_value.set_frequency.call_args_list],
                             [6_000_000, 6_000_000, 7_200_000, 7_200_000])
        self.assertEqual(self.store.message(mb["id"]).status, "done")
        self.assertEqual([entry["message_ids"] for entry in reversed(self.store.log())],
                         [str(ma["id"]), str(ma["id"]), str(mb["id"]), str(mb["id"])])
        # Saving changed timing/frequency causes the running scheduler to replan.
        self.store.save_schedule(replace(sb, window_start="20:00", window_end="21:00", interval_minutes=10,
                                         frequency_khz=7300))
        self.assertEqual(self.station.tick(self.clock()), [])
        self.assertEqual(self.station.next_runs[sb.id], at("2026-10-28 19:00"))

    async def test_invalid_batch_never_partially_queues(self):
        aid = await self.agent("A")
        schedule = await self.schedule(aid, "13:00", "14:00", 15, 6000)
        for data in ({"agent_ids": [aid, 999]}, {"agent_ids": []}, {"agent_ids": [True]},
                     {"agent_ids": [aid], "agent_id": aid}, {"agent_ids": [aid], "schedule_id": 999}):
            response = await self.client.post("/api/messages", headers=self.h, json={"groups": "12345", **data})
            self.assertEqual(response.status, 400, await response.text())
        self.assertEqual(self.store.queue_size(), 0)
        response = await self.client.post("/api/messages", headers=self.h, json={
            "groups": "12345", "agent_id": aid, "schedule_id": schedule.id,
        })
        self.assertEqual((await response.json())["agent_id"], aid)

    async def test_token_batch_and_legacy_response(self):
        a, b = await self.agent("A"), await self.agent("B")
        _, token = self.store.add_token("remote")
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.client.post("/api/submit", headers=headers,
                                          json={"groups": "12345", "agent_ids": [a, b]})
        self.assertEqual(response.status, 201)
        result = await response.json()
        self.assertEqual(len(result["messages"]), 2)
        self.assertEqual(set(result["messages"][0]), {"id", "groups"})
        response = await self.client.post("/api/submit", headers=headers, json={"groups": "11111"})
        self.assertEqual(set(await response.json()), {"id", "groups"})
        response = await self.client.get("/api/agents", headers={**headers, "X-Forwarded-For": "192.0.2.1"})
        self.assertEqual(response.status, 401)

    async def test_invalid_recipient_does_not_consume_pad(self):
        self.store.set("station_encryption", True)
        pad = otp.new_pad(pages=2, groups_per_page=10)
        path = self.data / "pads" / "test.json"
        otp.save_pad(pad, path)
        response = await self.client.post("/api/messages", headers=self.h, json={
            "text": "Hallo", "pad": "test", "agent_ids": [999],
        })
        self.assertEqual(response.status, 400)
        self.assertEqual(otp.load_pad(path).used, [])

    async def test_delete_agent_during_preparation_stops_delivery(self):
        aid = await self.agent("A")
        schedule = await self.schedule(aid, "13:00", "14:00", 15, 6000)
        message = self.store.add_message("12345", agent_id=aid)
        render = self.station.render
        def delete_while_rendering(planned):
            audio = render(planned)
            self.store.delete_agent(aid)
            return audio
        with patch.object(self.station, "render", side_effect=delete_while_rendering):
            entry = await self.station.transmit(schedule)
        self.assertEqual(self.store.log_entry(entry)["status"], "stopped")
        self.assertEqual(self.store.message(message.id).sent_count, 0)
        self.assertEqual(self.store.message(message.id).status, "cancelled")

    async def test_delete_during_play_does_not_burn_unsent_replacement(self):
        a, b = await self.agent("A"), await self.agent("B")
        schedule = await self.schedule(a, "13:00", "14:00", 15, 6000)
        original = self.store.add_message("12345", agent_id=a)
        original_play = self.output.play
        replacement = None
        async def delete_and_replace(*args):
            nonlocal replacement
            self.assertIsNotNone(self.station.current)
            self.store.delete_agent(a)
            self.store.delete_message(original.id)
            replacement = self.store.add_message("98765", agent_id=b)
            return await original_play(*args)
        with patch.object(self.output, "play", side_effect=delete_and_replace):
            log_id = await self.station.transmit(schedule)
        self.assertNotEqual(replacement.id, original.id)
        pending = self.store.message(replacement.id)
        self.assertEqual((pending.status, pending.sent_count, pending.groups), ("queued", 0, ["98765"]))
        self.assertNotIn("98765", self.store.log_entry(log_id)["transcript"])

    async def test_identical_slots_prioritize_messages_then_take_turns(self):
        a, b = await self.agent("A"), await self.agent("B")
        sa = await self.schedule(a, "13:00", "14:00", 15, 6000)
        sb = await self.schedule(b, "13:00", "14:00", 15, 7200)
        self.store.save_schedule(replace(sa, filler="random", filler_min=1, filler_max=1))
        self.store.save_schedule(replace(sb, filler="random", filler_min=1, filler_max=1))
        # Filler for A cannot block B's waiting message, even though A was created first.
        mb = self.store.add_message("22222", agent_id=b, transmissions=3)
        self.station.replan(self.clock())
        self.clock.now = at("2026-10-28 12:00")
        await asyncio.gather(*self.station.tick(self.clock()))
        self.assertEqual(self.store.message(mb.id).sent_count, 1)
        ma = self.store.add_message("11111", agent_id=a, transmissions=2)
        # Both now have work. The least recently served wins; this survives restart.
        await self.station.stop()
        self.station = Station(self.store, self.data, output=self.output, clock=self.clock, rate=8000)
        self.station.replan(self.clock())
        for minute in (15, 30, 45):
            self.clock.now = at(f"2026-10-28 12:{minute}")
            await asyncio.gather(*self.station.tick(self.clock()))
        self.assertEqual(self.store.message(ma.id).sent_count, 2)
        self.assertEqual(self.store.message(mb.id).sent_count, 2)
        winners = [e["schedule_id"] for e in reversed(self.store.log()) if e["status"] == "ok"]
        self.assertEqual(winners, [sb.id, sa.id, sb.id, sa.id])
        listed = await (await self.client.get("/api/schedules")).json()
        self.assertEqual(listed[0]["conflicts"][0]["schedule_id"], sb.id)
        self.assertEqual(listed[1]["conflicts"][0]["schedule_id"], sa.id)
        # A GET response can still be used as the body of a PUT.
        response = await self.client.put(f"/api/schedules/{sa.id}", headers=self.h, json=listed[0])
        self.assertEqual(response.status, 200)

    async def test_rejected_encrypted_submissions_leave_pad_unchanged(self):
        self.store.set("station_encryption", True)
        aid = await self.agent("A")
        path = self.data / "pads" / "p.json"
        otp.save_pad(otp.new_pad(pages=2, groups_per_page=10), path)
        before = path.read_bytes()
        for options in ({"transmissions": 0}, {"transmissions": 1.5}, {"priority": 9},
                        {"expires_minutes": 0}, {"expires_minutes": True}, {"expires": "invalid"},
                        {"expires": ["2026-01-01"]}, {"not_before": "2026-10-29", "expires": "2026-10-28"},
                        {"schedule_id": True}, {"agent_ids": [aid, 999]}):
            with self.subTest(options=options):
                response = await self.client.post("/api/messages", headers=self.h, json={
                    "text": "Hallo", "pad": "p", **options,
                })
                self.assertEqual(response.status, 400, await response.text())
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(self.store.queue_size(), 0)

    async def test_encrypted_batch_uses_one_pad_page_and_single_schedule_works(self):
        self.store.set("station_encryption", True)
        a, b = await self.agent("A"), await self.agent("B")
        schedule = await self.schedule(a, "13:00", "14:00", 15, 6000)
        path = self.data / "pads" / "p.json"
        pad = otp.new_pad(pages=3, groups_per_page=10)
        otp.save_pad(pad, path)
        response = await self.client.post("/api/messages", headers=self.h, json={
            "text": "Hallo", "pad": "p", "agent_ids": [a, b],
        })
        self.assertEqual(response.status, 201, await response.text())
        messages = (await response.json())["messages"]
        self.assertEqual(messages[0]["groups"], messages[1]["groups"])
        self.assertEqual(otp.decrypt(messages[0]["groups"], pad), "HALLO")
        self.assertEqual(len(otp.load_pad(path).used), 1)
        response = await self.client.post("/api/messages", headers=self.h, json={
            "text": "Morgen", "pad": "p", "agent_ids": [a], "schedule_id": schedule.id,
        })
        self.assertEqual(response.status, 201, await response.text())
        self.assertEqual((await response.json())["messages"][0]["agent_id"], a)
        self.assertEqual(len(otp.load_pad(path).used), 2)
