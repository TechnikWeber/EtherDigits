"""Command line: voices, transmissions, pads, encryption."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import otp
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


def _read_text(value: str | None) -> str:
    """The argument, or standard input when it is missing or "-"."""
    if value is None or value == "-":
        return sys.stdin.read()
    return value


def cmd_pad_new(args: argparse.Namespace) -> int:
    out = Path(args.output)
    if out.exists() and not args.force:
        raise otp.OtpError(f"{out} exists. Overwriting a pad destroys its keys; use --force if you mean it")
    if args.no_codebook:
        codebook: dict | None = {}
    elif args.codebook:
        codebook = otp.parse_codebook(Path(args.codebook).read_text(encoding="utf-8"))
    else:
        codebook = None
    pad = otp.new_pad(args.pages, args.groups, args.lang, codebook, spaces=not args.no_spaces, name=args.name or "")
    otp.save_pad(pad, out)
    print(f"wrote {out}: {len(pad.pages)} pages of {args.groups} groups, checkerboard {pad.language}, "
          f"{len(pad.codebook)} codebook words")
    print("Hand an identical copy to the receiver in person, never over the internet.")
    return 0


def cmd_pad_info(args: argparse.Namespace) -> int:
    pad = otp.load_pad(Path(args.pad))
    pages = len(pad.pages)
    groups = len(next(iter(pad.pages.values()))) // pad.group_size
    print(f"pad        {pad.name or Path(args.pad).name}")
    print(f"created    {pad.created}")
    print(f"pages      {pages} ({len(pad.unused())} unused, {len(pad.used)} used), {groups} groups each")
    print(f"language   {pad.language}, codebook {len(pad.codebook)} words, spaces {'on' if pad.spaces else 'off'}")
    return 0


def cmd_encrypt(args: argparse.Namespace) -> int:
    path = Path(args.pad)
    pad = otp.load_pad(path)
    text = _read_text(args.text)
    _, dropped = otp.normalize(text)
    groups = otp.encrypt(text, pad, args.page)
    otp.save_pad(pad, path)
    if dropped:
        print("left out: " + " ".join(dropped), file=sys.stderr)
    print(f"page {groups[0]} is now marked used, {len(pad.unused())} pages left", file=sys.stderr)
    print(" ".join(groups))
    return 0


def cmd_decrypt(args: argparse.Namespace) -> int:
    path = Path(args.pad)
    pad = otp.load_pad(path)
    text = otp.decrypt(_read_text(args.groups), pad)
    otp.save_pad(pad, path)
    print(text)
    return 0


def cmd_checkerboard(args: argparse.Namespace) -> int:
    layout = otp.LAYOUTS[args.lang]
    signs = {v: k for k, v in otp.SIGNS.items()}
    names = {" ": "space", otp.FIG: "fig", otp.CODE: "code"}
    print("     " + "  ".join(f"{i:>5}" for i in range(10)))
    print("     " + "  ".join(f"{c:>5}" for c in layout["top"].ljust(10)))
    for row in ("7", "8"):
        print(f"  {row}  " + "  ".join(f"{c:>5}" for c in layout[row]))
    nine = []
    for i in range(10):
        code = "9" + str(i)
        sign = signs.get(code)
        nine.append(names.get(sign, sign) if sign else names.get(code, ""))
    print("  9  " + "  ".join(f"{c:>5}" for c in nine))
    print()
    print("fig: 98, every digit twice, 98   (1830 -> 98 11 88 33 00 98)")
    print("code: 99 and a three-digit codebook number")
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

    pad = sub.add_parser("pad", help="one-time pads: create, show")
    pad_sub = pad.add_subparsers(dest="pad_command", required=True)
    pn = pad_sub.add_parser("new", help="create a new pad file")
    pn.add_argument("-o", "--output", required=True, metavar="FILE", help="pad file to write (.json)")
    pn.add_argument("--pages", type=int, default=20, help="number of key pages (default: 20)")
    pn.add_argument("--groups", type=int, default=50, help="groups per page (default: 50)")
    pn.add_argument("--lang", choices=sorted(otp.LAYOUTS), default="de", help="checkerboard language (default: de)")
    pn.add_argument("--codebook", metavar="FILE", help="own codebook: lines of 'code word'")
    pn.add_argument("--no-codebook", action="store_true", help="no codebook at all")
    pn.add_argument("--no-spaces", action="store_true", help="leave out spaces between words (shorter)")
    pn.add_argument("--name", help="a name for the pad")
    pn.add_argument("--force", action="store_true", help="overwrite an existing file")
    pn.set_defaults(func=cmd_pad_new)
    pi = pad_sub.add_parser("info", help="show pages left and settings")
    pi.add_argument("pad", metavar="FILE")
    pi.set_defaults(func=cmd_pad_info)

    e = sub.add_parser("encrypt", help="encrypt text with the next unused page of a pad")
    e.add_argument("--pad", required=True, metavar="FILE")
    e.add_argument("--page", help="use this page id instead of the next unused one")
    e.add_argument("text", nargs="?", help="the message (default: read standard input)")
    e.set_defaults(func=cmd_encrypt)

    d = sub.add_parser("decrypt", help="decrypt digit groups with a pad")
    d.add_argument("--pad", required=True, metavar="FILE")
    d.add_argument("groups", nargs="?", help="indicator group and message (default: read standard input)")
    d.set_defaults(func=cmd_decrypt)

    c = sub.add_parser("checkerboard", help="print the checkerboard for pencil and paper")
    c.add_argument("--lang", choices=sorted(otp.LAYOUTS), default="de")
    c.set_defaults(func=cmd_checkerboard)
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
