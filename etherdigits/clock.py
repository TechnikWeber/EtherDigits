"""Is the station's clock right? A minimal SNTP client (RFC 4330).

Receivers tune in at the announced minute, so the station must be on time.
The station asks a time server once an hour, warns when the system clock is
off by more than two seconds, and schedules by the corrected time.
"""

from __future__ import annotations

import socket
import struct
import time

NTP_EPOCH = 2208988800  # seconds from 1900 to 1970
WARN_SECONDS = 2.0


class ClockError(Exception):
    pass


def _ts(data: bytes) -> float:
    seconds, fraction = struct.unpack("!II", data)
    return seconds - NTP_EPOCH + fraction / 2 ** 32


def sntp_offset(server: str = "pool.ntp.org", port: int = 123, timeout: float = 3.0) -> float:
    """How far the local clock is behind the server (positive: local clock is slow)."""
    request = b"\x23" + 47 * b"\0"  # version 4, mode 3 (client)
    try:
        infos = socket.getaddrinfo(server, port, type=socket.SOCK_DGRAM)
    except OSError as exc:
        raise ClockError(f"time server {server!r} not found ({exc})") from exc
    family, _, _, _, address = infos[0]
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        t0 = time.time()
        try:
            sock.sendto(request, address)
            data, _ = sock.recvfrom(512)
        except OSError as exc:
            raise ClockError(f"no answer from time server {server!r} ({exc})") from exc
        t3 = time.time()
    if len(data) < 48:
        raise ClockError("short answer from the time server")
    mode, stratum = data[0] & 0x7, data[1]
    if mode != 4 or not 1 <= stratum <= 15:
        raise ClockError("the time server gave no usable time")
    t1, t2 = _ts(data[32:40]), _ts(data[40:48])
    return ((t1 - t0) + (t2 - t3)) / 2
