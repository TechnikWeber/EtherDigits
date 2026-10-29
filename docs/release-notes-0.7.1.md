EtherDigits 0.7.1 fixes Kerstin's German pronunciation and stale voice clips in schedule previews.

**Fixed**
- Rebuilt all Kerstin clips with sentence context. The previous isolated-word generation collapsed phoneme durations and produced unintelligible digits. Words are now extracted using the model's phoneme boundaries; the surrounding sentence is not included in the clips.
- Saved schedule previews and transmissions load the current voice pack for each render. A running station no longer keeps old recordings indefinitely under language aliases such as `de` or voice IDs such as `de-kerstin`.
- Voice-pack generation rejects invalid alignments and collapsed durations, and records the model checksum and generation settings for reproducibility.

**Upgrade**
- Stop the running station and replace the application with this version, keeping your existing data folder. No additional database migration is needed for this patch.
- Reload the browser and click **Listen / Probe anhören** again. Audio already loaded in a player remains the old recording until a new preview is generated.
- Piper and the alignment tools are only needed to rebuild voice packs. The downloads contain the corrected WAV files and need no additional speech model or internet connection for playback.

**Validation**
- 178 automated tests passed locally, including replacement of a same-sized WAV after warming saved previews under both a language alias and a voice ID.
- The actual saved-schedule API response and browser player audio were compared byte for byte with a fresh render from the corrected Kerstin pack.
- Independent local speech recognition recovered all ten digits and six announcement words in the corrected reference sequence. Recognition is an additional check, not a guarantee of perfect intelligibility in every listening condition.
- The release workflow tests and smoke-tests the packaged program on Windows x64, macOS ARM64, Linux x64 and Linux ARM64.

This remains a pre-release. Physical radio output has not yet been tested with hardware. The license is unchanged; see LICENSE and NOTICE.md.

**Downloads**

| File | For |
|---|---|
| `etherdigits-windows-x64.zip` | Windows 10/11 |
| `etherdigits-macos-arm64.zip` | macOS on Apple silicon |
| `etherdigits-linux-x64.zip` | Linux PCs (glibc 2.35+, PortAudio needed for sound card output) |
| `etherdigits-linux-arm64.zip` | Raspberry Pi OS 64-bit and other ARM64 Linux |

Unzip and start `etherdigits` (`etherdigits.exe` on Windows). The packaged programs are unsigned.
