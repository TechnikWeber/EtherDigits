EtherDigits 0.7.2 adds packaged programs for more computers. The program itself is unchanged since 0.7.1.

**New downloads**
- **Windows on ARM** (Snapdragon laptops): `etherdigits-windows-arm64.zip`, a native ARM64 program.
- **Intel Macs**: `etherdigits-macos-x64.zip`, next to the Apple silicon build.
- **`SHA256SUMS`** lists the checksum of every file: `sha256sum -c SHA256SUMS --ignore-missing`.

All downloads: Windows x64 and ARM64, macOS Apple silicon and Intel, Linux x64, Raspberry Pi / Linux ARM64 (64-bit). A 32-bit Raspberry Pi OS uses the installer from the README.

**Upgrade**
- Stop the running station and replace the application with this version, keeping your existing data folder. Nothing else changes.

**Validation**
- The release workflow runs the automated tests and smoke-tests the packaged program (version, voices, a rendered transmission) on every one of the six platforms before publishing.

This remains a pre-release. Physical radio output has not yet been tested with hardware. The license is unchanged; see LICENSE and NOTICE.md.
