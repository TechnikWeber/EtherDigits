"""Command line: list voices, render a transmission to WAV or MP3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .groups import DEFAULT_GROUP_SIZE, GroupError, parse_groups, random_groups
from .render import DEFAULT_RATE, EFFECTS, render, write_audio
from .script import INTERVALS, Format, Transmission, build_script, transcript
from .voicepack import VoicePackError, find_pack, list_packs


def cmd_voices(_args: argparse.Namespace) -> int:
    packs = list_packs()
    if not packs:
        print("no voice packs found")
        return 1
    for pack in packs:
        words = sum(1 for t in pack.clips if not t.isdigit())
        print(f"{pack.id:16} {pack.language:4} {pack.name}  [{pack.license}, {words} words]")
    return 0


def build_format(args: argparse.Namespace) -> Format:
    data: dict = {}
    if args.format_file:
        data = json.loads(Path(args.format_file).read_text(encoding="utf-8"))
    overrides = {
        "callsign": args.callsign,
        "interval": args.interval,
        "interval_repeats": args.interval_repeats,
        "callsign_repeats": args.callsign_repeats,
        "message_repeats": args.repeats,
    }
    data.update({k: v for k, v in overrides.items() if v is not None})
    if args.group_twice:
        data["group_twice"] = True
    return Format.from_dict(data)


def cmd_render(args: argparse.Namespace) -> int:
    fmt = build_format(args)
    messages = [parse_groups(m, args.group_size, args.pad) for m in args.message or []]
    if args.random:
        messages.append(random_groups(args.random, args.group_size))
    steps = build_script(Transmission(messages=messages, format=fmt))
    if args.print or not args.output:
        print(transcript(steps, fmt), flush=True)
    if not args.output:
        return 0
    pack = find_pack(args.voice)
    audio = render(steps, pack, rate=args.rate, effect=args.effect)
    write_audio(Path(args.output), audio, args.rate)
    seconds = len(audio) / args.rate
    print(f"wrote {args.output} ({int(seconds // 60)}:{int(seconds % 60):02d} min, voice {pack.id})", file=sys.stderr)
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="etherdigits", description="Run your own numbers station.")
    p.add_argument("--version", action="version", version=f"EtherDigits {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("voices", help="list voice packs")
    v.set_defaults(func=cmd_voices)

    r = sub.add_parser("render", help="build a transmission and write it as WAV or MP3",
                       description="Without -m or --random a 'no message' transmission is built. "
                                   "Without -o the transcript is printed only.")
    r.add_argument("-m", "--message", action="append", metavar="GROUPS",
                   help='digit groups, e.g. "12345 67890" (repeat -m for several messages)')
    r.add_argument("--random", type=int, metavar="N", help="add a test message of N random groups")
    r.add_argument("-o", "--output", metavar="FILE", help="output file, .wav or .mp3")
    r.add_argument("--voice", default="de", help="voice pack id, language or folder (default: de)")
    r.add_argument("--callsign", help="station callsign, digits (default: 472)")
    r.add_argument("--repeats", type=int, help="how often each message is read (default: 2)")
    r.add_argument("--callsign-repeats", type=int, help="how often the callsign is read (default: 3)")
    r.add_argument("--interval", choices=INTERVALS, help="interval signal (default: melody)")
    r.add_argument("--interval-repeats", type=int, help="how often the interval signal plays (default: 2)")
    r.add_argument("--group-twice", action="store_true", help="read every group twice")
    r.add_argument("--group-size", type=int, default=DEFAULT_GROUP_SIZE, help="digits per group (default: 5)")
    r.add_argument("--pad", choices=("random", "zero"), help="fill a short last group instead of failing")
    r.add_argument("--effect", choices=EFFECTS, default="none", help="'radio' sounds like shortwave AM")
    r.add_argument("--rate", type=int, default=DEFAULT_RATE, help=f"sample rate (default: {DEFAULT_RATE})")
    r.add_argument("--format-file", metavar="JSON", help="format settings from a JSON file")
    r.add_argument("--print", action="store_true", help="also print the transcript")
    r.set_defaults(func=cmd_render)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except (GroupError, VoicePackError, ValueError, RuntimeError, OSError) as exc:
        print(f"etherdigits: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
