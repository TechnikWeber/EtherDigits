# Plan

EtherDigits is a numbers station you run yourself: it reads out groups of digits
in a fixed, recognisable format, on a schedule, around the clock, through a sound
card, a radio or an internet stream.

## Principles

- **A dumb transmitter.** The station receives finished digit groups. Keys and
  plain text live in a separate offline tool. Whoever gets hold of the station
  learns nothing. Encrypting on the station is possible, but optional and marked
  as the weaker choice.
- **One-time pad.** The only method that cannot be broken. The receiver needs a
  radio, a pencil and a pad of key pages, and no computer.
- **Recorded voices.** Voice packs are folders of clips, generated once with Piper
  (or recorded by hand). Nothing is synthesised while the station runs.
- **Runs unattended.** Survives restarts, keeps its queue, checks its clock,
  limits transmit time and reports problems.
- **Linux, Windows, macOS.** Python service, web interface, no platform-specific
  parts in the core.

## Architecture

```
 offline tool (one HTML file)            remote clients
 pads, encode, decode                    web UI, API with token
        │ digit groups                          │
        └───────────────┬───────────────────────┘
                        ▼
   service: queue (SQLite) → scheduler → script builder → renderer
                                                              │
         sound card + PTT (serial RTS/DTR) / CAT (Hamlib rigctld)
         Icecast stream · WAV/MP3 file · transmission log
```

## Stages

### 1. Core (done in 0.1)

- [x] Digit groups: parse, validate, pad, random test groups
- [x] Voice packs: format, loader, search path (`ETHERDIGITS_VOICES`)
- [x] Voice packs built with Piper: `de-kerstin`, `de-thorsten`, `en-ljspeech`
- [x] Transmission script: interval signal, callsign, group count, message,
      repeats, separator, "no message", end, end tone
- [x] Renderer: clips, tones, interval melody, "radio" effect, WAV and MP3
- [x] Command line: `voices`, `render`
- [x] Tests

### 2. Offline tool

- [ ] One self-contained HTML file, works without network
- [ ] Pad generator using the browser's secure random source, printable pads
      (one page per message, page number as indicator group)
- [ ] Straddling checkerboard (German and English layouts) and a small codebook
- [ ] Encode and decode, addition without carry (mod 10)
- [ ] Used-page register that refuses to use a page twice
- [ ] The same logic in Python (`etherdigits.otp`), tested against the HTML tool

### 3. Service

- [ ] Message queue in SQLite: priority, expiry, repeat count, burn after sending
- [ ] Scheduler: fixed UTC times, every N minutes, weekdays, several schedules
- [ ] Filler messages when the queue is empty (no traffic analysis)
- [ ] Web interface (English, Deutsch): queue, schedule, preview, log, settings
- [ ] HTTP API with tokens to submit messages remotely
- [ ] Optional encryption on the station from stored pads, clearly warned

### 4. Radio

- [ ] Sound card output with device selection (`sounddevice`), VOX
- [ ] PTT via serial RTS/DTR (e.g. Digirig), GPIO on a Raspberry Pi
- [ ] CAT via Hamlib `rigctld`: frequency and mode per schedule, PTT
- [ ] Transmit time limit, emergency stop, PTT always released on errors
- [ ] Morse identification

### 5. Unattended and remote

- [ ] Service setup: systemd, Windows service, launchd; `install.sh`
- [ ] Health page, clock check (NTP), sound device reconnect
- [ ] Login with optional TOTP; "submitter" role that can only hand in messages
- [ ] Icecast stream
- [ ] Packages for Windows and macOS in releases
- [ ] Practice mode for receivers: dictation and check

## Legal

Encrypted or obscured content is not allowed on amateur radio bands. Use an
internet stream, a dummy load, local playback, or a service licensed for it.
