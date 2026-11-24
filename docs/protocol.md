# LG soundbar Bluetooth serial protocol

These notes describe the soundbar's Bluetooth functions and how LG's Sound
Bar app uses them, cross-checked against frames captured by
[websterwh/lg-s75qr](https://github.com/websterwh/lg-s75qr) and against an
LG G1. No LG code is included in this repository.

Values are hexadecimal unless stated otherwise. In the command tables, the
**Used here** column says whether this library uses a command: **yes**,
**no** (not yet), or **never** (left out on purpose, because it changes
firmware, resets settings or only serves LG's own diagnostics).

## Transport

- Bluetooth Classic Serial Port Profile, UUID `00001101-0000-1000-8000-00805f9b34fb`.
- The app looks the RFCOMM channel up with SDP rather than hard-coding it.
  An LG G1 uses channel 10; an LG US70TR uses channel 2.
  Here, unlike the app, the channel of the last connection is tried first,
  and the service is only looked up when there is none, when the soundbar
  refuses it, or when no soundbar answers on it: a lookup is itself a
  Bluetooth connection, which wakes a soundbar that is off (whether it also
  moves one that is on to Bluetooth is unconfirmed).
- There is no application-level authentication, encryption or session ID.
  Pairing is handled by the operating system.
- The host must **trust** the soundbar, as phones trust what they pair with.
  An LG G1 paired but not trusted by a Linux host accepts the RFCOMM
  connection, then resets it about 75 ms later, before answering anything.
- The app keeps the serial link open after the phone's audio (A2DP) link
  drops if the soundbar sets the `SPP_NOT_DISCONN` flag and is not on its
  Bluetooth input. This only affects when the app disconnects; it does not
  allow turning the soundbar on.

## Frames

```
41 54 | major | minor | length | payload... | checksum
```

`checksum = (-(length + sum(payload))) & 0xff`, so a frame with no payload has
a checksum of `00`. Received frames are found by searching for `41 54`; frames
with a bad checksum are dropped.

## Major byte

| Major | Meaning |
|---|---|
| `00` | General: handshake, inputs, power, feature lists |
| `06` | Usage statistics (LG's "ALAMP" logs) |
| `0c` | Firmware: read-only information and updates |
| `0d` | Utility: speaker levels and settings |
| anything else | An input's code, for commands that act on that input |

Commands that act on the current input (volume, mute, sound mode, night mode,
playback) use the current input's code as their major byte, so the current
input must be known first (`00/0b`). Replies use the same code.

### Input codes

| Code | Input | Code | Input |
|---|---|---|---|
| `07` | Bluetooth | `b0` | TV rear |
| `09` | LG TV (wireless sound sync) | `b1` | TV woofer |
| `10` | CD | `c0` | HDMI 1 |
| `40` | USB 1 | `c1` | HDMI 2 |
| `41` | USB 2 | `c2` | HDMI 3 |
| `50` | AUX | `c3` | HDMI ARC |
| `60` | Portable | `c4` | HDMI eARC |
| `81` | FM | `d0` | Optical 1 |
| `82` | AM | `d1` | Optical 2 |
| `83` | DAB | `df` | Optical/HDMI ARC |

## Connecting

The app's start-up sequence. Each
step marked *waits* is asked again every 3 seconds until answered, 3 times in
all, after which the app disconnects:

1. `00/15` (Android check), then 50 ms later `00/16` (emergency check),
   `00/17 1f` (firmware chip types the app supports) and `00/0b` (current
   input, *waits*). An LG G1 answers `00/16` (`00`) and `00/0b`, not the
   others.
2. On the current input's answer: `<input>/03` (current state, *waits*)
   and `00/19` (model type).
3. On the current state's answer: `00/04` (supported inputs, *waits*).
4. On the supported inputs' answer: connection states for the inputs
   listed, then `00/06` (feature list, *waits*).
5. On the feature list's answer: `00/08` (extended feature flags, *waits*)
   if it says the soundbar has them; else firmware chips if it supports
   updates; else start-up ends.
6. On the extended flags' answer: the settings whose flags are set, then
   firmware chips and details if it supports updates.

This library follows that order and waits as the app does, with two
differences: it asks for the current input first and alone, before the
opening messages, and it carries on without an answer rather than
disconnecting. In step 6 it asks for what the flags offer, as the app does,
with two differences: the subwoofer and rear speaker states are also asked
for with their level flags, and the sleep timer is asked for only from a
soundbar without feature flags. Until the flags are known (or if a
soundbar has none) it asks for everything. The connection states in step 4
are those of the current input, not each listed input.

Two answers change the start-up, in the app and here (neither is confirmed
on a real soundbar: an LG G1 has no MTK chip and is not in emergency mode):

- **MTK start-up state (`00/18`)**, sent by soundbars with an MTK chip.
  `00` means still starting up: the app ignores the start-up's answers and
  waits up to 20 seconds, then gives up on the connection. `01` means it
  has started up: the app runs the start-up again from step 1. This
  library does the same, asking for the current input again first, and
  gives up on connecting after 20 seconds without `01`.
- **Emergency check (`00/16`) answered `01`**: a failed firmware update has
  left the soundbar in emergency mode. The app stops its start-up, asks for
  the firmware chips (`0c/00`) and offers its recovery update. This
  library stops its start-up the same way, short of the update, and reports
  it in `state.emergency`, so an application can point to LG's app until
  the soundbar reports normal mode.

After each input change, the app asks for the new input's snapshot and
its connection state (see `<input>/3f`, `/52`, `/5b`, `/5f`, `/66`).

The soundbar sends `00/02` (watchdog) from time to time; the app answers with
`00/02`. The soundbar confirms most setters by sending the new state back and
may stay silent when a setter changes nothing. It also sends changes made
with its remote or buttons by itself.

## Recognising a soundbar

The LG app filters devices in two places:

- **Scan results:** the Bluetooth name starts with `LG ` or `LG-`. Nothing
  else is checked, because a scan only sees the few services a device
  advertises (an LG G1 advertises two audio services, not the serial port).
- **Paired devices:** the name starts with `LG ` or `LG-` and the device
  offers the serial port service, which is known once it has been paired.

An LG G1 is named `LG G1(XX)`, where `XX` varies. Renaming a soundbar in the
app does not use this protocol.

## Feature lists

### `00/06`: supported feature lists

| Byte | Meaning |
|---|---|
| 0 | Bit `04`: firmware information is available (`0c/00`). Bit `08`: the extended list (`00/08`) is available. |
| 1 | `01`: the app offers its sleep timer |
| 2 | `01`: the app shows its power off button (`00/0a`) |
| 3 | Repeat modes supported, as a mask of the repeat values below |
| 5 onwards | Per input, 4 bytes of feature bits, most significant first: play/pause (bit 12), file list (15), repeat (18), sound effect (20), portable shown as AUX (24) |
| 45 | FM tuning step: `64` (100 kHz) or `32` (50 kHz) |

The app only reads an answer of at least 65 bytes. An LG G1 answers with 105
bytes starting `0c 00 01 07 01`: extended list and firmware information
available, no sleep timer, power off offered.

### `00/08`: extended feature flags

The first 10 bytes are flags, each at a byte and bit. The LG app only offers a
setting when its flag is set.

| Flag | Byte, bit | Flag | Byte, bit |
|---|---|---|---|
| NFC direct play | 0, 0 | Rear level | 3, 7 |
| Beep sound | 0, 1 | Night time | 4, 7 |
| Progress volume display | 0, 2 | Surround | 5, 0 |
| Battery saving | 0, 3 | Smart diagnosis | 5, 5 |
| DRC | 0, 4 | Side level | 5, 6 |
| Bluetooth address support | 0, 6 | Center level | 5, 7 |
| Serial link survives audio drop | 0, 7 | LG XBOOM | 6, 1 |
| Tone control | 1, 0 | LG XBOOM Go | 6, 2 |
| Party mode | 1, 4 | Overhead level | 6, 5 |
| Lighting text | 1, 6 | Neural:X | 6, 6 |
| Night mode | 1, 7 | Dialog control | 6, 7 |
| Lighting effect | 2, 4 | Special EQ | 7, 0 |
| TV remote | 3, 0 | Auto power down | 7, 1 |
| AV sync | 3, 1 | Soundbar mode | 7, 4 |
| Woofer level | 3, 2 | Meridian EQ list | 7, 5 |
| Auto volume | 3, 3 | 2021 night mode | 7, 6 |
| Auto power | 3, 4 | Sound feedback | 8, 4 |
| Auto display | 3, 5 | New model type | 9, 1 |
| Optical/HDMI ARC combined | 3, 6 | Audio info | 9, 2 |
| IMAX | 9, 3 | Volume display | 9, 5 |
| New firmware info | 9, 6 | Extended list 2 (`00/24`) | 9, 7 |

An LG G1 sends `d4 81 00 df 80 a1 80 05 00 00`. That leaves out auto display,
overhead level, side level and Neural:X, yet it answers the auto display,
overhead level and Neural:X queries anyway (Neural:X with two bytes, `00 00`).

With the combined Optical/HDMI ARC flag, the app shows Optical (`d0`), HDMI
ARC (`c3`) and eARC (`c4`) as one "Optical/HDMI ARC" input and selects it with
`df`. An LG G1 reports its inputs as `07 09 40 c0 d0`; after `df` is selected
it reports `d0`, or `c4` while a TV is connected by eARC.

### `00/24`: extended feature flags 2

Asked for only when the "Extended list 2" flag is set (an LG G1 does not set
it). One byte per 8 flags:

| Flag | Byte, bit |
|---|---|
| Subwoofer state notifications | 0, 0 |
| Rear speaker state notifications | 0, 1 |
| Speaker mute sound check | 0, 2 |
| Built-in subwoofer image | 1, 2 |
| LED display | 1, 5 |
| Up-mixer | 3, 5 |
| WOW interface | 3, 6 |
| WOW Orchestra | 4, 2 |
| Rear left/right swap | 5, 0 |
| BLE MAC address | 5, 3 |
| ThinQ app support | 5, 4 |
| Usage statistics | 5, 5 |

## General commands (`00/xx`)

| Minor | Name | Send | Reply | Used here |
|---|---|---|---|---|
| `01` | Select input | input code | current input code | yes |
| `02` | Watchdog | none (answer the soundbar's) | | yes |
| `04` | Supported inputs | none | input codes | yes |
| `06` | Supported feature lists | none | see above | yes |
| `07` | Storage state | input code (USB) | input code, storage state | no |
| `08` | Extended feature flags | none | see above | yes |
| `0a` | Power | `00` turns off | | yes (off only; there is no power on) |
| `0b` | Current input | none | input code | yes |
| `15` | Android check | none | | yes (handshake) |
| `16` | Emergency check | none | `00` normal, `01` emergency (firmware recovery) mode | yes (handshake; `01` stops the start-up, see "Connecting") |
| `17` | Firmware chip types | mask of chip makers the app supports: `01` ESS, `02` MCS, `04` CSR, `08` MTK, `10` Realtek | | yes (handshake, `1f`) |
| `18` | MTK boot state | (sent by the soundbar) | `00` starting up, `01` started up, `ff` error | yes (see "Connecting"; unconfirmed) |
| `19` | Model type | none | model type (`20` for a G1: soundbar) | yes (read, unused) |
| `20` | Bluetooth address support | | | no |
| `23` | New model type | none | type, model ID (2 bytes), sub-type | yes (read, unused; asked only with the new model type flag, as by the app) |
| `24` | Extended feature flags 2 | none | see above | yes (asked only with the Extended list 2 flag, as by the app) |

## Input commands (`<input>/xx`)

These use the input's code as the major byte.

| Minor | Name | Send | Reply | Used here |
|---|---|---|---|---|
| `02` | Volume | maximum, volume (third byte: woofer volume on TV rear/woofer) | maximum, volume | yes |
| `03` | State snapshot | none | play state (`ff` none, `00` stop, `01` playing, `02` paused), flags (bit 0 muted), maximum volume, volume, 4 unknown bytes, repeat, shuffle, ... | yes (mute and volume) |
| `05` | Next track | none | | no (USB/CD) |
| `06` | Previous track | none | | no (USB/CD) |
| `0a` | Play | none, or file index (2 bytes) | | no (USB/CD) |
| `0b` | Pause | none | | no (USB/CD) |
| `0c` | Stop | none | | no (USB/CD) |
| `0f`, `10` | Start, end fast forward | none | | no (USB/CD) |
| `11`, `12` | Start, end rewind | none | | no (USB/CD) |
| `13` | Auto tuning | none | | no (radio) |
| `15` | Folder information | see folder information below | | no (USB) |
| `16` | Play time | | text (6 or more characters) | no (USB) |
| `17` | Track tag | | character set, text | no (USB) |
| `1d` | Mute | `01` on, `00` off | same | yes |
| `1f` | Sound mode and tone | see sound modes and tone control | | yes |
| `25` | Repeat | repeat value | same | no (USB) |
| `26` | Shuffle | `01` on, `00` off | same | no (USB) |
| `31` | Frequency | | | no (radio) |
| `32` | Preset | `00` number, `01` list | | no (radio) |
| `33` | Enter preset | | | no (radio) |
| `34` | Preset frequency | | | no (radio) |
| `35` | FM stereo mode | `00` stereo, `01` mono | | no (radio) |
| `36` | Store preset | none | `00` stored, `01` full, `02` failed | no (radio) |
| `37` | Clear all presets | none | | no (radio) |
| `38` | Select preset | preset number | | no (radio) |
| `3f` | LG optical connection | none | `01` connected, `00` not, `ff` not reported | read, unused |
| `40` | Delete preset | preset number | | no (radio) |
| `47` | Party mode (multi-pairing) | mode | same | no (party mode flag) |
| `49` | Lighting | `00` + effect index selects; `01` asks for text types; `02` for themes | | no (lighting flags) |
| `4a` | Night mode | `01` on, `00` off; none to query | same | yes |
| `50` | Radio text (RDS) | | | no (radio) |
| `52` | LG TV connection | none | as `3f` | read, unused |
| `5b` | TV rear/woofer connection | none | as `3f` | no |
| `5f` | Optical connection | none | as `3f` | read, unused |
| `66` | HDMI ARC connection | none | as `3f` | read, unused |
| `72` | Audio information | none | text, such as the stream's format | yes (audio info flag; a G1 lacks it) |
| `80` | Swap rear left and right | `01` swapped, `00` normal | same | no (needs `00/24`) |

The connection queries (`3f`, `52`, `5f`, `66`) are sent on each input, as the
LG app does, but this library shows none of them. The app only uses one:
on the Optical input, the LG optical state (`3f`) picks whether the input is
shown as an LG TV link ("LGOPT" on the soundbar) or plain Optical. It stores
the others but shows none. There is no eARC query: on E-ARC an LG G1 answers
the HDMI ARC query, with the reply labelled `c3` (ARC), and says not
connected, as plain ARC is not in use. An LG G1 answered every one of these
queries with `00`.

## Utility commands (`0d/xx`)

Settings are queried by sending them with no payload. Levels answer with
value, minimum, maximum; the app ignores level replies without a range.

| Minor | Name | Send | Reply | Used here |
|---|---|---|---|---|
| `09` | DRC | `01`/`00` | same | yes |
| `14` | Sleep timer | `01`, minutes; `00 00` off | on, minutes left (`01` = one minute left); a G1 does not answer | yes (set, and read from its reports; offered and not asked, as by the app, when the feature list says so) |
| `19` | TV remote | `01`/`00` | same | yes |
| `1a` | AV sync | value in 10 ms steps (unsigned) | value, minimum, maximum | yes |
| `1b` | Woofer level | value (signed) | value, minimum, maximum | yes |
| `1c` | Auto volume | `01`/`00` | same | yes |
| `1d` | Auto power | `01`/`00` | same | yes |
| `1e` | Auto display | `01`/`00` | same | yes |
| `1f` | Initialise settings | which settings to reset | | never |
| `21` | Rear level | value (signed) | value, minimum, maximum | yes |
| `22` | Surround (rear output) | `01`/`00` | same | yes |
| `24` | Smart diagnosis | sub-command, see below | | never |
| `25` | Subwoofer state | none | `01` connected, `00` not, `ff` not reported; a G1 answers | yes (asked with the `00/24` flag, as by the app, or with the woofer level flag: a G1 has no `00/24` but answers; that the level flag means a separate subwoofer, not a built-in one, is unconfirmed) |
| `26` | Center level | value (signed) | value, minimum, maximum | yes |
| `27` | Side level | value (signed) | value, minimum, maximum | yes |
| `29` | Overhead level | value (signed) | value, minimum, maximum | yes |
| `2a` | Neural:X | `01`/`00` | same (a G1 answers `00 00`) | yes |
| `2b` | Dialog control | value | value, minimum, maximum | yes |
| `2c` | Special EQ | none | special EQ value, see below | yes |
| `2d` | Auto power down | `01`/`00` | same | no (flag) |
| `2e` | Disconnect audio (A2DP) | none | | no (the app sends it, then connects to the soundbar it is switching to 300 ms later) |
| `2f` | Soundbar mode | | | no (flag) |
| `30` | Meridian EQ list | | | no (flag) |
| `38` | Sound feedback (beep) | `01`/`00` | same | no (flag) |
| `43` | Rear speaker state | none | state, then bit 0 left and bit 1 right connected; a G1 does not answer, even with rear speakers | yes (asked with the `00/24` flag, as by the app, or with the rear level flag) |
| `44` | Speaker mute for sound check | mask: `00` none, `01` main, `02` subwoofer, `08` rear left, `10` rear right | | never |
| `49` | LED display | value | same | no (needs `00/24`) |
| `57` | Up-mixer | | | no (needs `00/24`) |
| `58` | WOW Orchestra | | | no (needs `00/24`) |
| `59` | MAC address | | | no |

## Firmware commands (`0c/xx`)

The read-only queries are part of the app's normal start-up. The update
commands rewrite the soundbar's firmware.

| Minor | Name | Send | Reply | Used here |
|---|---|---|---|---|
| `00` | Firmware chips | none | `xx`, chip mask, flag | yes |
| `01` | Firmware details | chip, `07` (all fields) | see below | yes |
| `02` | Firmware update | step (`02` ready to transfer, with file details), see below | | never |
| `03` | Cancel update | | | never |
| `04` | Update complete | | | never |
| `05` | Firmware data | | | never |
| `06` | Firmware data packet | | buffer size (2 bytes) | never |
| `07` | Firmware chips (new) | none | `xx`, flag, chip numbers | yes (asked in place of `00` with the new firmware info flag, as by the app; the chips are then named by the type text in their details; unconfirmed on a real soundbar) |

Chip mask bits: 0 PEQ, 1 touch, 2 DSP, 3 sub, 4 DJ sound, 5 MICOM, 7 MAIN.
Bit 6 is a mode flag, not a chip. The chip number is the bit position.

`0c/01` replies with fields at fixed offsets, each a length byte followed by
text: product number at 3, product name at 19, model at 35, firmware type at
51, image version at 67, country at 83. Byte 2 is the character set and byte
99 whether an update can be completed. An LG G1 reports MICOM `M2103110` and
MAIN `B210414A`, with model `G1`. This library shows the image versions as
the device's firmware and the model as the device's model, falling back to the
model in the Bluetooth name (`LG G1(XX)`) until a soundbar has reported one.

Update steps: `00` CDN download start, `01` CDN download end, `02` ready to
transfer, `03` transfer complete, `04` flashing check. Failure reasons: `00`
resend current file, `01` failed, `02` battery low.

## Usage statistics (`06/xx`)

| Minor | Name | Used here |
|---|---|---|
| `00` | Used time per feature (audio format, auto volume, DRC, EQ, input, Neural:X, night time, smart up-mix, WOW Orchestra) | never |
| `01` | Button press counts | never |
| `02` | Extra information | never |

Asked for only when the soundbar sets the usage statistics flag in `00/24`.

## Sound modes and tone control (`<input>/1f`)

The first payload byte says what follows:

| First byte | Meaning | Rest of the payload |
|---|---|---|
| `00` | Current sound mode | mode; send to select one |
| `01` | Tone, three bands | bass, middle, treble (signed); send to set all three |
| `02` | Supported sound modes | 8-byte big-endian bitmap, bit n = nth mode in the full list |
| `03` | Tone, two bands | bass, treble (signed); send to set both |
| `04` | Tone ranges | bass min, bass max, middle min, middle max, treble min, treble max |
| `05` | Supported sound modes | mode values |

With the tone control flag, the app offers bass and treble, and a middle band
when the soundbar reports three bands (hidden on models with "q" in their
name). It uses the reported ranges, or -5 to 5 when none are sent. An LG G1
reports `03 00 00` (two bands, both 0) and no range.

| Value | Mode | Value | Mode |
|---|---|---|---|
| `02` | Standard | `53` | Night |
| `1e` | Flat | `54` | Game |
| `1f` | Boost | `55` | Cinema |
| `20` | Treble and Bass | `76` | Bass |
| `37`, `51` | Bass Blast | `81`, `82` | ASC |
| `38` | Music | `83` | DTS Virtual:X |
| `39` | Voice | `86` | Bass Blast+ |
| `52` | Clear Voice | `89` | Movie |
| `90` | AI Sound Pro | `92` | Sports |
| `97` | Clear Voice Pro | | |

The full list, in bitmap order, is `SOUND_MODES` in
`src/lg_soundbar_bluetooth/const.py`. An LG G1
offers Standard, Bass Blast, Music, Movie and AI Sound Pro.

## Special EQ (`0d/2c`)

A special sound mode the soundbar switched to, which overrides the chosen
sound mode. It is not the incoming audio format (that is `<input>/72`).

| Value | Meaning |
|---|---|
| `00` | Off: the chosen sound mode applies |
| `01` | Dolby Atmos |
| `02` | DTS:X |
| `03` | TV sound mode share ("Synced with TV"): an LG TV controls the sound mode |

While one is active, the app:

- shows it as the sound effect instead of the chosen sound mode;
- does not allow choosing a sound mode;
- locks auto volume during Dolby Atmos and DTS:X;
- locks night mode during Dolby Atmos and DTS:X, unless the soundbar sets
  the 2021 night mode flag;
- enables dialog control only during DTS:X;
- locks the center, rear and side levels during TV sound mode share.

The G1's manual agrees: "When this product detects Dolby Atmos® or DTS:X®
stream, you cannot change sound effect to any other", and the soundbar shows
"NOT SUPPORTED" if you try.

## Connecting, waking and scanning

What an LG G1 (with Auto Power on and BT LOCK off) does, as tested:

- **Connecting wakes it.** Any Bluetooth connection wakes it from off, even a
  bare `l2ping`; it then starts on Bluetooth, whatever input it was on.
- **Connecting moves it to Bluetooth.** If it is on another input, it first
  answers `00/0b` with that input, then reports Bluetooth about 0.1 to 0.3
  seconds later. LG's app connecting does the same. Selecting the input
  again works, but a G1 ignores `00/01 c4` (its eARC code), whether sent at
  once or a second after the move, and takes `00/01 df` (Optical/HDMI ARC,
  as the app selects it), after which it reports `d0` and, with the TV on,
  `c4` about a second later. Sometimes it moves before answering `00/0b`,
  and then reports Bluetooth first: the input it was on is not known. The feature
  flags (`00/08`), which say whether Optical, ARC and eARC are one input,
  arrive about 0.15 seconds after the move.
- **It only says what it was on if asked first.** Before the move it
  answers `00/0b` with the input it was on; after it, it reports only
  Bluetooth, and its own reports, unasked, have only ever said Bluetooth.
  The LG app asks for the input last in its start-up sequence; this
  library asks first and alone, the moment the connection opens (from a
  worker thread, so a busy event loop cannot delay it), and sends
  nothing else until it is answered; then it follows the app's start-up
  order (see "Connecting" above). Leaving out the app's opening messages
  (`00/15` to `00/17`) did not stop the move; they are sent after the input
  is answered. The diagnostics record when each step happened.
- **Asked alone, the input is always reported before the move.** In 12
  connections (eARC, USB, LG TV, HDMI) it came 0.02 to 0.1 seconds after the
  connection opened, the feature flags by 0.2 seconds, and the move 0.2 to
  0.7 seconds after opening.
- **Following the LG app's start-up order, the feature flags come late**:
  0.3 to 0.6 seconds after opening (2.4 when Home Assistant was busy),
  often after the move. So this library keeps the flags from the last
  connection and uses them to switch back from Bluetooth to Optical/HDMI
  ARC without waiting; this connection's flags replace them when they
  arrive.
- **After switching back to HDMI, it moves itself to eARC about a second
  later**, with a TV on eARC and nothing on its HDMI input. Selecting HDMI
  again a few seconds later sticks. Going from Bluetooth to HDMI with the
  remote does not do this. Unconfirmed why; possibly HDMI-CEC with the TV.
  So while connecting, if it leaves the input it was switched back to, this
  library selects it once more (Optical, ARC and eARC count as one).
  After the start-up, `connect(keep_input=True)` also waits for the
  soundbar to reach the input and selects it again if it has not (up to
  twice), reporting how it went in `input_restore`.
  To review: the start-up re-select only shortens the time on eARC (about 1
  second instead of a few with the check after it), and has only been
  seen with nothing on the HDMI input; drop it if it is not worth keeping.
- **Switching back before the move rarely stops it.** Selecting the input
  as soon as it was reported (Optical/HDMI ARC once the flags were known,
  about 0.1 seconds after opening) stopped the move in 1 of 4 connections;
  in the others it moved anyway and was switched back again. Not used.
- **It still sometimes moves before answering**, when Home Assistant is
  busy (at a restart, or reloading): it then reports Bluetooth twice, its
  own report of the move and then its answer, and the input it was on is
  not known. The diagnostics note this and how long opening the connection
  took. (That it reports Bluetooth only once when on Bluetooth throughout is
  unconfirmed.)
- **No audio profile connects with the serial port.** After a connection,
  BlueZ showed the link and the remote control profile (AVRCP) as known but
  not connected, and no audio stream (A2DP), so the move to Bluetooth comes
  from the serial port connection or what is sent on it.
- **The newest controller wins.** A second control connection takes over:
  the soundbar drops the older one (Home Assistant connecting kicked LG's app
  off). The app may then take it back by reconnecting.
- **It resets the connection (`ECONNRESET`) as it switches off.**
- **It is discoverable whenever it is on**, on any input and whatever is
  connected (LG's app, phone audio, Home Assistant), and never while off. It
  answers a Classic scan (inquiry) within about 4 seconds, and scanning does
  not wake it. A scan cannot tell whether something else is connected.
- **The TV switches it to E-ARC** when the TV turns on, reporting each input
  in turn on the way. A switch away from Bluetooth made over the connection
  holds with the TV off.
- **With BT LOCK on**, it does not answer at all while off (`connect` fails
  with "Host is down"), and may refuse connections on inputs other than BT
  and LG TV.

An application can therefore tell whether the soundbar is on with a
5-second scan (for example `bluetooth-classic`'s
`find_device_by_address()`), connect only when needed, and not reconnect
after a connection drops. With `keep_input`, this library switches back to
the input reported first if a connection moved it to Bluetooth.

There is no power on command, and the app does not offer one: it hides its
power button while a Bluetooth soundbar is not connected and suggests
checking that it is nearby and plugged in; it only offers turning on to
Wi-Fi models in network standby. "Bluetooth standby mode" and "Bluetooth
connection restriction" (BT LOCK) are Wi-Fi model settings in the app; on a
G1, BT LOCK is set with the remote.

## What an LG G1's manual adds

- No sleep timer is mentioned, matching the G1 not answering `0d/14`.
- Rear speakers are an optional kit (SPK8-S).
- Ranges: subwoofer −15 to 6, center −6 to 6, rear −6 to 6, bass and treble
  −5 to 5, matching what a G1 reports; volume 0 to 40 on the display,
  though a G1 reports a volume maximum of 100 over Bluetooth.
- Settings on the remote: surround, TV remote, Auto Power and BT LOCK (which
  limits Bluetooth connections to the BT and LG TV inputs; no app command for
  it has been found). Night time, DRC, auto volume, dialog control, AV sync
  and Neural:X are only in the app.
- The Information button shows the audio format on OPT, ARC, E-ARC and HDMI
  only, so the audio information query may only be answered on those inputs.

## Other values

| Values | Meaning |
|---|---|
| Repeat | `00` off, `01` one, `02` folder, `04` all |
| Storage state | `00` unmounted, `01` error, `02` ready, `03` reading, `04` reading done, `05` data changed, `06` deleted |
| Folder information sub-commands | `00` folder count, `01` file count, `02` folder name, `03` file name, `07` file names in current folder (start and count, 2 bytes each), `08` current file (folder and file index, 2 bytes each), `0f` cancel |
| Smart diagnosis sub-commands | `00` run (`00` initialise sound check), `01` supported items, `02` initial info, `03` amplifier check, `04` current volume, `05` audio link state |
| Sleep timer choices in the app | 10, 20, 30, 40, 50, 60, 70, 80, 90, 120, 150, 180 minutes |
