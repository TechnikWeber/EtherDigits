"""SQLite storage: queue, schedules, log, settings, API tokens.

One connection guarded by a lock; the service is small and writes rarely.
Times are ISO strings in UTC ("2026-10-28T18:00:00Z"), so they sort as text.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from .groups import GroupError, parse_groups
from .schedule import Schedule, ScheduleError, iso, parse_iso, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schedules (id INTEGER PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    created TEXT NOT NULL,
    groups TEXT,                    -- NULL once burned
    group_count INTEGER NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 0,
    schedule_id INTEGER,            -- NULL: any schedule
    not_before TEXT,
    expires TEXT,
    transmissions INTEGER NOT NULL DEFAULT 1,
    sent_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'queued',   -- queued | done | expired | cancelled
    burn INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'ui',
    last_sent TEXT
);
CREATE INDEX IF NOT EXISTS messages_queue ON messages (status, priority DESC, created);
CREATE TABLE IF NOT EXISTS log (
    id INTEGER PRIMARY KEY,
    started TEXT NOT NULL,
    duration REAL NOT NULL DEFAULT 0,
    schedule_id INTEGER,
    schedule_name TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT '',          -- message | filler | null | test, empty in discreet mode
    message_ids TEXT NOT NULL DEFAULT '',
    transcript TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,                   -- ok | error | busy
    error TEXT NOT NULL DEFAULT '',
    recording TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS log_started ON log (started DESC);
CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    hash TEXT NOT NULL UNIQUE,
    created TEXT NOT NULL,
    last_used TEXT
);
"""

DEFAULT_SETTINGS = {
    "discreet": False,             # log without kind, message ids and transcript; keep no recordings
    "keep_recordings_days": 7,
    "station_encryption": False,   # allow encrypting on the station with stored pads
    "lead_seconds": 20,            # render this long before the transmission
}

PRIORITIES = (0, 1, 2)             # normal, high, urgent


class StoreError(ValueError):
    pass


@dataclass
class Message:
    id: int
    created: str
    groups: list[str] | None
    group_count: int
    label: str
    priority: int
    schedule_id: int | None
    not_before: str | None
    expires: str | None
    transmissions: int
    sent_count: int
    status: str
    burn: bool
    source: str
    last_sent: str | None

    def to_dict(self, with_groups: bool = True) -> dict:
        d = dict(self.__dict__)
        if not with_groups:
            d["groups"] = None
        return d


def _message(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"], created=row["created"], groups=row["groups"].split() if row["groups"] else None,
        group_count=row["group_count"], label=row["label"], priority=row["priority"],
        schedule_id=row["schedule_id"], not_before=row["not_before"], expires=row["expires"],
        transmissions=row["transmissions"], sent_count=row["sent_count"], status=row["status"],
        burn=bool(row["burn"]), source=row["source"], last_sent=row["last_sent"],
    )


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            if self.path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.executescript(SCHEMA)
        self.version = 0  # bumped whenever schedules change, so the scheduler can replan

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def _x(self, sql: str, args: tuple = ()) -> int:
        with self._lock:
            cur = self._db.execute(sql, args)
            return cur.lastrowid if sql.lstrip().upper().startswith("INSERT") else cur.rowcount

    # --- settings ----------------------------------------------------------

    def settings(self) -> dict:
        """The public settings only; internal keys such as the password hash stay inside."""
        data = dict(DEFAULT_SETTINGS)
        for row in self._q("SELECT key, value FROM settings"):
            if row["key"] in DEFAULT_SETTINGS:
                data[row["key"]] = json.loads(row["value"])
        return data

    def get(self, key: str, default=None):
        rows = self._q("SELECT value FROM settings WHERE key = ?", (key,))
        if rows:
            return json.loads(rows[0]["value"])
        return DEFAULT_SETTINGS.get(key, default)

    def set(self, key: str, value) -> None:
        self._x("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)))

    def update_settings(self, changes: dict) -> dict:
        """Only the public settings in DEFAULT_SETTINGS, with type checks."""
        for key, value in changes.items():
            if key not in DEFAULT_SETTINGS:
                raise StoreError(f"unknown setting {key!r}")
            default = DEFAULT_SETTINGS[key]
            if isinstance(default, bool):
                if not isinstance(value, bool):
                    raise StoreError(f"{key} must be true or false")
            elif isinstance(default, int):
                if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 3650:
                    raise StoreError(f"{key} must be a whole number from 0 to 3650")
        if "lead_seconds" in changes and not 5 <= changes["lead_seconds"] <= 300:
            raise StoreError("lead_seconds must be between 5 and 300")
        for key, value in changes.items():
            self.set(key, value)
        return self.settings()

    # --- schedules ---------------------------------------------------------

    def schedules(self) -> list[Schedule]:
        out = []
        for row in self._q("SELECT id, data FROM schedules ORDER BY id"):
            data = json.loads(row["data"])
            data["id"] = row["id"]
            try:
                out.append(Schedule.from_dict(data))
            except ScheduleError:
                continue  # a broken row must not stop the station
        return out

    def schedule(self, schedule_id: int) -> Schedule | None:
        return next((s for s in self.schedules() if s.id == schedule_id), None)

    def save_schedule(self, schedule: Schedule) -> Schedule:
        schedule.validate()
        data = schedule.to_dict()
        data.pop("id")
        if schedule.id is None:
            schedule.id = self._x("INSERT INTO schedules (data) VALUES (?)", (json.dumps(data),))
        elif not self._x("UPDATE schedules SET data = ? WHERE id = ?", (json.dumps(data), schedule.id)):
            raise StoreError(f"schedule {schedule.id} does not exist")
        self.version += 1
        return schedule

    def delete_schedule(self, schedule_id: int) -> bool:
        with self._lock:
            # Messages bound to this schedule fall back to "any schedule".
            self._x("UPDATE messages SET schedule_id = NULL WHERE schedule_id = ?", (schedule_id,))
            done = bool(self._x("DELETE FROM schedules WHERE id = ?", (schedule_id,)))
        self.version += 1
        return done

    # --- messages ----------------------------------------------------------

    def add_message(self, groups: list[str] | str, *, label: str = "", priority: int = 0,
                    schedule_id: int | None = None, not_before: str | None = None, expires: str | None = None,
                    transmissions: int = 1, burn: bool = True, source: str = "ui") -> Message:
        if isinstance(groups, str):
            try:
                groups = parse_groups(groups)
            except GroupError as exc:
                raise StoreError(str(exc)) from exc
        if not groups:
            raise StoreError("the message is empty")
        if any(len(g) != 5 or not (g.isdigit() and g.isascii()) for g in groups):
            raise StoreError("every group must have five digits")
        if len(groups) > 500:
            raise StoreError("at most 500 groups per message")
        if priority not in PRIORITIES:
            raise StoreError("priority must be 0 (normal), 1 (high) or 2 (urgent)")
        if not isinstance(transmissions, int) or not 1 <= transmissions <= 100:
            raise StoreError("transmissions must be between 1 and 100")
        if schedule_id is not None and self.schedule(schedule_id) is None:
            raise StoreError(f"schedule {schedule_id} does not exist")
        try:
            nb, ex = parse_iso(not_before), parse_iso(expires)
        except ScheduleError as exc:
            raise StoreError(str(exc)) from exc
        if nb and ex and ex <= nb:
            raise StoreError("the message would expire before it may be sent")
        mid = self._x(
            "INSERT INTO messages (created, groups, group_count, label, priority, schedule_id, not_before, expires,"
            " transmissions, burn, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (iso(utcnow()), " ".join(groups), len(groups), (label or "")[:80], priority, schedule_id,
             iso(nb), iso(ex), transmissions, int(bool(burn)), source[:60]),
        )
        return self.message(mid)

    def message(self, message_id: int) -> Message | None:
        rows = self._q("SELECT * FROM messages WHERE id = ?", (message_id,))
        return _message(rows[0]) if rows else None

    def messages(self, status: str | None = None, limit: int = 200) -> list[Message]:
        if status:
            rows = self._q("SELECT * FROM messages WHERE status = ? ORDER BY priority DESC, created, id LIMIT ?",
                           (status, limit))
        else:
            rows = self._q("SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,))
        return [_message(r) for r in rows]

    def expire(self, now: str) -> int:
        """Mark messages past their expiry; burned ones lose their groups."""
        with self._lock:
            n = self._x("UPDATE messages SET status = 'expired' WHERE status = 'queued' AND expires IS NOT NULL"
                        " AND expires <= ?", (now,))
            self._x("UPDATE messages SET groups = NULL WHERE status = 'expired' AND burn = 1")
        return n

    def due(self, schedule_id: int, now: str, limit: int) -> list[Message]:
        """Messages a transmission of this schedule should carry, most important first."""
        self.expire(now)
        rows = self._q(
            "SELECT * FROM messages WHERE status = 'queued' AND groups IS NOT NULL"
            " AND (schedule_id IS NULL OR schedule_id = ?) AND (not_before IS NULL OR not_before <= ?)"
            " ORDER BY priority DESC, created, id LIMIT ?",
            (schedule_id, now, limit),
        )
        return [_message(r) for r in rows]

    def mark_sent(self, message_ids: list[int], when: str) -> None:
        with self._lock:
            for mid in message_ids:
                self._x("UPDATE messages SET sent_count = sent_count + 1, last_sent = ? WHERE id = ?", (when, mid))
                self._x("UPDATE messages SET status = 'done' WHERE id = ? AND sent_count >= transmissions", (mid,))
            self._x("UPDATE messages SET groups = NULL WHERE status = 'done' AND burn = 1")

    def cancel_message(self, message_id: int) -> bool:
        with self._lock:
            done = bool(self._x("UPDATE messages SET status = 'cancelled' WHERE id = ? AND status = 'queued'",
                                (message_id,)))
            self._x("UPDATE messages SET groups = NULL WHERE id = ? AND status = 'cancelled' AND burn = 1",
                    (message_id,))
        return done

    def delete_message(self, message_id: int) -> bool:
        return bool(self._x("DELETE FROM messages WHERE id = ? AND status != 'queued'", (message_id,)))

    def queue_size(self) -> int:
        return self._q("SELECT COUNT(*) AS n FROM messages WHERE status = 'queued'")[0]["n"]

    # --- log ---------------------------------------------------------------

    def add_log(self, **entry) -> int:
        cols = ["started", "duration", "schedule_id", "schedule_name", "kind", "message_ids", "transcript",
                "status", "error", "recording"]
        values = [entry.get(c, "" if c not in ("duration", "schedule_id") else None) for c in cols]
        values[1] = values[1] or 0
        return self._x(f"INSERT INTO log ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", tuple(values))

    def log(self, limit: int = 100) -> list[dict]:
        return [dict(r) for r in self._q("SELECT * FROM log ORDER BY started DESC, id DESC LIMIT ?", (limit,))]

    def log_entry(self, entry_id: int) -> dict | None:
        rows = self._q("SELECT * FROM log WHERE id = ?", (entry_id,))
        return dict(rows[0]) if rows else None

    def forget_recordings_before(self, cutoff: str) -> list[str]:
        with self._lock:
            rows = self._q("SELECT recording FROM log WHERE recording != '' AND started < ?", (cutoff,))
            self._x("UPDATE log SET recording = '' WHERE recording != '' AND started < ?", (cutoff,))
        return [r["recording"] for r in rows]

    # --- API tokens ----------------------------------------------------------

    def add_token(self, name: str) -> tuple[int, str]:
        """A new submit token. The token itself is returned once and stored only as a hash."""
        name = (name or "").strip()[:40]
        if not name:
            raise StoreError("the token needs a name")
        token = "ed_" + secrets.token_urlsafe(24)
        tid = self._x("INSERT INTO tokens (name, hash, created) VALUES (?, ?, ?)", (name, token_hash(token), iso(utcnow())))
        return tid, token

    def tokens(self) -> list[dict]:
        return [dict(r) for r in self._q("SELECT id, name, created, last_used FROM tokens ORDER BY id")]

    def check_token(self, token: str) -> dict | None:
        rows = self._q("SELECT id, name FROM tokens WHERE hash = ?", (token_hash(token),))
        if not rows:
            return None
        self._x("UPDATE tokens SET last_used = ? WHERE id = ?", (iso(utcnow()), rows[0]["id"]))
        return dict(rows[0])

    def revoke_token(self, token_id: int) -> bool:
        return bool(self._x("DELETE FROM tokens WHERE id = ?", (token_id,)))
