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

### 2. Offline tool (done in 0.2)

- [x] One self-contained HTML file (`pad_tool.html`), no network access
- [x] Pad generator using the secure random source, printable pads
      (one page per message, random page id as indicator group)
- [x] Straddling checkerboard (German and English layouts), editable codebook
- [x] Encode and decode, addition without carry (mod 10)
- [x] Used pages are refused; the browser also remembers them in case an old
      pad file is loaded again
- [x] The same logic in Python (`etherdigits.otp`, CLI `pad`, `encrypt`,
      `decrypt`, `checkerboard`), tested against the HTML tool

### 3. Service (done in 0.3)

- [x] Message queue in SQLite: priority, not before, expiry, number of
      transmissions, burn after sending, bound to a schedule or any
- [x] Scheduler: fixed UTC times on weekdays, every N minutes with offset,
      several schedules; rendered ahead, sent on the second, never late
- [x] Filler when the queue is empty: random groups, "no message" or silence
- [x] Web interface (English, Deutsch): overview, queue, schedules with editor
      and preview, log with recordings, settings
- [x] HTTP API: tokens that can only submit
- [x] Admin password (scrypt), sessions, login brake, local-only access
      without a password, cross-site request protection
- [x] Optional encryption on the station from uploaded pads, off by default
- [x] Discreet log: no difference between message and filler on record

### 4. Radio (done in 0.4, not yet tried on a real radio)

- [x] Sound card output with device selection and level; resampled to the
      device's rate
- [x] Monitor: the same audio on a second device of the station computer, off
      by default
- [x] Live level meter (server-sent events) in the header and on the overview
- [x] PTT: VOX, serial RTS/DTR (also inverted), CAT; lead and tail time; always
      released on errors
- [x] CAT via Hamlib `rigctld`: frequency and mode per schedule, set before the
      slot; a failure cancels the transmission
- [x] Transmit time limit, checked before going on air and while playing
- [x] Emergency stop that locks the transmitter until released; test tone
- [x] Morse identification at the end of a transmission
- [ ] GPIO PTT on a Raspberry Pi

### 5. Unattended and remote (done in 0.5)

- [x] Service setup: systemd user service, launchd agent, Windows Startup
      entry with a restarting supervisor; `install.sh`, `install.ps1`
- [x] Clock check against a time server every hour (SNTP), scheduling by the
      corrected time, warning above 2 s
- [x] `/api/health` for monitoring tools
- [x] Sound devices are looked up afresh for every transmission, so a
      replugged USB sound card is found again
- [x] Two-factor login (TOTP) with replay protection; `totp-off` for a lost
      authenticator
- [x] Icecast stream around the clock, reconnecting with back-off
- [x] Packaged programs for Windows, macOS and Linux (PyInstaller, built on tags)
- [x] Practice mode for receivers: dictation, checked group by group

- [x] PTT via a GPIO pin of a Raspberry Pi (kernel GPIO interface, Pi 1 to 5),
      ARM64 build and tests

## Later

- [ ] Try the whole chain with a real radio and a Digirig
- [ ] Try GPIO PTT on a real Raspberry Pi

## Legal

Encrypted or obscured content is not allowed on amateur radio bands. Use an
internet stream, a dummy load, local playback, or a service licensed for it.
