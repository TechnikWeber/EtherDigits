"""Schedules: when a station transmits, and how it sounds.

All times are UTC. Listeners abroad cannot be expected to know about
daylight saving time at the station, and real numbers stations always
announced their schedules in UTC.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta, timezone

from .groups import GroupError
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
        if self.effect not in EFFECTS:
            raise ScheduleError(f"effect must be one of {', '.join(EFFECTS)}")
        if self.filler not in FILLERS:
            raise ScheduleError(f"filler must be one of {', '.join(FILLERS)}")
        if not 1 <= int(self.filler_min) <= int(self.filler_max) <= 500:
            raise ScheduleError("filler length: 1 to 500 groups, minimum not above maximum")
        if not 1 <= int(self.max_messages) <= 20:
            raise ScheduleError("messages per transmission: 1 to 20")
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
        if self.kind == "times":
            day = after.replace(hour=0, minute=0, second=0, microsecond=0)
            for offset in range(8):
                date = day + timedelta(days=offset)
                if date.weekday() not in self.weekdays:
                    continue
                for t in self.times:
                    hour, minute = map(int, t.split(":"))
                    candidate = date.replace(hour=hour, minute=minute)
                    if candidate > after:
                        return candidate
            return None
        step = timedelta(minutes=int(self.interval_minutes))
        base = EPOCH + timedelta(minutes=int(self.offset_minutes))
        n = (after - base) // step + 1
        candidate = base + n * step
        # Skip runs on days that are switched off; a week holds at most 10080 runs.
        for _ in range(10081):
            if candidate.weekday() in self.weekdays:
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
