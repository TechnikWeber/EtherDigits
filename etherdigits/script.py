"""The transmission script: what is said, in which order, with which pauses.

A transmission follows the pattern real numbers stations use:

    interval signal        a short tune or beeps, so listeners can tune in
    "Attention" + callsign, several times
    for each message:
        "Groups" + group count (twice)
        the groups
        "Repeat" + the groups again (as often as configured)
        "Separator" between messages
    "No message" when there is nothing to send
    "End"

The script is a plain list of steps. Rendering turns it into audio, and
`transcript` turns it into text for logs and previews.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

from .groups import GroupError, validate_callsign


@dataclass(frozen=True)
class Say:
    token: str  # "0".."9" or a word from voicepack.WORDS


@dataclass(frozen=True)
class Pause:
    seconds: float


@dataclass(frozen=True)
class Tone:
    freq: float
    seconds: float


@dataclass(frozen=True)
class Melody:
    name: str  # see render.MELODIES


Step = Say | Pause | Tone | Melody

INTERVALS = ("melody", "beeps", "none")


@dataclass
class Format:
    """Everything about how a transmission sounds, except the voice."""

    callsign: str = "472"
    interval: str = "melody"         # melody | beeps | none
    interval_repeats: int = 2
    callsign_repeats: int = 3
    announce_group_count: bool = True
    message_repeats: int = 2         # how often each message is read in total
    group_twice: bool = False        # read every group twice ("12345 12345 ...")
    digit_gap: float = 0.18          # seconds between digits of a group
    group_gap: float = 0.9           # seconds between groups
    section_gap: float = 1.6         # seconds between parts of the transmission
    end_tone: bool = True

    def validate(self) -> None:
        self.callsign = validate_callsign(self.callsign)
        if self.interval not in INTERVALS:
            raise GroupError(f"interval must be one of {', '.join(INTERVALS)}")
        for name in ("interval_repeats", "callsign_repeats", "message_repeats"):
            value = getattr(self, name)
            if not isinstance(value, int) or not 0 <= value <= 100:
                raise GroupError(f"{name} must be a whole number from 0 to 100")
        if self.message_repeats < 1:
            raise GroupError("message_repeats must be at least 1")
        for name in ("digit_gap", "group_gap", "section_gap"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not 0 <= value <= 30:
                raise GroupError(f"{name} must be between 0 and 30 seconds")

    @classmethod
    def from_dict(cls, data: dict) -> "Format":
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise GroupError("unknown format setting(s): " + ", ".join(sorted(unknown)))
        fmt = cls(**data)
        fmt.validate()
        return fmt


@dataclass
class Transmission:
    messages: list[list[str]] = field(default_factory=list)  # each message is a list of groups
    format: Format = field(default_factory=Format)


def _digits(text: str, gap: float) -> list[Step]:
    steps: list[Step] = []
    for i, d in enumerate(text):
        if i:
            steps.append(Pause(gap))
        steps.append(Say(d))
    return steps


def _groups(groups: list[str], fmt: Format) -> list[Step]:
    steps: list[Step] = []
    for i, group in enumerate(groups):
        for n in range(2 if fmt.group_twice else 1):
            if i or n:
                steps.append(Pause(fmt.group_gap))
            steps += _digits(group, fmt.digit_gap)
    return steps


def build_script(tx: Transmission) -> list[Step]:
    fmt = tx.format
    fmt.validate()
    steps: list[Step] = []

    def section(part: list[Step]) -> None:
        if steps:
            steps.append(Pause(fmt.section_gap))
        steps.extend(part)

    for _ in range(fmt.interval_repeats if fmt.interval != "none" else 0):
        if fmt.interval == "melody":
            section([Melody("ether")])
        else:
            section([Tone(1000, 0.25), Pause(0.25), Tone(1000, 0.25), Pause(0.25), Tone(1000, 0.25)])

    if fmt.callsign_repeats:
        call: list[Step] = [Say("attention")]
        for i in range(fmt.callsign_repeats):
            call += [Pause(fmt.group_gap)] + _digits(fmt.callsign, fmt.digit_gap)
        section(call)

    if not tx.messages:
        section([Say("no_message")])

    for m, groups in enumerate(tx.messages):
        if m:
            section([Say("separator")])
        if fmt.announce_group_count:
            count = str(len(groups))
            section([Say("groups"), Pause(fmt.group_gap)] + _digits(count, fmt.digit_gap)
                    + [Pause(fmt.group_gap)] + _digits(count, fmt.digit_gap))
        section(_groups(groups, fmt))
        for _ in range(fmt.message_repeats - 1):
            section([Say("repeat"), Pause(fmt.group_gap)] + _groups(groups, fmt))

    section([Say("end")])
    if fmt.end_tone:
        section([Tone(800, 0.8)])
    return steps


_WORD_LABELS = {
    "attention": "ATTENTION",
    "groups": "GROUPS",
    "repeat": "REPEAT",
    "separator": "SEPARATOR",
    "no_message": "NO MESSAGE",
    "end": "END",
}


def transcript(steps: list[Step], fmt: Format) -> str:
    """Readable text of a script: digits of a group are joined, gaps become breaks."""
    lines: list[str] = []
    line: list[str] = []
    word = ""

    def flush_word() -> None:
        nonlocal word
        if word:
            line.append(word)
            word = ""

    def flush_line() -> None:
        flush_word()
        if line:
            lines.append(" ".join(line))
            line.clear()

    for step in steps:
        if isinstance(step, Say):
            if step.token.isdigit():
                word += step.token
            else:
                flush_word()
                line.append(_WORD_LABELS.get(step.token, step.token.upper()))
        elif isinstance(step, Pause):
            if step.seconds >= fmt.section_gap:
                flush_line()
            elif step.seconds >= fmt.group_gap:
                flush_word()
        elif isinstance(step, Melody):
            flush_line()
            lines.append(f"[interval signal: {step.name}]")
        elif isinstance(step, Tone):
            flush_line()
            lines.append(f"[tone {step.freq:g} Hz]")
    flush_line()
    # Beeps come as several tones in a row; show them once.
    out: list[str] = []
    for text in lines:
        if not (out and text.startswith("[tone") and out[-1] == text):
            out.append(text)
    return "\n".join(out)
