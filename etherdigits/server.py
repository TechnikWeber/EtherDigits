"""Web interface and HTTP API.

Access rules:
- No admin password set: only this computer may use the interface
  (requests from 127.0.0.1 / ::1 without proxy headers).
- Password set: everybody must log in; the session lives in a cookie.
- /api/submit takes an API token instead ("Authorization: Bearer ed_..."),
  and that token can do nothing else: submitters hand in messages, they
  cannot read the queue, the log or the settings.
Requests that change something must carry the header "X-EtherDigits: 1",
which a foreign web page cannot set (cross-site request protection).
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import io
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from aiohttp import web

from . import __version__, otp
from .auth import (Sessions, Throttle, check_new_password, hash_password, new_totp_secret, totp_uri, verify_password,
                   verify_totp)
from .groups import GroupError
from .radio import RIG_MODES, RadioError, Rig, gpio_chips, list_devices, serial_ports, validate_output
from .groups import random_groups
from .render import EFFECTS, MELODIES, render, write_wav
from .schedule import FILLERS, Schedule, ScheduleError, iso, parse_iso
from .script import INTERVALS, Format, Transmission, build_script
from .station import Station
from .store import PRIORITIES, Store, StoreError
from .voicepack import VoicePackError, find_pack, list_packs

log = logging.getLogger("etherdigits.server")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
COOKIE = "ed_session"
PUBLIC = {"/api/session", "/api/login", "/api/health"}
PAD_NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
STATION = web.AppKey("station", Station)
STORE = web.AppKey("store", Store)
SESSIONS = web.AppKey("sessions", Sessions)
THROTTLE = web.AppKey("throttle", Throttle)
DATA = web.AppKey("data", Path)


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def is_local(request: web.Request) -> bool:
    if any(h in request.headers for h in ("X-Forwarded-For", "Forwarded", "X-Real-IP")):
        return False  # behind a proxy everybody looks local; do not trust that
    try:
        return ipaddress.ip_address(request.remote or "").is_loopback
    except ValueError:
        return False


def password_set(request: web.Request) -> bool:
    return bool(request.app[STORE].get("admin_password"))


def logged_in(request: web.Request) -> bool:
    if not password_set(request):
        return is_local(request)
    return request.app[SESSIONS].valid(request.cookies.get(COOKIE))


@web.middleware
async def errors(request: web.Request, handler):
    try:
        return await handler(request)
    except ApiError as exc:
        return web.json_response({"error": str(exc)}, status=exc.status)
    except (StoreError, ScheduleError, GroupError, otp.OtpError, VoicePackError, RadioError) as exc:
        return web.json_response({"error": str(exc)}, status=400)


@web.middleware
async def access(request: web.Request, handler):
    path = request.path
    if not path.startswith("/api/") or path in PUBLIC:
        return await handler(request)
    if path == "/api/submit":
        auth = request.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        info = request.app[STORE].check_token(token) if token else None
        if not info:
            raise ApiError(401, "a valid API token is needed")
        request["token"] = info
        return await handler(request)
    if not logged_in(request):
        raise ApiError(401, "login required")
    if request.method not in ("GET", "HEAD") and request.headers.get("X-EtherDigits") != "1":
        raise ApiError(403, "missing X-EtherDigits header")
    return await handler(request)


@web.middleware
async def security_headers(request: web.Request, handler):
    response = await handler(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:; img-src 'self' data:; "
        "frame-ancestors 'none'")
    if request.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


async def body(request: web.Request) -> dict:
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(400, "the request body must be JSON")
    if not isinstance(data, dict):
        raise ApiError(400, "the request body must be a JSON object")
    return data


def int_arg(request: web.Request, name: str = "id") -> int:
    try:
        return int(request.match_info[name])
    except (KeyError, ValueError):
        raise ApiError(404, "not found")


# --- session -------------------------------------------------------------------

async def get_session(request: web.Request) -> web.Response:
    return web.json_response({"logged_in": logged_in(request), "password_set": password_set(request),
                              "totp": bool(request.app[STORE].get("totp_secret")),
                              "local": is_local(request), "version": __version__})


async def get_health(request: web.Request) -> web.Response:
    """For monitoring tools: 200 when the scheduler runs and the clock is fine, otherwise 503.
    Says nothing about traffic."""
    station = request.app[STATION]
    tick = station.last_tick
    loop_ok = tick is not None and (station.clock() - tick).total_seconds() < 10
    offset = station.clock_status.get("offset")
    clock_ok = offset is None or abs(offset) <= 2
    ok = loop_ok and clock_ok
    return web.json_response({"ok": ok, "scheduler": loop_ok, "clock": clock_ok, "version": __version__},
                             status=200 if ok else 503)


async def post_login(request: web.Request) -> web.Response:
    who = request.remote or "?"
    throttle = request.app[THROTTLE]
    if throttle.blocked(who):
        raise ApiError(429, "too many wrong passwords; wait a minute")
    data = await body(request)
    stored = request.app[STORE].get("admin_password")
    if not stored:
        raise ApiError(400, "no password is set")
    ok = await asyncio.to_thread(verify_password, str(data.get("password", "")), stored)
    if not ok:
        throttle.fail(who)
        raise ApiError(401, "wrong password")
    store = request.app[STORE]
    secret = store.get("totp_secret")
    if secret:
        if not data.get("code"):
            raise ApiError(401, "code required")
        counter = verify_totp(secret, str(data["code"]), last_counter=int(store.get("totp_last") or -1))
        if counter is None:
            throttle.fail(who)
            raise ApiError(401, "wrong code")
        store.set("totp_last", counter)
    throttle.reset(who)
    response = web.json_response({"ok": True})
    response.set_cookie(COOKIE, request.app[SESSIONS].create(), httponly=True, samesite="Strict",
                        secure=request.secure, max_age=12 * 3600)
    return response


async def post_logout(request: web.Request) -> web.Response:
    request.app[SESSIONS].drop(request.cookies.get(COOKIE))
    response = web.json_response({"ok": True})
    response.del_cookie(COOKIE)
    return response


async def post_password(request: web.Request) -> web.Response:
    data = await body(request)
    store = request.app[STORE]
    current = store.get("admin_password")
    if current and not await asyncio.to_thread(verify_password, str(data.get("current", "")), current):
        raise ApiError(401, "the current password is wrong")
    new = data.get("new", "")
    problem = check_new_password(new)
    if problem:
        raise ApiError(400, problem)
    store.set("admin_password", await asyncio.to_thread(hash_password, new))
    sessions = request.app[SESSIONS]
    sessions.drop_all()
    response = web.json_response({"ok": True})
    response.set_cookie(COOKIE, sessions.create(), httponly=True, samesite="Strict", secure=request.secure,
                        max_age=12 * 3600)
    return response


async def post_totp_setup(request: web.Request) -> web.Response:
    store = request.app[STORE]
    stored = store.get("admin_password")
    if not stored:
        raise ApiError(400, "set a password first")
    data = await body(request)
    if not await asyncio.to_thread(verify_password, str(data.get("password", "")), stored):
        raise ApiError(401, "the current password is wrong")
    secret = new_totp_secret()
    store.set("totp_pending", secret)
    return web.json_response({"secret": secret, "uri": totp_uri(secret)})


async def post_totp_enable(request: web.Request) -> web.Response:
    store = request.app[STORE]
    pending = store.get("totp_pending")
    if not pending:
        raise ApiError(400, "start the setup first")
    counter = verify_totp(pending, str((await body(request)).get("code", "")))
    if counter is None:
        raise ApiError(400, "wrong code")
    store.set("totp_secret", pending)
    store.set("totp_last", counter)
    store.set("totp_pending", "")
    return web.json_response({"ok": True})


async def post_totp_disable(request: web.Request) -> web.Response:
    store = request.app[STORE]
    data = await body(request)
    secret = store.get("totp_secret")
    if not secret:
        return web.json_response({"ok": True})
    if not await asyncio.to_thread(verify_password, str(data.get("password", "")), store.get("admin_password")):
        raise ApiError(401, "the current password is wrong")
    if verify_totp(secret, str(data.get("code", "")), last_counter=int(store.get("totp_last") or -1)) is None:
        raise ApiError(400, "wrong code")
    store.set("totp_secret", "")
    return web.json_response({"ok": True})


# --- station -------------------------------------------------------------------

async def get_status(request: web.Request) -> web.Response:
    return web.json_response(request.app[STATION].status())


async def get_voices(request: web.Request) -> web.Response:
    packs = [{"id": p.id, "name": p.name, "language": p.language, "license": p.license} for p in list_packs()]
    return web.json_response({"voices": packs, "effects": list(EFFECTS), "intervals": list(INTERVALS),
                              "melodies": list(MELODIES), "fillers": list(FILLERS), "rig_modes": list(RIG_MODES),
                              "format_defaults": Format().__dict__})


def schedule_json(schedule: Schedule, station: Station) -> dict:
    data = schedule.to_dict()
    data["upcoming"] = [iso(t) for t in schedule.upcoming(station.clock(), 3)]
    return data


async def get_schedules(request: web.Request) -> web.Response:
    station = request.app[STATION]
    return web.json_response([schedule_json(s, station) for s in request.app[STORE].schedules()])


def schedule_from(data: dict, schedule_id: int | None) -> Schedule:
    data = dict(data)
    data.pop("upcoming", None)
    data["id"] = schedule_id
    schedule = Schedule.from_dict(data)
    find_pack(schedule.voice)  # raises VoicePackError, answered with 400
    return schedule


async def post_schedule(request: web.Request) -> web.Response:
    schedule = request.app[STORE].save_schedule(schedule_from(await body(request), None))
    return web.json_response(schedule_json(schedule, request.app[STATION]), status=201)


async def put_schedule(request: web.Request) -> web.Response:
    sid = int_arg(request)
    if request.app[STORE].schedule(sid) is None:
        raise ApiError(404, "schedule not found")
    schedule = request.app[STORE].save_schedule(schedule_from(await body(request), sid))
    return web.json_response(schedule_json(schedule, request.app[STATION]))


async def delete_schedule(request: web.Request) -> web.Response:
    if not request.app[STORE].delete_schedule(int_arg(request)):
        raise ApiError(404, "schedule not found")
    return web.json_response({"ok": True})


def existing_schedule(request: web.Request) -> Schedule:
    schedule = request.app[STORE].schedule(int_arg(request))
    if schedule is None:
        raise ApiError(404, "schedule not found")
    return schedule


async def post_preview(request: web.Request) -> web.Response:
    """Render what this schedule would send now, without sending or consuming anything."""
    station = request.app[STATION]
    data = await body(request) if request.can_read_body else {}
    schedule = schedule_from(data["schedule"], None) if data.get("schedule") else existing_schedule(request)
    if schedule.id is None:
        schedule.id = -1
    planned = station.plan(schedule, test=bool(data.get("test")))
    if planned is None:
        raise ApiError(400, "this schedule sends nothing when the queue is empty")
    audio = await asyncio.to_thread(station.render, planned)

    def to_wav() -> bytes:
        buf = io.BytesIO()
        write_wav(buf, audio, station.rate)
        return buf.getvalue()

    # Long filler transcripts are cut before encoding, so the header always decodes.
    return web.Response(body=await asyncio.to_thread(to_wav), content_type="audio/wav",
                        headers={"X-Transcript": quote(planned.text()[:3000]), "X-Kind": planned.kind})


async def post_practice(request: web.Request) -> web.Response:
    """Random groups to copy by ear, for receivers in training. Nothing is sent or logged."""
    data = await body(request)
    try:
        count = int(data.get("groups", 5))
        pause = float(data.get("group_gap", 1.5))
    except (TypeError, ValueError):
        raise ApiError(400, "groups and group_gap must be numbers")
    if not 1 <= count <= 50 or not 0.3 <= pause <= 10:
        raise ApiError(400, "1 to 50 groups, pauses of 0.3 to 10 s")
    effect = str(data.get("effect", "none"))
    if effect not in EFFECTS:
        raise ApiError(400, "unknown effect")
    pack = find_pack(str(data.get("voice", "de")))
    groups = random_groups(count)
    fmt = Format(interval="none", callsign_repeats=0, announce_group_count=False, message_repeats=1,
                 end_tone=False, group_gap=pause, group_twice=bool(data.get("group_twice")))
    steps = build_script(Transmission([groups], fmt))
    station = request.app[STATION]
    audio = await asyncio.to_thread(render, steps, pack, station.rate, effect)

    def to_wav() -> bytes:
        buf = io.BytesIO()
        write_wav(buf, audio, station.rate)
        return buf.getvalue()

    return web.Response(body=await asyncio.to_thread(to_wav), content_type="audio/wav",
                        headers={"X-Groups": " ".join(groups)})


async def post_transmit(request: web.Request) -> web.Response:
    schedule = existing_schedule(request)
    data = await body(request) if request.can_read_body else {}
    station = request.app[STATION]
    if station.current:
        raise ApiError(409, "a transmission is on air")
    station.spawn(station.transmit(schedule, test=bool(data.get("test"))))
    return web.json_response({"ok": True}, status=202)


# --- messages ------------------------------------------------------------------

def message_args(data: dict, store: Store, data_dir: Path, source: str, now: datetime) -> dict:
    groups = data.get("groups")
    text = data.get("text")
    if text:
        if not store.get("station_encryption"):
            raise ApiError(403, "encrypting on the station is switched off in the settings")
        groups = encrypt_on_station(str(text), str(data.get("pad", "")), data_dir)
    if not groups:
        raise ApiError(400, "groups (or text and pad) are needed")
    expires = data.get("expires")
    if data.get("expires_minutes"):
        try:
            minutes = int(data["expires_minutes"])
        except (TypeError, ValueError):
            raise ApiError(400, "expires_minutes must be a whole number")
        if not 1 <= minutes <= 60 * 24 * 365:
            raise ApiError(400, "expires_minutes must be between 1 and 525600")
        expires = iso(now + timedelta(minutes=minutes))
    def as_int(name: str, default):
        value = data.get(name, default)
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            raise ApiError(400, f"{name} must be a whole number")
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ApiError(400, f"{name} must be a whole number")
    return dict(groups=groups, label=str(data.get("label", ""))[:80], priority=as_int("priority", 0),
                schedule_id=as_int("schedule_id", None), not_before=data.get("not_before") or None,
                expires=expires or None, transmissions=as_int("transmissions", 1),
                burn=bool(data.get("burn", True)), source=source)


def pad_path(data_dir: Path, name: str) -> Path:
    if not PAD_NAME.match(name or ""):
        raise ApiError(400, "pad names may use letters, digits, - and _ (at most 40)")
    return data_dir / "pads" / f"{name}.json"


_pad_lock = asyncio.Lock()


def encrypt_on_station(text: str, name: str, data_dir: Path) -> list[str]:
    path = pad_path(data_dir, name)
    if not path.is_file():
        raise ApiError(400, f"pad {name!r} is not on the station")
    pad = otp.load_pad(path)
    groups = otp.encrypt(text, pad)
    otp.save_pad(pad, path)  # the used page is recorded before the plain text is forgotten
    return groups


async def get_messages(request: web.Request) -> web.Response:
    status = request.query.get("status") or None
    return web.json_response([m.to_dict() for m in request.app[STORE].messages(status)])


async def post_message(request: web.Request) -> web.Response:
    data = await body(request)
    async with _pad_lock:
        args = message_args(data, request.app[STORE], request.app[DATA], "ui", request.app[STATION].clock())
    message = request.app[STORE].add_message(**args)
    return web.json_response(message.to_dict(), status=201)


async def post_cancel(request: web.Request) -> web.Response:
    if not request.app[STORE].cancel_message(int_arg(request)):
        raise ApiError(404, "no queued message with this id")
    return web.json_response({"ok": True})


async def delete_message(request: web.Request) -> web.Response:
    if not request.app[STORE].delete_message(int_arg(request)):
        raise ApiError(400, "only messages that are no longer queued can be deleted; cancel it first")
    return web.json_response({"ok": True})


async def post_submit(request: web.Request) -> web.Response:
    """Remote submission with an API token. The answer reveals nothing about the queue."""
    data = await body(request)
    token = request["token"]
    async with _pad_lock:
        args = message_args(data, request.app[STORE], request.app[DATA], f"api:{token['name']}",
                            request.app[STATION].clock())
    message = request.app[STORE].add_message(**args)
    return web.json_response({"id": message.id, "groups": message.group_count}, status=201)


# --- log -------------------------------------------------------------------------

async def get_log(request: web.Request) -> web.Response:
    try:
        limit = max(1, min(500, int(request.query.get("limit", 100))))
    except ValueError:
        limit = 100
    return web.json_response(request.app[STORE].log(limit))


async def get_recording(request: web.Request) -> web.StreamResponse:
    entry = request.app[STORE].log_entry(int_arg(request))
    if not entry or not entry["recording"]:
        raise ApiError(404, "no recording")
    base = (request.app[DATA] / "recordings").resolve()
    path = (base / entry["recording"]).resolve()
    if base not in path.parents or not path.is_file():
        raise ApiError(404, "no recording")
    return web.FileResponse(path, headers={"Content-Type": "audio/wav"})


# --- settings, tokens, pads ----------------------------------------------------

async def get_settings(request: web.Request) -> web.Response:
    return web.json_response(request.app[STORE].settings())


async def put_settings(request: web.Request) -> web.Response:
    return web.json_response(request.app[STORE].update_settings(await body(request)))


async def get_tokens(request: web.Request) -> web.Response:
    return web.json_response(request.app[STORE].tokens())


async def post_token(request: web.Request) -> web.Response:
    tid, token = request.app[STORE].add_token(str((await body(request)).get("name", "")))
    return web.json_response({"id": tid, "token": token}, status=201)


async def delete_token(request: web.Request) -> web.Response:
    if not request.app[STORE].revoke_token(int_arg(request)):
        raise ApiError(404, "token not found")
    return web.json_response({"ok": True})


def pad_summary(name: str, pad: otp.Pad) -> dict:
    return {"name": name, "label": pad.name, "language": pad.language, "pages": len(pad.pages),
            "unused": len(pad.unused()), "created": pad.created}


async def get_pads(request: web.Request) -> web.Response:
    out = []
    for path in sorted((request.app[DATA] / "pads").glob("*.json")):
        try:
            out.append(pad_summary(path.stem, otp.load_pad(path)))
        except otp.OtpError:
            out.append({"name": path.stem, "error": "unreadable"})
    return web.json_response(out)


async def post_pad(request: web.Request) -> web.Response:
    data = await body(request)
    path = pad_path(request.app[DATA], str(data.get("name", "")))
    if path.exists():
        raise ApiError(409, "a pad with this name is already on the station")
    pad = otp.Pad.from_json(data.get("pad") or {})
    otp.save_pad(pad, path)
    return web.json_response(pad_summary(path.stem, pad), status=201)


async def delete_pad(request: web.Request) -> web.Response:
    path = pad_path(request.app[DATA], request.match_info["name"])
    if not path.is_file():
        raise ApiError(404, "pad not found")
    path.unlink()
    return web.json_response({"ok": True})


# --- radio output ------------------------------------------------------------------

def output_config(store: Store) -> dict:
    return validate_output({}, store.get("output") or {})


def public_output(cfg: dict) -> dict:
    """The output settings for the browser: the stream password never leaves the station."""
    out = dict(cfg)
    out["stream_password_set"] = bool(out.pop("stream_password"))
    return out


async def get_output(request: web.Request) -> web.Response:
    return web.json_response(public_output(output_config(request.app[STORE])))


async def put_output(request: web.Request) -> web.Response:
    store = request.app[STORE]
    changes = await body(request)
    changes.pop("stream_password_set", None)
    if not changes.get("stream_password"):
        changes.pop("stream_password", None)  # empty field: keep the stored password
    cfg = validate_output(changes, output_config(store))
    store.set("output", cfg)
    await asyncio.to_thread(request.app[STATION].reconfigure)
    return web.json_response(public_output(cfg))


async def get_devices(_request: web.Request) -> web.Response:
    try:
        devices, error = await asyncio.to_thread(list_devices), ""
    except RadioError as exc:
        devices, error = [], str(exc)
    return web.json_response({"devices": devices, "error": error,
                              "serial_ports": await asyncio.to_thread(serial_ports),
                              "gpio_chips": await asyncio.to_thread(gpio_chips)})


async def post_output_test(request: web.Request) -> web.Response:
    data = await body(request)
    station = request.app[STATION]
    if data.get("what") == "cat":
        cfg = output_config(request.app[STORE])
        hz = await asyncio.to_thread(Rig(cfg["rig_host"], cfg["rig_port"]).frequency)
        return web.json_response({"frequency_hz": hz})
    if station.current:
        raise ApiError(409, "a transmission is on air")
    if request.app[STORE].get("tx_blocked"):
        raise ApiError(409, "the transmitter is locked (emergency stop)")
    try:
        seconds = min(30.0, max(0.5, float(data.get("seconds", 3))))
    except (TypeError, ValueError):
        raise ApiError(400, "seconds must be a number")
    station.spawn(station.test_tone(seconds))
    return web.json_response({"ok": True}, status=202)


async def post_stop(request: web.Request) -> web.Response:
    request.app[STATION].emergency_stop()
    return web.json_response({"ok": True, "blocked": True})


async def post_release(request: web.Request) -> web.Response:
    request.app[STORE].set("tx_blocked", False)
    return web.json_response({"ok": True, "blocked": False})


async def get_meter(request: web.Request) -> web.StreamResponse:
    """Server-sent events: the level ten times a second while on air, once a second otherwise."""
    response = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-store",
                                           "X-Accel-Buffering": "no"})
    await response.prepare(request)
    meter = request.app[STATION].meter
    try:
        while True:
            snap = meter.snapshot()
            await response.write(f"data: {json.dumps(snap)}\n\n".encode())
            await asyncio.sleep(0.1 if snap["on_air"] else 1.0)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    return response


# --- app ---------------------------------------------------------------------------

async def index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB_DIR / "index.html")


async def pad_tool(_request: web.Request) -> web.FileResponse:
    """The offline pad tool as a download, to open on a computer without network. It holds no keys."""
    return web.FileResponse(WEB_DIR.parent / "pad_tool.html",
                            headers={"Content-Disposition": 'attachment; filename="pad_tool.html"'})


def make_app(store: Store, station: Station, data_dir: Path, run_station: bool = True) -> web.Application:
    app = web.Application(middlewares=[security_headers, errors, access], client_max_size=2 * 1024 * 1024)
    app[STORE], app[STATION], app[DATA] = store, station, Path(data_dir)
    app[SESSIONS], app[THROTTLE] = Sessions(), Throttle()
    r = app.router
    r.add_get("/", index)
    r.add_get("/pad_tool.html", pad_tool)
    r.add_static("/static/", WEB_DIR, show_index=False)
    r.add_get("/api/session", get_session)
    r.add_post("/api/login", post_login)
    r.add_post("/api/logout", post_logout)
    r.add_post("/api/password", post_password)
    r.add_get("/api/health", get_health)
    r.add_post("/api/totp/setup", post_totp_setup)
    r.add_post("/api/totp/enable", post_totp_enable)
    r.add_post("/api/totp/disable", post_totp_disable)
    r.add_get("/api/status", get_status)
    r.add_get("/api/voices", get_voices)
    r.add_get("/api/schedules", get_schedules)
    r.add_post("/api/schedules", post_schedule)
    r.add_post("/api/preview", post_preview)
    r.add_put("/api/schedules/{id}", put_schedule)
    r.add_delete("/api/schedules/{id}", delete_schedule)
    r.add_post("/api/schedules/{id}/preview", post_preview)
    r.add_post("/api/schedules/{id}/transmit", post_transmit)
    r.add_post("/api/practice", post_practice)
    r.add_get("/api/messages", get_messages)
    r.add_post("/api/messages", post_message)
    r.add_post("/api/messages/{id}/cancel", post_cancel)
    r.add_delete("/api/messages/{id}", delete_message)
    r.add_post("/api/submit", post_submit)
    r.add_get("/api/log", get_log)
    r.add_get("/api/log/{id}/recording", get_recording)
    r.add_get("/api/settings", get_settings)
    r.add_put("/api/settings", put_settings)
    r.add_get("/api/tokens", get_tokens)
    r.add_post("/api/tokens", post_token)
    r.add_delete("/api/tokens/{id}", delete_token)
    r.add_get("/api/pads", get_pads)
    r.add_post("/api/pads", post_pad)
    r.add_delete("/api/pads/{name}", delete_pad)
    r.add_get("/api/output", get_output)
    r.add_put("/api/output", put_output)
    r.add_get("/api/output/devices", get_devices)
    r.add_post("/api/output/test", post_output_test)
    r.add_post("/api/stop", post_stop)
    r.add_post("/api/release", post_release)
    r.add_get("/api/meter", get_meter)

    if run_station:
        async def start(app: web.Application) -> None:
            app["station_task"] = asyncio.create_task(station.run())

        async def stop(app: web.Application) -> None:
            await station.stop()
            app["station_task"].cancel()
            await asyncio.gather(app["station_task"], return_exceptions=True)

        app.on_startup.append(start)
        app.on_cleanup.append(stop)
    return app


def first_run(store: Store) -> None:
    """A switched-off example schedule, so the interface is not empty."""
    if not store.schedules():
        store.save_schedule(Schedule(name="Station 472", enabled=False, times=["18:00", "20:00"]))


def is_loopback_host(host: str) -> bool:
    if host in ("localhost",):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
