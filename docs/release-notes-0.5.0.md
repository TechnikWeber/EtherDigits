First public pre-release. Everything in the plan is built; the radio output has not been tried with a real radio yet.

**Station**
- Transmissions in the classic numbers station format: interval signal, callsign, group count, message, repeat, end, optional Morse identification
- Three free voices: Kerstin and Thorsten (German), LJ (English); add your own recordings
- Schedules in UTC (fixed times on weekdays, or every N minutes), queue with priority, expiry and number of transmissions, filler of random groups when nothing is waiting
- Web interface in English and German: overview with live level meter, messages, schedules, log with transcripts and recordings, listening practice, settings
- Submit API with tokens that can do nothing but hand in messages

**One-time pad**
- `pad_tool.html`: offline browser tool for pads, encryption, decryption and printing, refuses to use a page twice
- The same in Python and on the command line, checked against the browser tool digit for digit

**Radio and stream**
- Sound card output, monitor on the station computer (off by default), PTT via VOX, serial RTS/DTR, CAT (Hamlib rigctld) or a Raspberry Pi GPIO pin
- Frequency and mode per schedule, transmit time limit, emergency stop, test tone
- Icecast internet stream around the clock

**Unattended**
- Installers for Linux/macOS and Windows, background service with restart, clock check against a time server, `/api/health`, password with optional two-factor login

**Downloads**

| File | For |
|---|---|
| `etherdigits-windows-x64.zip` | Windows 10/11 |
| `etherdigits-macos-arm64.zip` | macOS on Apple silicon |
| `etherdigits-linux-x64.zip` | Linux on PCs (glibc 2.35+, needs `libportaudio2` for the sound card) |
| `etherdigits-linux-arm64.zip` | Raspberry Pi OS 64-bit and other ARM64 Linux |

Unzip and start `etherdigits` (Windows: `etherdigits.exe`); it opens the web interface. The files are not signed: Windows SmartScreen ("More info" → "Run anyway") and macOS Gatekeeper (right-click → Open) ask once.

Encrypted or obscured content is not allowed on amateur radio bands. Use the internet stream, a dummy load, local playback, or a service licensed for it.
