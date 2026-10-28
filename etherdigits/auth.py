"""Admin password, login sessions and a brake against password guessing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

SESSION_HOURS = 12
MIN_PASSWORD = 10


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 15, r=8, p=1, maxmem=64 * 1024 * 1024)
    return "scrypt$15$8$1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, log_n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=2 ** int(log_n), r=int(r),
                                p=int(p), maxmem=64 * 1024 * 1024, dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def check_new_password(password: str) -> str | None:
    """An error text, or None when the password is acceptable."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        return f"the password needs at least {MIN_PASSWORD} characters"
    if len(password) > 200:
        return "the password may have at most 200 characters"
    if len(set(password)) < 4:
        return "the password is too simple"
    return None


class Sessions:
    """Login sessions in memory; a restart logs everybody out, which is fine for one admin."""

    def __init__(self, clock=time.monotonic):
        self._sessions: dict[str, float] = {}
        self._clock = clock

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = self._clock() + SESSION_HOURS * 3600
        return token

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        expiry = self._sessions.get(token)
        if expiry is None:
            return False
        if expiry < self._clock():
            del self._sessions[token]
            return False
        return True

    def drop(self, token: str | None) -> None:
        self._sessions.pop(token or "", None)

    def drop_all(self) -> None:
        self._sessions.clear()


class Throttle:
    """After 5 wrong passwords from one address, that address waits a minute."""

    def __init__(self, limit: int = 5, seconds: float = 60, clock=time.monotonic):
        self.limit, self.seconds, self._clock = limit, seconds, clock
        self._fails: dict[str, list[float]] = {}

    def blocked(self, who: str) -> bool:
        now = self._clock()
        fails = [t for t in self._fails.get(who, []) if now - t < self.seconds]
        self._fails[who] = fails
        return len(fails) >= self.limit

    def fail(self, who: str) -> None:
        self._fails.setdefault(who, []).append(self._clock())

    def reset(self, who: str) -> None:
        self._fails.pop(who, None)


# --- TOTP (RFC 6238), the six-digit codes of authenticator apps -------------------

TOTP_STEP = 30


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp(secret: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF
    return str(value % 10 ** digits).zfill(digits)


def verify_totp(secret: str, code: str, now: float | None = None, last_counter: int = -1) -> int | None:
    """The matching time step (one step of clock drift allowed), or None.

    Steps at or before `last_counter` are refused, so a code cannot be used twice.
    """
    code = "".join(c for c in str(code) if c.isdigit())
    if len(code) != 6:
        return None
    current = int((time.time() if now is None else now) // TOTP_STEP)
    for counter in (current - 1, current, current + 1):
        if counter > last_counter and hmac.compare_digest(totp(secret, counter), code):
            return counter
    return None


def totp_uri(secret: str, account: str = "admin", issuer: str = "EtherDigits") -> str:
    from urllib.parse import quote
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"
