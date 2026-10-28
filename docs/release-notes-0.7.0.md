EtherDigits 0.7.0 adds agents with their own listening schedules and fixes three delivery problems found during review.

**New**
- Agents tab: create, rename and delete recipients. Each agent can have several schedules with their own fixed times or windows, weekdays, time zone, transmission interval, voice, callsign, radio frequency and mode.
- Messages: select one or several agents. Each recipient gets an independent queue entry and transmission count. A message for one agent never goes out on another agent's schedule.
- Example: Agent A receives every 15 minutes from 13:00–14:00, Agent B every 30 minutes from 18:00–19:00. Both windows can use Europe/Berlin or another time zone.
- API: `agent_id` or `agent_ids` on message submission, and authenticated `/api/agents` management. Existing single-message API responses remain compatible.
- Warnings for identical schedule start times in the next eight days, shown under Agents and Schedules.

**Fixed**
- Message IDs are never reused after deletion. Deleting an agent and their message during a running transmission can no longer cause a new, unsent message to be marked as sent or burned. Late completion also preserves cancelled and expired states.
- At identical slots, real messages take precedence over filler; equally ready schedules take turns according to the last successful transmission, including after restart. A second agent no longer loses every shared slot to the first agent's filler.
- Invalid transmission counts, priorities, recipient selections and dates are rejected before encryption consumes a pad page. Encrypted groups are validated before the updated pad is saved.
- Schedule forms accept the default 0.18-second digit pause and freely chosen fractional frequencies.
- Planning ahead no longer expires other messages before their actual deadline.

**Upgrade and operation**
- Existing databases are upgraded automatically, preserving schedules, message IDs and queue contents. Back up the data folder before upgrading; stop older station processes before starting this version.
- One transmitter still handles only one schedule at a time. A conflicting slot is logged as busy and its messages remain queued. Use separate start times with enough space for each transmission; the warning detects equal starts, not duration overlaps.
- Identical encrypted groups require the matching pad at every recipient. For separate pads, encrypt and submit separately for each agent.
- Frequency changes require CAT enabled under Settings.
- This remains a pre-release. Real-radio output has not yet been tested with physical hardware.

**Validation**
- 173 automated tests pass locally. Browser checks cover the complete agent/message flow, conflict warnings, German/English text and mobile layout.
- Regression tests cover delivery during deletion, database migration, slot fairness across restart, conflict detection, per-agent routing, atomic multi-recipient submission and pad preservation after invalid inputs.
- The release workflow runs the test suite and JavaScript syntax check on every target platform before packaging.

**Downloads**

| File | For |
|---|---|
| `etherdigits-windows-x64.zip` | Windows 10/11 |
| `etherdigits-macos-arm64.zip` | macOS on Apple silicon |
| `etherdigits-linux-x64.zip` | Linux PCs (glibc 2.35+, PortAudio needed for sound card output) |
| `etherdigits-linux-arm64.zip` | Raspberry Pi OS 64-bit and other ARM64 Linux |

Unzip and start `etherdigits` (`etherdigits.exe` on Windows). The packaged programs are unsigned. The license remains MIT with the additional restriction of no military use; see LICENSE and NOTICE.md.
