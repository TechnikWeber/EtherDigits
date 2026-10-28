"""The station: picks messages, fills quiet slots, renders ahead, transmits on time.

A transmission is prepared `lead_seconds` before its slot, so rendering
never makes it late. When the queue is empty the station still transmits
filler (random groups that look exactly like a real message) unless the
schedule says otherwise: a station that only speaks when there is news
gives its traffic away.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from .clock import WARN_SECONDS, ClockError, sntp_offset
from .groups import random_groups
from .radio import Meter, Rig, Transmitter
from .stream import StreamSink
from .render import DEFAULT_RATE, render, tone, write_wav
from .schedule import Schedule, iso, utcnow
from .script import Transmission, build_script, transcript
from .store import Store
from .voicepack import VoicePack, find_pack

log = logging.getLogger("etherdigits.station")


class SilentOutput(Transmitter):
    """No radio: real time and a moving meter, no sound. Tests use realtime=False."""

    def __init__(self, realtime: bool = True):
        super().__init__({"mode": "silent"}, realtime=realtime)


@dataclass
class Planned:
    schedule: Schedule
    kind: str                       # message | filler | null | test
    transmission: Transmission
    message_ids: list[int] = field(default_factory=list)

    @property
    def steps(self):
        return build_script(self.transmission)

    def text(self) -> str:
        return transcript(self.steps, self.transmission.format)


class Station:
    def __init__(self, store: Store, data_dir: Path, output=None, clock=None, rate: int = DEFAULT_RATE):
        self.store = store
        self.data_dir = Path(data_dir)
        self.fixed_output = output  # tests pass one; otherwise it comes from the settings
        self.clock_offset = 0.0     # seconds the system clock is behind the time server
        self.clock_status: dict = {"checked": None, "offset": None, "server": "", "error": ""}
        self.clock = clock or self.corrected_now
        self.last_tick: datetime | None = None
        self.stream = StreamSink(rate)
        self._last_clock_check: datetime | None = None
        self._clock_task: asyncio.Task | None = None
        self.meter = Meter()
        self._stop = threading.Event()
        self.rate = rate
        self.current: dict | None = None
        self.next_runs: dict[int, datetime | None] = {}
        self._packs: dict[str, VoicePack] = {}
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self._version = -1
        self._stopping = False
        self._last_housekeeping: datetime | None = None

    # --- planning ----------------------------------------------------------

    def pack(self, voice: str) -> VoicePack:
        if voice not in self._packs:
            self._packs[voice] = find_pack(voice)
        return self._packs[voice]

    def plan(self, schedule: Schedule, now: datetime | None = None, test: bool = False) -> Planned | None:
        """What this schedule would send now. Nothing is consumed until the transmission succeeds."""
        fmt = schedule.station_format()
        if test:
            return Planned(schedule, "test", Transmission([random_groups(10)], fmt))
        due = self.store.due(schedule.id, iso(now or self.clock()), schedule.max_messages)
        if due:
            return Planned(schedule, "message", Transmission([m.groups for m in due], fmt), [m.id for m in due])
        if schedule.filler == "skip":
            return None
        if schedule.filler == "null":
            return Planned(schedule, "null", Transmission([], fmt))
        count = schedule.filler_min + secrets.randbelow(schedule.filler_max - schedule.filler_min + 1)
        # The first group plays the page id of a real message: random as well.
        return Planned(schedule, "filler", Transmission([random_groups(count)], fmt))

    def render(self, planned: Planned) -> np.ndarray:
        return render(planned.steps, self.pack(planned.schedule.voice), rate=self.rate, effect=planned.schedule.effect)

    # --- transmitting ------------------------------------------------------

    def transmitter(self) -> Transmitter:
        if self.fixed_output is not None:
            return self.fixed_output
        return Transmitter(self.store.get("output") or {})

    @property
    def output(self) -> Transmitter:
        return self.transmitter()

    def _log_skip(self, schedule: Schedule, when: datetime, status: str, error: str) -> int:
        return self.store.add_log(started=iso(when), schedule_id=schedule.id, schedule_name=schedule.name,
                                  status=status, error=error)

    async def transmit(self, schedule: Schedule, at: datetime | None = None, test: bool = False) -> int | None:
        """Prepare, wait for the slot, send, log. Returns the log entry id."""
        discreet = bool(self.store.get("discreet"))
        if self.store.get("tx_blocked"):
            return self._log_skip(schedule, at or self.clock(), "blocked", "the transmitter is locked (emergency stop)")
        if self._lock.locked():
            return self._log_skip(schedule, at or self.clock(), "busy", "another transmission was still on air")
        async with self._lock:
            started = at or self.clock()
            planned = None
            try:
                planned = self.plan(schedule, started, test=test)
                if planned is None:
                    return None
                tx = self.transmitter()
                audio = await asyncio.to_thread(self.render, planned)
                seconds = len(audio) / self.rate
                limit = tx.cfg["max_tx_seconds"]
                if seconds > limit:
                    raise RuntimeError(f"the transmission would last {seconds:.0f} s, the limit is {limit} s")
                await asyncio.to_thread(tx.check)
                await asyncio.to_thread(self._tune, tx, schedule)
                if at is not None:
                    wait = (at - self.clock()).total_seconds()
                    if wait > 0:
                        await asyncio.sleep(wait)
                if self.store.get("tx_blocked"):
                    return self._log_skip(schedule, started, "blocked", "the transmitter is locked (emergency stop)")
                started = self.clock()
                self.current = {"schedule": schedule.name, "schedule_id": schedule.id, "started": iso(started),
                                "duration": round(seconds, 1)}
                self._stop.clear()
                self.stream.push(audio)
                result = await tx.play(audio, self.rate, self.meter, self._stop)
                if result.stopped:
                    # Not fully sent: the messages stay in the queue.
                    return self.store.add_log(started=iso(started), duration=round(result.seconds, 1),
                                              schedule_id=schedule.id, schedule_name=schedule.name,
                                              status="stopped", error="emergency stop",
                                              kind="" if discreet else planned.kind)
                if planned.message_ids:
                    self.store.mark_sent(planned.message_ids, iso(started))
                recording = "" if discreet else await asyncio.to_thread(self._record, audio, started, schedule)
                return self.store.add_log(
                    started=iso(started), duration=round(seconds, 1), schedule_id=schedule.id,
                    schedule_name=schedule.name, status="ok", recording=recording,
                    kind="" if discreet else planned.kind,
                    message_ids="" if discreet else " ".join(map(str, planned.message_ids)),
                    transcript="" if discreet else planned.text(),
                )
            except asyncio.CancelledError:
                self._stop.set()
                if self.current is not None:  # cut off on air by a shutdown: on record, messages stay queued
                    self.store.add_log(started=iso(started), schedule_id=schedule.id, schedule_name=schedule.name,
                                       status="stopped", error="the station was shut down",
                                       kind="" if discreet or planned is None else planned.kind)
                raise
            except Exception as exc:  # the station must survive any single failure
                log.exception("transmission failed")
                return self.store.add_log(started=iso(started), schedule_id=schedule.id, schedule_name=schedule.name,
                                          status="error", error=str(exc)[:300],
                                          kind="" if discreet or planned is None else planned.kind)
            finally:
                self.current = None

    def _tune(self, tx: Transmitter, schedule: Schedule) -> None:
        """Set frequency and mode before the slot, when CAT is on and the schedule names them."""
        if not tx.cfg["cat"] or not (schedule.frequency_khz or schedule.rig_mode):
            return
        rig = Rig(tx.cfg["rig_host"], tx.cfg["rig_port"])
        if schedule.frequency_khz:
            rig.set_frequency(round(schedule.frequency_khz * 1000))
        if schedule.rig_mode:
            rig.set_mode(schedule.rig_mode)

    def emergency_stop(self) -> None:
        """Cut the running transmission at once and lock the transmitter until released."""
        self.store.set("tx_blocked", True)
        self._stop.set()

    async def test_tone(self, seconds: float = 3.0) -> int | None:
        """A 1 kHz tone through the whole chain (PTT included), for setting levels."""
        if self.store.get("tx_blocked"):
            raise RuntimeError("the transmitter is locked (emergency stop)")
        if self._lock.locked():
            raise RuntimeError("a transmission is on air")
        async with self._lock:
            tx = self.transmitter()
            await asyncio.to_thread(tx.check)
            audio = tone(1000, seconds, self.rate, level=0.5)
            started = self.clock()
            self.current = {"schedule": "1 kHz", "schedule_id": None, "started": iso(started), "duration": seconds}
            self._stop.clear()
            try:
                result = await tx.play(audio, self.rate, self.meter, self._stop)
            finally:
                self.current = None
            return self.store.add_log(started=iso(started), duration=round(result.seconds, 1),
                                      schedule_name="1 kHz", kind="test",
                                      status="stopped" if result.stopped else "ok")

    def _record(self, audio: np.ndarray, started: datetime, schedule: Schedule) -> str:
        folder = self.data_dir / "recordings" / started.strftime("%Y-%m-%d")
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{started.strftime('%H%M%S')}-{schedule.id}.wav"
        write_wav(folder / name, audio, self.rate)
        return f"{folder.name}/{name}"

    # --- the scheduler loop --------------------------------------------------

    def corrected_now(self) -> datetime:
        return utcnow() + timedelta(seconds=self.clock_offset)

    def check_clock(self) -> dict:
        """Ask the time server (blocking; run it in a thread)."""
        server = str(self.store.get("ntp_server") or "")
        status = {"checked": iso(utcnow()), "offset": None, "server": server, "error": ""}
        if not server:
            status["error"] = "off"
        else:
            try:
                offset = sntp_offset(server)
                status["offset"] = round(offset, 3)
                if abs(offset) < 86400:  # a day off is a broken answer, not a clock to follow
                    self.clock_offset = offset
            except ClockError as exc:
                status["error"] = str(exc)
        self.clock_status = status
        if status["offset"] is not None and abs(status["offset"]) > WARN_SECONDS:
            log.warning("system clock is %.1f s off; the station uses the time server's time", status["offset"])
        return status

    def replan(self, now: datetime) -> None:
        self.next_runs = {s.id: s.next_run(now) for s in self.store.schedules()}
        self._version = self.store.version

    def tick(self, now: datetime) -> list[asyncio.Task]:
        """Start every transmission whose slot is within the lead time. Called once a second."""
        if self._version != self.store.version:
            self.replan(now)
        lead = timedelta(seconds=int(self.store.get("lead_seconds")))
        started = []
        schedules = {s.id: s for s in self.store.schedules()}
        for sid, slot in list(self.next_runs.items()):
            schedule = schedules.get(sid)
            if schedule is None or slot is None:
                continue
            if slot - now <= lead:
                self.next_runs[sid] = schedule.next_run(slot)
                if slot < now - timedelta(seconds=5):
                    continue  # the machine slept through it; never send late
                started.append(self.spawn(self.transmit(schedule, at=slot)))
        if self._last_housekeeping is None or now - self._last_housekeeping >= timedelta(minutes=1):
            self._last_housekeeping = now
            self.housekeeping(now)
        if self.clock == self.corrected_now and (self._last_clock_check is None
                                                 or now - self._last_clock_check >= timedelta(hours=1)):
            self._last_clock_check = now
            if self._clock_task is None or self._clock_task.done():
                self._clock_task = asyncio.create_task(asyncio.to_thread(self.check_clock))
        self.last_tick = now
        return started

    def spawn(self, coro) -> asyncio.Task:
        """Run a transmission in the background; stop() waits for it."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def housekeeping(self, now: datetime) -> None:
        self.store.expire(iso(now))
        days = int(self.store.get("keep_recordings_days"))
        for rel in self.store.forget_recordings_before(iso(now - timedelta(days=days))):
            path = self.data_dir / "recordings" / rel
            try:
                path.unlink(missing_ok=True)
                if path.parent.is_dir() and not any(path.parent.iterdir()):
                    path.parent.rmdir()
            except OSError:
                log.warning("could not remove old recording %s", path)

    def reconfigure(self) -> None:
        """Apply changed output settings to the long-running parts (the stream)."""
        if self.fixed_output is None:
            self.stream.configure(self.transmitter().cfg)

    async def run(self) -> None:
        log.info("station running")
        self.reconfigure()
        self.replan(self.clock())
        while not self._stopping:
            try:
                self.tick(self.clock())
            except Exception:
                log.exception("scheduler tick failed")
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._stopping = True
        self._stop.set()
        await asyncio.to_thread(self.stream.close)
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def status(self) -> dict:
        discreet = bool(self.store.get("discreet"))
        runs = sorted(((t, sid) for sid, t in self.next_runs.items() if t), key=lambda x: x[0])
        names = {s.id: s.name for s in self.store.schedules()}
        return {
            "now": iso(self.clock()),
            "on_air": self.current,
            "next": [{"schedule_id": sid, "schedule": names.get(sid, "?"), "at": iso(t)} for t, sid in runs[:10]],
            "queue": self.store.queue_size(),
            "output": self.output.name,
            "monitor": bool(self.output.cfg["monitor"]),
            "blocked": bool(self.store.get("tx_blocked")),
            "clock": dict(self.clock_status, warn_seconds=WARN_SECONDS),
            "stream": dict(self.stream.state),
            "discreet": discreet,
        }
