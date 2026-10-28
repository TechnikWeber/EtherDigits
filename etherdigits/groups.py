"""Digit groups: parse what people type, make random test groups."""

from __future__ import annotations

import re
import secrets

DEFAULT_GROUP_SIZE = 5

# Spaces, dashes, dots, slashes and line breaks may separate groups.
_SEPARATORS = re.compile(r"[\s\-./,;]+")


class GroupError(ValueError):
    """The input is not a valid list of digit groups."""


def parse_groups(text: str, group_size: int = DEFAULT_GROUP_SIZE, pad: str | None = None) -> list[str]:
    """Turn "12345 67890" (or "1234567890") into ["12345", "67890"].

    The station sends exactly what it gets, so a short last group is an
    error unless `pad` is given: "random" fills it with random digits,
    "zero" with zeros. With a one-time pad the receiver simply decodes the
    padding to noise at the end.
    """
    if group_size < 1:
        raise GroupError("group size must be at least 1")
    digits = _SEPARATORS.sub("", text or "")
    if not digits:
        raise GroupError("the message is empty")
    bad = sorted({c for c in digits if not c.isdigit() or not c.isascii()})
    if bad:
        raise GroupError("only digits are allowed, found: " + " ".join(repr(c) for c in bad))
    rest = len(digits) % group_size
    if rest:
        missing = group_size - rest
        if pad == "random":
            digits += "".join(secrets.choice("0123456789") for _ in range(missing))
        elif pad == "zero":
            digits += "0" * missing
        else:
            raise GroupError(
                f"{len(digits)} digits do not fill groups of {group_size}; "
                f"{missing} digit(s) missing in the last group"
            )
    return [digits[i:i + group_size] for i in range(0, len(digits), group_size)]


def random_groups(count: int, group_size: int = DEFAULT_GROUP_SIZE) -> list[str]:
    """Random groups from the system's secure random source.

    Good for test transmissions and for filler messages that keep the
    schedule busy when there is nothing to say.
    """
    if count < 1:
        raise GroupError("count must be at least 1")
    return ["".join(secrets.choice("0123456789") for _ in range(group_size)) for _ in range(count)]


def validate_callsign(callsign: str) -> str:
    """A station callsign here is a short string of digits, such as "472"."""
    callsign = _SEPARATORS.sub("", callsign or "")
    if not callsign or not callsign.isdigit() or not callsign.isascii():
        raise GroupError("the callsign must be digits only, for example 472")
    if len(callsign) > 10:
        raise GroupError("the callsign may have at most 10 digits")
    return callsign
