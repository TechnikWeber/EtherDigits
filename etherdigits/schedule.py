"""Schedules: when a station transmits, and how it sounds.

Times are in the schedule's time zone, UTC by default. Real numbers stations
announced their schedules in UTC, so listeners abroad need not know about
daylight saving time at the station; with a zone such as Europe/Berlin,
18:00 stays 18:00 local time all year.

Two kinds:
- "times": fixed times on chosen weekdays.
- "interval": every N minutes on chosen weekdays, either around the clock
  (on a fixed UTC grid) or inside a daily window such as 18:00 to 19:00,
  starting at the window's beginning. A window may run past midnight; it
  belongs to the weekday it starts on.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from .groups import GroupError
from .radio import RIG_MODES
from .render import EFFECTS
from .script import Format

KINDS = ("times", "interval")
FILLERS = ("random", "null", "skip")
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
EPOCH = datetime(1970, 1, 5, tzinfo=timezone.utc)  # a Monday, so weekly maths stays simple


class ScheduleError(ValueError):
    pass


@dataclass
class Schedule:
    id: int | None = None
    name: str = "Station"
    enabled: bool = True
    kind: str = "times"                       # times | interval
    times: list[str] = field(default_factory=lambda: ["18:00"])  # HH:MM UTC, for kind "times"
    weekdays: list[int] = field(default_factory=lambda: list(range(7)))  # 0 = Monday
    interval_minutes: int = 60                # for kind "interval"
    offset_minutes: int = 0                   # shift of the interval grid
    voice: str = "de"
    effect: str = "none"
    format: dict = field(default_factory=dict)  # Format fields that differ from the defaults
    filler: str = "random"                    # random groups | "no message" | skip (send nothing)
    filler_min: int = 10
    filler_max: int = 30
    max_messages: int = 1                     # messages per transmission
    window_start: str = ""                    # interval only: "18:00"; "" = around the clock
    window_end: str = ""                      # interval only: "19:00" (last slot at or before it)
    timezone: str = "UTC"                     # IANA name, e.g. Europe/Berlin
    frequency_khz: float = 0.0                # 0 = leave the radio as it is (needs CAT)
    rig_mode: str = ""                        # e.g. AM, USB; "" = leave as it is

    def validate(self) -> "Schedule":
        self.name = (self.name or "").strip()[:60]
        self.enabled = bool(self.enabled)
        try:
            for name in ("interval_minutes", "offset_minutes", "filler_min", "filler_max", "max_messages"):
                setattr(self, name, int(getattr(self, name)))
        except (TypeError, ValueError) as exc:
            raise ScheduleError(f"not a whole number: {exc}") from exc
        if not isinstance(self.times, list) or not isinstance(self.weekdays, list) or not isinstance(self.format, dict):
            raise ScheduleError("times and weekdays must be lists, format an object")
        if not self.name:
            raise ScheduleError("the schedule needs a name")
        if self.kind not in KINDS:
            raise ScheduleError(f"kind must be one of {', '.join(KINDS)}")
        self.times = sorted({str(t).strip() for t in self.times if str(t).strip()})
        for t in self.times:
            if not _TIME.match(t):
                raise ScheduleError(f"time {t!r} must look like 18:30 (UTC)")
        if self.kind == "times" and not self.times:
            raise ScheduleError("add at least one time")
        self.weekdays = sorted({int(d) for d in self.weekdays})
        if not self.weekdays or any(d < 0 or d > 6 for d in self.weekdays):
            raise ScheduleError("pick at least one weekday")
        if not 1 <= int(self.interval_minutes) <= 10080:
            raise ScheduleError("the interval must be between 1 minute and 7 days")
        if not 0 <= int(self.offset_minutes) < int(self.interval_minutes):
            raise ScheduleError("the offset must be smaller than the interval")
        self.timezone = str(self.timezone or "UTC").strip()
        try:
            zone(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ScheduleError(f"unknown time zone {self.timezone!r} (e.g. UTC, Europe/Berlin)") from exc
        self.window_start, self.window_end = str(self.window_start or "").strip(), str(self.window_end or "").strip()
        if self.window_start or self.window_end:
            for t in (self.window_start, self.window_end):
                if not _TIME.match(t):
                    raise ScheduleError(f"window time {t!r} must look like 18:30; give both start and end")
            if self.window_start == self.window_end:
                raise ScheduleError("the window needs different start and end times")
        if self.effect not in EFFECTS:
            raise ScheduleError(f"effect must be one of {', '.join(EFFECTS)}")
        if self.filler not in FILLERS:
            raise ScheduleError(f"filler must be one of {', '.join(FILLERS)}")
        if not 1 <= int(self.filler_min) <= int(self.filler_max) <= 500:
            raise ScheduleError("filler length: 1 to 500 groups, minimum not above maximum")
        if not 1 <= int(self.max_messages) <= 20:
            raise ScheduleError("messages per transmission: 1 to 20")
        try:
            self.frequency_khz = float(self.frequency_khz or 0)
        except (TypeError, ValueError) as exc:
            raise ScheduleError("the frequency must be a number in kHz") from exc
        if self.frequency_khz and not 100 <= self.frequency_khz <= 10_000_000:
            raise ScheduleError("the frequency must be between 100 kHz and 10 GHz (in kHz), or 0")
        self.rig_mode = str(self.rig_mode or "").upper()
        if self.rig_mode not in RIG_MODES:
            raise ScheduleError(f"mode must be one of {', '.join(m for m in RIG_MODES if m)}")
        try:
            self.station_format()
        except GroupError as exc:
            raise ScheduleError(str(exc)) from exc
        return self

    def station_format(self) -> Format:
        return Format.from_dict(dict(self.format))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Schedule":
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ScheduleError("unknown schedule setting(s): " + ", ".join(sorted(unknown)))
        try:
            return cls(**data).validate()
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ScheduleError):
                raise
            raise ScheduleError(f"invalid schedule: {exc}") from exc

    def next_run(self, after: datetime) -> datetime | None:
        """The first transmission strictly after `after` (aware UTC), or None when disabled."""
        if not self.enabled:
            return None
        after = after.astimezone(timezone.utc)
        tz = zone(self.timezone)
        if self.kind == "times":
            minutes = [_minutes(t) for t in self.times]
        elif self.window_start:
            start, end = _minutes(self.window_start), _minutes(self.window_end)
            if end < start:
                end += 1440  # runs past midnight
            minutes = list(range(start, end + 1, int(self.interval_minutes)))
        else:
            return self._next_on_grid(after, tz)
        # Wall-clock times in the schedule's zone; yesterday too, for windows past midnight.
        today = after.astimezone(tz).date()
        for offset in range(-1, 9):
            day = today + timedelta(days=offset)
            if day.weekday() not in self.weekdays:
                continue
            midnight = datetime(day.year, day.month, day.day, tzinfo=tz)
            for m in minutes:
                candidate = (midnight + timedelta(minutes=m)).astimezone(timezone.utc)
                if candidate > after:
                    return candidate
        return None

    def _next_on_grid(self, after: datetime, tz) -> datetime | None:
        """Every N minutes around the clock, on a fixed UTC grid (shifted by the offset)."""
        step = timedelta(minutes=int(self.interval_minutes))
        base = EPOCH + timedelta(minutes=int(self.offset_minutes))
        n = (after - base) // step + 1
        candidate = base + n * step
        # Skip runs on days that are switched off; a week holds at most 10080 runs.
        for _ in range(10081):
            if candidate.astimezone(tz).weekday() in self.weekdays:
                return candidate
            candidate += step
        return None

    def upcoming(self, after: datetime, count: int = 5) -> list[datetime]:
        runs: list[datetime] = []
        t = after
        while len(runs) < count:
            t = self.next_run(t)
            if t is None:
                break
            runs.append(t)
        return runs


def _minutes(text: str) -> int:
    hour, minute = map(int, text.split(":"))
    return hour * 60 + minute


@lru_cache(maxsize=64)
def zone(name: str):
    if name in ("UTC", "Etc/UTC", "Z"):
        return timezone.utc
    return ZoneInfo(name)


def time_zones() -> list[str]:
    try:
        return ["UTC"] + sorted(z for z in available_timezones() if "/" in z and not z.startswith(("Etc/", "SystemV/")))
    except Exception:  # no time zone data on this system
        return ["UTC"]


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScheduleError(f"not a date and time: {text!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
