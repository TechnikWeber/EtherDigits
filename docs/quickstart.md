# Quick start

From nothing to a secret message on the air in about fifteen minutes.

## The idea in one picture

```
  SENDER                         STATION                         RECEIVER
  (a computer without            (runs EtherDigits               (radio or stream,
   network, pad tool)             around the clock)               pencil, same pad)

  "Meet tomorrow 18:30"
        │  pad tool + pad page
        ▼
  12651 06840 50631 ...  ──────►  queue ──► schedule ──► voice ──►  "one two six five one ..."
                         typed in,                                       │ writes the groups down
                         or sent with                                    ▼
                         an API token                              pad tool + same pad page
                                                                         │
                                                                         ▼
                                                                   "MEET TOMORROW 18:30"
```

- The **pad** is a list of random digit pages. Sender and receiver have the same
  copy, and nobody else does. Each page is used for exactly one message.
- The **pad tool** turns text into digit groups with one page, and back again
  with the same page. It runs offline in a browser.
- The **station** knows nothing about the pad. It only receives digit groups and
  reads them out at fixed times, in the voice and format you choose. When there
  is nothing to say, it reads random groups, so listeners cannot tell.

## 1. Install

Linux or macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/TechnikWeber/EtherDigits/main/install.sh | bash
```

Windows: run `install.ps1` as shown in the [README](../README.md#install), or
download the program from the [releases](https://github.com/TechnikWeber/EtherDigits/releases)
and double-click it.

Open <http://127.0.0.1:8472/>. The station is running, but it has no radio
output yet: it plays nothing out loud, it only keeps time and records.

## 2. Hear what the station sounds like

1. Go to **Schedules**. There is an example schedule, *Station 472*, switched off.
2. Click **Listen**. After a moment you hear a transmission: a short tune,
   "Achtung 4 7 2", the number of groups, random groups, the repeat, "Ende".
3. Click **Edit** to change the voice (Kerstin, Thorsten, LJ), the sound
   (clean or shortwave), the callsign, the times, and under *Transmission
   layout* how often everything is repeated. **Listen** inside the editor plays
   your changes before you save them.
4. Tick **Active** and save. The overview now shows the next transmissions.

Want to hear every real transmission on this computer? **Settings → Output and
radio → Monitor on the station computer**, pick your speakers, save. Switch it
off again when it gets on your nerves; the level meter in the header still
shows when the station is on air and how loud.

## 3. Make a pad

1. In **Messages**, click **download pad_tool.html**. Copy the file to the
   computer where you write messages, ideally one without network, and open it
   in a browser.
2. In the pad tool, tab **Pad**: give it a name, leave 20 pages of 50 groups,
   choose the language, and click **Create pad**.
3. Click **Save pad**. That file is the key. Keep it safe.
4. Give the receiver an identical copy: the file on a USB stick, or
   **Print pad** and hand over the paper. In person, never by e-mail or chat.

## 4. Encrypt a message

1. Pad tool, tab **Encrypt**. Type the message, e.g. *Treffen morgen 18:30 Uhr
   am Bahnhof*. Below it you see how many groups it needs and whether it fits
   on a page.
2. Click **Encrypt**. You get the digit groups; the first one (highlighted) is
   the page number.
3. Click **Save pad** again, so the file remembers that this page is used up.
4. Click **Copy**.

## 5. Hand it to the station

1. Station, tab **Messages**. Paste the groups.
2. Choose how urgent it is, in how many transmissions it should go out, and
   when it expires. Leave *Delete the digits after the last transmission* on.
3. Click **Add to queue**.

At its next slot the station reads your message instead of random groups. The
**Log** shows each transmission with its transcript and a recording.

From somewhere else? Create an **API token** under Settings and send the groups
with one HTTP request; see the [README](../README.md#the-station).

## 6. Receive and decrypt

The receiver listens on the frequency or the stream at the announced time and
writes the groups down. The tab **Practice** is for training exactly that.

Then, in the pad tool with the same pad: tab **Decrypt**, type the groups (page
number first), **Decrypt**. Without a computer, the printed checkerboard card
and the pad page are enough: subtract the page digit by digit without borrowing
(2 − 5 = 7), then read the digits off the checkerboard.

## 7. Going on air

Pick one:

| Way | What you need | Where |
|---|---|---|
| Internet stream | an Icecast server (your own, or hosted) and ffmpeg | Settings → Internet stream |
| Radio | a sound card into the radio, and PTT by VOX, a serial interface such as a Digirig, CAT or a Raspberry Pi GPIO pin | Settings → Output and radio |
| Files | nothing | `etherdigits render ... -o file.mp3`, or the recordings in the log |

With a radio: set **Output** to your radio's sound card, choose the PTT, save,
and press **Test tone** to set the level on the radio. **Emergency stop** on the
overview cuts any transmission at once and locks the transmitter until you
release it.

Encrypted or obscured content is not allowed on amateur radio bands. Use the
stream, a dummy load, local playback, or a service licensed for it.

## The rules that keep it secret

1. **Never use a page twice.** The tool refuses, but only if you save the pad
   after every message.
2. **Only two copies of the pad.** Hand them over in person.
3. **Destroy a page after use**, on paper and in your head.
4. **Keep the pad away from the station.** The station only needs digit groups.
5. **Let the filler run.** A station that only speaks when there is news gives
   its traffic away. The *Discreet log* setting also keeps the log from telling
   real messages and filler apart.

## When something does not work

| Problem | Fix |
|---|---|
| Forgot the password | on the station run `etherdigits password`; it sets a new one without asking for the old |
| Lost the authenticator app | on the station run `etherdigits totp-off` |
| "sound output needs the sounddevice package and PortAudio" | Linux: `sudo apt install libportaudio2` or `sudo dnf install portaudio` |
| Nothing happens at the scheduled time | is the schedule **Active**? Is the transmitter locked by an emergency stop? Look in the **Log** |
| The clock warning appears | the system clock is off; the station already follows the time server, but set the system clock right |
| Stream says it cannot connect | check server, port, mount point and source password; ffmpeg must be installed |
