**License change:** from this version on, EtherDigits is licensed under the MIT License with an additional restriction: no military use, including armed forces and intelligence services. See [LICENSE](https://github.com/TechnikWeber/EtherDigits/blob/main/LICENSE) and [NOTICE.md](https://github.com/TechnikWeber/EtherDigits/blob/main/NOTICE.md). Version 0.5.0 and older stay under the plain MIT License.

**New**
- Check group: new pads add one group to every message, so the receiver sees whether the message was copied correctly. It can be checked with pencil and paper too. Pads from 0.5 keep working as before.
- Schedules: "every N minutes" can run inside a daily window (e.g. 18:00 to 19:00, also past midnight), and every schedule can use a time zone such as Europe/Berlin, which follows daylight saving time.
- The station's web interface offers the pad tool as a download (Messages tab).
- Quick start guide: [docs/quickstart.md](https://github.com/TechnikWeber/EtherDigits/blob/main/docs/quickstart.md).
- Windows: time zone data comes with the program (tzdata).

**Downloads**

| File | For |
|---|---|
| `etherdigits-windows-x64.zip` | Windows 10/11 |
| `etherdigits-macos-arm64.zip` | macOS on Apple silicon |
| `etherdigits-linux-x64.zip` | Linux on PCs (glibc 2.35+, needs `libportaudio2` for the sound card) |
| `etherdigits-linux-arm64.zip` | Raspberry Pi OS 64-bit and other ARM64 Linux |

Unzip and start `etherdigits` (Windows: `etherdigits.exe`); it opens the web interface. The files are not signed: Windows SmartScreen ("More info" → "Run anyway") and macOS Gatekeeper (right-click → Open) ask once.

The radio output has still not been tried with a real radio. Encrypted or obscured content is not allowed on amateur radio bands.
