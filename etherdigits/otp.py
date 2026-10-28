"""One-time pad, straddling checkerboard and codebook.

Encryption, step by step:

1. Normalise the text: upper case, Ä→AE, Ö→OE, Ü→UE, ß→SS, accents removed.
2. Encode it into digits with the checkerboard. Frequent letters take one
   digit, the rest two; codebook words take five (99 + three digits);
   numbers are written in figure mode (98, every digit doubled, 98).
3. Pad with 9s to a full group. A 9 or 99 at the very end is an unfinished
   code, which the decoder ignores, so padding never shows up in the text.
4. Pads made with a check group (the default) add one more group: digit by
   digit the column sums of all groups, mod 10. It is encrypted with the
   rest, so only the receiver can tell a message from filler; a single
   misheard digit always shows. It can be checked with pencil and paper.
5. Add the key page digit by digit without carry (mod 10).
6. Put the page id in front, unencrypted, so the receiver knows which page
   to use.

The browser tool (pad_tool.html) contains the same logic in JavaScript;
tests/test_interop.py checks that both agree digit for digit.

This file must stay in step with the "engine" script in pad_tool.html.
"""

from __future__ import annotations

import json
import secrets
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

GROUP_SIZE = 5
FIG = "98"
CODE = "99"
PAD_DIGIT = "9"
ASCII_DIGITS = "0123456789"

# Rows 7 and 8 are prefixes for two-digit letters, row 9 for signs and modes.
LAYOUTS: dict[str, dict[str, str]] = {
    # German: E N I S R A T cover about 62 % of the letters in German text.
    "de": {"top": "ENISRAT", "7": "DHULCGMOBW", "8": "FKZPVJYXQ:"},
    # English: E T A O I N S cover about 58 % of the letters in English text.
    "en": {"top": "ETAOINS", "7": "RHDLCUMWFG", "8": "YPBVKJXQZ:"},
}
SIGNS = {" ": "90", ".": "91", ",": "92", "?": "93", "-": "94", "/": "95", "(": "96", ")": "97"}
# Signs that are typed differently but mean the same.
SIGN_ALIASES = {"!": ".", ";": ",", "–": "-", "—": "-", "\n": " ", "\t": " ", "\r": " "}

DEFAULT_CODEBOOKS: dict[str, dict[str, str]] = {
    "de": {
        "100": "ABBRECHEN", "101": "ABFAHRT", "102": "ADRESSE", "103": "ANKUNFT", "104": "BAHNHOF",
        "105": "BESTÄTIGEN", "106": "DRINGEND", "107": "FLUGHAFEN", "108": "GEFAHR", "109": "GELD",
        "110": "GESTERN", "111": "HEUTE", "112": "HOTEL", "113": "KONTAKT", "114": "MORGEN",
        "115": "NACHRICHT", "116": "PAKET", "117": "SOFORT", "118": "TELEFON", "119": "TREFFEN",
        "120": "TREFFPUNKT", "121": "UHR", "122": "VERSCHIEBEN", "123": "WARTEN", "124": "WIEDERHOLEN",
        "125": "MONTAG", "126": "DIENSTAG", "127": "MITTWOCH", "128": "DONNERSTAG", "129": "FREITAG",
        "130": "SAMSTAG", "131": "SONNTAG", "132": "NICHT", "133": "UND", "134": "ODER",
    },
    "en": {
        "100": "ABORT", "101": "DEPARTURE", "102": "ADDRESS", "103": "ARRIVAL", "104": "STATION",
        "105": "CONFIRM", "106": "URGENT", "107": "AIRPORT", "108": "DANGER", "109": "MONEY",
        "110": "YESTERDAY", "111": "TODAY", "112": "HOTEL", "113": "CONTACT", "114": "TOMORROW",
        "115": "MESSAGE", "116": "PACKAGE", "117": "IMMEDIATELY", "118": "TELEPHONE", "119": "MEET",
        "120": "MEETING", "121": "OCLOCK", "122": "POSTPONE", "123": "WAIT", "124": "REPEAT",
        "125": "MONDAY", "126": "TUESDAY", "127": "WEDNESDAY", "128": "THURSDAY", "129": "FRIDAY",
        "130": "SATURDAY", "131": "SUNDAY", "132": "NOT", "133": "AND", "134": "OR",
    },
}


class OtpError(ValueError):
    pass


# --- text and checkerboard -------------------------------------------------

def normalize(text: str) -> tuple[str, list[str]]:
    """Upper-case text the checkerboard can write, and the characters it had to drop."""
    out: list[str] = []
    dropped: list[str] = []
    for ch in text:
        ch = SIGN_ALIASES.get(ch, ch)
        up = {"ä": "AE", "Ä": "AE", "ö": "OE", "Ö": "OE", "ü": "UE", "Ü": "UE", "ß": "SS", "ẞ": "SS"}.get(ch)
        if up is None:
            base = unicodedata.normalize("NFD", ch)[0]
            up = base.upper() if "a" <= base.lower() <= "z" else base
        for c in up:
            if "A" <= c <= "Z" or "0" <= c <= "9" or c in SIGNS or c == ":":
                out.append(c)
            elif ch not in dropped:
                dropped.append(ch)
    # One space between words, none at the ends.
    text = "".join(out)
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip(), dropped


def _table(lang: str) -> dict[str, str]:
    if lang not in LAYOUTS:
        raise OtpError(f"unknown checkerboard language {lang!r} (available: {', '.join(LAYOUTS)})")
    layout = LAYOUTS[lang]
    table = {ch: str(i) for i, ch in enumerate(layout["top"])}
    for row in ("7", "8"):
        for i, ch in enumerate(layout[row]):
            table[ch] = row + str(i)
    table.update(SIGNS)
    return table


def normalize_codebook(codebook: dict[str, str] | None) -> dict[str, str]:
    """code -> normalised word; codes must be three digits, words unique."""
    result: dict[str, str] = {}
    seen: set[str] = set()
    for code, word in (codebook or {}).items():
        code = str(code).strip()
        if len(code) != 3 or not code.isdigit() or not code.isascii():
            raise OtpError(f"codebook code {code!r} must be three digits")
        norm, _ = normalize(word)
        if not norm or not norm.isalpha():
            raise OtpError(f"codebook entry {code} must be a single word: {word!r}")
        if norm in seen:
            raise OtpError(f"codebook word {norm} appears twice")
        seen.add(norm)
        result[code] = norm
    return result


def parse_codebook(text: str) -> dict[str, str]:
    """Lines like "119 TREFFEN" or "119=TREFFEN"; # starts a comment."""
    book: dict[str, str] = {}
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.replace("=", " ").split(None, 1)
        if len(parts) != 2:
            raise OtpError(f"codebook line {n}: expected 'code word'")
        book[parts[0]] = parts[1].strip()
    return normalize_codebook(book)


def encode(text: str, lang: str = "de", codebook: dict[str, str] | None = None, spaces: bool = True) -> str:
    """Text to checkerboard digits (not yet encrypted)."""
    table = _table(lang)
    words = {w: c for c, w in normalize_codebook(codebook).items()}
    norm, _ = normalize(text)
    if not spaces:
        norm = norm.replace(" ", "")
    out: list[str] = []
    i = 0
    while i < len(norm):
        ch = norm[i]
        if ch in ASCII_DIGITS:
            j = i
            while j < len(norm) and norm[j] in ASCII_DIGITS:
                j += 1
            out.append(FIG + "".join(d * 2 for d in norm[i:j]) + FIG)
            i = j
        elif "A" <= ch <= "Z":
            j = i
            while j < len(norm) and "A" <= norm[j] <= "Z":
                j += 1
            word = norm[i:j]
            if word in words:
                out.append(CODE + words[word])
            else:
                out.append("".join(table[c] for c in word))
            i = j
        else:
            out.append(table[ch])
            i += 1
    return "".join(out)


def decode(digits: str, lang: str = "de", codebook: dict[str, str] | None = None) -> str:
    """Checkerboard digits back to text. An unfinished code at the end is ignored."""
    reverse = {v: k for k, v in _table(lang).items()}
    book = normalize_codebook(codebook)
    digits = "".join(c for c in digits if c in ASCII_DIGITS)
    out: list[str] = []
    i, n = 0, len(digits)
    while i < n:
        d = digits[i]
        if d not in "789":
            out.append(reverse[d])
            i += 1
            continue
        if i + 1 >= n:
            break  # padding
        pair = digits[i:i + 2]
        if pair == CODE:
            if i + 5 > n:
                break  # padding
            code = digits[i + 2:i + 5]
            out.append(book.get(code, f"[{code}]"))
            i += 5
        elif pair == FIG:
            i += 2
            while i + 1 < n and digits[i:i + 2] != FIG:
                a, b = digits[i], digits[i + 1]
                out.append(a if a == b else "?")
                i += 2
            i += 2  # closing FIG (or the end)
        else:
            out.append(reverse.get(pair, "?"))
            i += 2
    return "".join(out).strip()


# --- key arithmetic ----------------------------------------------------------

def add(plain: str, key: str) -> str:
    """Digit-wise addition without carry: 7 + 5 = 2."""
    return "".join(str((int(p) + int(k)) % 10) for p, k in zip(plain, key))


def subtract(cipher: str, key: str) -> str:
    return "".join(str((int(c) - int(k)) % 10) for c, k in zip(cipher, key))


def groups_of(digits: str, size: int = GROUP_SIZE) -> list[str]:
    return [digits[i:i + size] for i in range(0, len(digits), size)]


def random_digits(n: int) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(n))


# --- pads --------------------------------------------------------------------

@dataclass
class Pad:
    """A pad of key pages. Sender and receiver each get an identical copy."""

    pages: dict[str, str]                       # page id -> key digits
    language: str = "de"
    codebook: dict[str, str] = field(default_factory=dict)
    group_size: int = GROUP_SIZE
    spaces: bool = True
    created: str = ""
    used: list[str] = field(default_factory=list)
    name: str = ""
    check: bool = False                         # last group is a check group (pads before 0.6 have none)

    def unused(self) -> list[str]:
        return [p for p in self.pages if p not in self.used]

    def to_json(self) -> dict:
        return {
            "format": "etherdigits-pad",
            "version": 1,
            "name": self.name,
            "created": self.created,
            "language": self.language,
            "group_size": self.group_size,
            "spaces": self.spaces,
            "check": self.check,
            "codebook": self.codebook,
            "pages": [{"id": pid, "key": key} for pid, key in self.pages.items()],
            "used": self.used,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Pad":
        if data.get("format") != "etherdigits-pad":
            raise OtpError("not an EtherDigits pad file")
        if data.get("version") != 1:
            raise OtpError(f"unsupported pad version {data.get('version')!r}")
        pages: dict[str, str] = {}
        for page in data.get("pages") or []:
            pid, key = str(page.get("id", "")), str(page.get("key", ""))
            if not pid or not key or any(c not in ASCII_DIGITS for c in pid + key):
                raise OtpError(f"broken page in pad file: {pid!r}")
            pages[pid] = key
        if not pages:
            raise OtpError("the pad has no pages")
        pad = cls(
            pages=pages,
            language=data.get("language") or "de",
            codebook=normalize_codebook(data.get("codebook") or {}),
            group_size=int(data.get("group_size") or GROUP_SIZE),
            spaces=bool(data.get("spaces", True)),
            created=data.get("created") or "",
            used=[str(u) for u in data.get("used") or []],
            name=data.get("name") or "",
            check=bool(data.get("check", False)),
        )
        _table(pad.language)
        return pad


def new_pad(pages: int = 20, groups_per_page: int = 50, language: str = "de",
            codebook: dict[str, str] | None = None, group_size: int = GROUP_SIZE,
            spaces: bool = True, name: str = "", check: bool = True) -> Pad:
    """A fresh pad. Page ids are random, so they do not reveal how many messages were sent."""
    if not 1 <= pages <= 1000:
        raise OtpError("pages must be between 1 and 1000")
    if not 5 <= groups_per_page <= 1000:
        raise OtpError("groups per page must be between 5 and 1000")
    _table(language)
    ids: set[str] = set()
    while len(ids) < pages:
        ids.add(random_digits(group_size))
    book = normalize_codebook(DEFAULT_CODEBOOKS.get(language, {}) if codebook is None else codebook)
    return Pad(
        pages={pid: random_digits(groups_per_page * group_size) for pid in ids},
        language=language,
        codebook=book,
        group_size=group_size,
        spaces=spaces,
        created=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        name=name,
        check=check,
    )


def load_pad(path: Path) -> Pad:
    try:
        return Pad.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        raise OtpError(f"{path}: not a valid pad file ({exc})") from exc


def save_pad(pad: Pad, path: Path) -> None:
    """Write atomically, so a crash never leaves half a pad behind."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(pad.to_json(), indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def check_group(digits: str, size: int = GROUP_SIZE) -> str:
    """Column sums of all groups, mod 10: 12345 + 67890 -> 79135."""
    sums = [0] * size
    for i, d in enumerate(digits):
        sums[i % size] += int(d)
    return "".join(str(s % 10) for s in sums)


def prepare(text: str, pad: Pad) -> str:
    """The plain digits that get encrypted: checkerboard, padding, check group."""
    plain = encode(text, pad.language, pad.codebook, pad.spaces)
    if not plain:
        return ""
    size = pad.group_size
    plain += PAD_DIGIT * (-len(plain) % size)
    if pad.check:
        plain += check_group(plain, size)
    return plain


def encrypt(text: str, pad: Pad, page_id: str | None = None) -> list[str]:
    """Encrypt with an unused page and mark it used. Returns indicator group + cipher groups."""
    if page_id is None:
        free = pad.unused()
        if not free:
            raise OtpError("every page of this pad is used; make a new pad")
        page_id = free[0]
    if page_id not in pad.pages:
        raise OtpError(f"page {page_id} is not in this pad")
    if page_id in pad.used:
        raise OtpError(f"page {page_id} was already used. A page must never be used twice")
    plain = prepare(text, pad)
    if not plain:
        raise OtpError("the message is empty")
    size = pad.group_size
    key = pad.pages[page_id]
    if len(plain) > len(key):
        raise OtpError(
            f"the message needs {len(plain) // size} groups, a page has {len(key) // size}; shorten it"
        )
    pad.used.append(page_id)
    return [page_id] + groups_of(add(plain, key), size)


def decrypt(groups: list[str] | str, pad: Pad, mark_used: bool = True) -> str:
    """Decrypt indicator group + cipher groups to text. Decrypting a used page again is fine."""
    return decrypt_message(groups, pad, mark_used)["text"]


def unpack(plain: str, check: bool, size: int = GROUP_SIZE) -> tuple[str, bool | None]:
    """Split off and verify the check group: (message digits, True/False, or None without check)."""
    if not check:
        return plain, None
    if len(plain) < 2 * size or len(plain) % size:
        return plain[:len(plain) - len(plain) % size - size] if len(plain) > size else "", False
    body, given = plain[:-size], plain[-size:]
    return body, check_group(body, size) == given


def decrypt_message(groups: list[str] | str, pad: Pad, mark_used: bool = True) -> dict:
    """Like decrypt, with the check result: {"text", "check": True | False | None, "plain"}."""
    if isinstance(groups, str):
        groups = groups.split()
    digits = "".join(c for c in "".join(groups) if c in ASCII_DIGITS)
    size = pad.group_size
    page_id, cipher = digits[:size], digits[size:]
    if page_id not in pad.pages:
        raise OtpError(f"page {page_id} is not in this pad")
    key = pad.pages[page_id]
    if len(cipher) > len(key):
        raise OtpError("the message is longer than the key page")
    if mark_used and page_id not in pad.used:
        pad.used.append(page_id)
    plain = subtract(cipher, key)
    body, ok = unpack(plain, pad.check, size)
    return {"text": decode(body, pad.language, pad.codebook), "check": ok, "plain": plain}
