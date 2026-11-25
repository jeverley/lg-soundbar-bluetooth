# CHANGELOG


## v0.5.1 (2026-11-25)

### Bug Fixes

- Report a link dropped as it opens, and refuse commands while not connected
  ([`aa0d714`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/aa0d714fe7741a696fc69fac1e6ad83227867b10))

- A link that drops as it opens raises HandshakeFailed (a CannotConnect), as during the start-up,
  instead of NotConnected. - Commands raise NotConnected unless the link is open, as before, instead
  of being dropped while it opens or closes. Links say is_connected. - disconnect() waits up to 5 s,
  longer than bluetooth-classic takes to close a link; if the close still hangs, the link is let go,
  so a later connect() opens a new one. - Needs bluetooth-classic 0.8.2, which retries while an old
  link closes.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt


## v0.5.0 (2026-11-25)

### Bug Fixes

- Open the link through bluetooth-classic 0.8, without serialx
  ([`ae0a3c1`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/ae0a3c156ed330228c7943fe9f079f6e9384eec3))

bluetooth-classic 0.8 opens RFCOMM links directly with open_rfcomm(), as the one aio-rfcomm owner in
  the process; the client's connector calls it again, and serialx is no longer a dependency.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt

### Features

- Connect through bluetooth-classic's RfcommClient
  ([`f394aae`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/f394aae56e3e21888adee23ac2e19bc99a97681c))

The client makes its link with a link factory (by default an RfcommClient for the Serial Port
  service) and connects it with establish_rfcomm_connection(), which retries while BlueZ says the
  soundbar is busy, as bleak-based libraries connect with bleak-retry-connector. Data arrives
  through the link's data callback from the first byte, and its end through the disconnected
  callback. Breaking changes now raise the minor version until 1.0.

BREAKING CHANGE: LGSoundbar's connector option is replaced by link_factory, which returns a link
  shaped like RfcommClient, and FakeSoundbar.connector by FakeSoundbar.link_factory
  (FakeSoundbar.transport is now FakeSoundbar.link). The client's own EBUSY retry is gone.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt

### Breaking Changes

- Lgsoundbar's connector option is replaced by link_factory, which returns a link shaped like
  RfcommClient, and FakeSoundbar.connector by FakeSoundbar.link_factory (FakeSoundbar.transport is
  now FakeSoundbar.link). The client's own EBUSY retry is gone.


## v0.4.3 (2026-11-25)

### Bug Fixes

- Open the link through serialx directly
  ([`a40d33d`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/a40d33d0118ca32d5111cb1aed668a078c784c9d))

The client's connector calls serialx.create_serial_connection() with bluetooth-classic's rfcomm://
  URL, as Home Assistant opens serial devices, instead of bluetooth-classic's open_rfcomm()
  shortcut. Once serialx has the rfcomm:// handler itself, only the import changes.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt


## v0.4.2 (2026-11-25)

### Bug Fixes

- Drop the RFCOMM channel, which links no longer report
  ([`8966ae7`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/8966ae76c404c4abd61fe0df2ab7621239f11bef))

bluetooth-classic 0.7 links do not say which RFCOMM channel they are on, so client.channel was
  always None: it is removed, and the client logs the service it opened instead. The protocol
  reference gives only the timing the soundbar tolerates, and the earliest move seen (0.12 s).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt


## v0.4.1 (2026-11-25)

### Bug Fixes

- Use bluetooth-classic 0.7, which opens links with aio-rfcomm
  ([`e757c3c`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/e757c3c89c471a8d9afdb2d8808b3df4cb03e9c0))

bluetooth-classic 0.7 opens RFCOMM links with aio-rfcomm; open_rfcomm() is unchanged, so the client
  needs no change. Links no longer report their channel, so client.channel stays None.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt

### Documentation

- Waking a G1 over Bluetooth needs Auto Power on
  ([`95b3a3d`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/95b3a3d7c693df4973b9d8edbb8730b88504e5a0))

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt


## v0.4.0 (2026-11-24)

### Documentation

- Record that an SDP lookup does not move a G1 to Bluetooth
  ([`8a91647`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/8a916471015f713571fe55361b3c19fe7ceca99f))

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt

### Features

- Connect through BlueZ's profile API, with no channel of our own
  ([`ac4c28a`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/ac4c28ab150ee834a96b8d440d4e5c96d7c0a6a5))

The connector opens the soundbar's Serial Port service with bluetooth-classic 0.6, where BlueZ makes
  the connection and finds the channel. The connector loses its channel argument, LGSoundbar its
  channel hint, and the "look up again if nothing answered" retry goes: a soundbar that does not
  answer is a failed connection. client.channel still reports the channel each connection used.

Link security is BlueZ's for client profiles; Security.MEDIUM is no longer asked for.
  BluetoothUnsupported and the rfcomm_supported re-export are removed, as no Bluetooth sockets of
  Python's own are needed. FakeSoundbar's connector follows.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt


## v0.3.0 (2026-11-24)

### Bug Fixes

- Only fall back from the stored channel when nothing answered on it
  ([`9324366`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/9324366dd801ec5ea5897d878af2018154e2ac6a))

- Look the service up again only when the stored channel accepted the connection but sent nothing; a
  soundbar that answered, or closed the link (switching off, not trusted), is not connected to
  again. - Keep the stored channel when the fallback fails before a lookup, and keep a looked-up
  channel even if its handshake fails. - Log the channel each connection opened, and whether it was
  the hint. - Note that busy retries without a channel look the service up again.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt

### Features

- Connect to the Serial Port service, with the last channel as a hint
  ([`4526e36`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/4526e36fdc37525c5735d1b570bd3628791ce9f8))

The connector opens the soundbar's Serial Port service through bluetooth-classic 0.5: the channel of
  the last connection is tried first, and the service is looked up in the soundbar's SDP records
  when there is none or the soundbar refuses it. The channel the link used is kept for next time. If
  something answers on the hinted channel but the handshake fails, the hint is dropped and the
  service is looked up once more.

channel_finder, probe_channels and PROBE_CHANNELS are removed: there is no more sdptool lookup or
  probing of likely channels. A failed lookup raises CannotConnect. FakeSoundbar's connector accepts
  no channel and uses its Serial Port channel (10, as on a G1), reporting it as the transport's
  rfcomm_channel.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt


## v0.2.1 (2026-11-24)

### Bug Fixes

- Report a link dropped while putting the input back, and connect once
  ([`85d7ad3`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/85d7ad373ab256699d691a1b72bb416edb7f6221))

- If the soundbar drops the connection while connect(keep_input=True) selects the input again, as
  when it is switched off, the restore is reported as not reached instead of NotConnected escaping
  connect(). - Overlapping connect() calls open one connection: a second call waits for the first. -
  A comment explains why the input's own code is used when the feature flags are still unknown, with
  tests for that and for a move that comes after the start-up.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt


## v0.2.0 (2026-11-24)

### Features

- Make sure the input is put back after connecting
  ([`497906c`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/497906c80950add4d943591ec90e3a31e2ef8983))

connect(keep_input=True) now also waits until the soundbar is on the input it was switched back to,
  selects it again if it is not (up to twice), and records how it went in the new input_restore: the
  input reported first, whether the connection moved it, the code sent, whether it got there, and
  how many more selections it took. Applications no longer need their own retry.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt


## v0.1.0 (2026-11-24)

### Documentation

- Show how to find and pair a soundbar
  ([`0f99736`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/0f9973651ddb8f909a3d8ddf8fb361c5fd7c62a9))

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt

### Features

- Control LG soundbars over Bluetooth
  ([`be7c621`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/be7c621bea25c41827c88a3aa96c06a47d65da4d))

Control LG soundbars such as the G1 over Bluetooth Classic: volume, mute, inputs and sound modes;
  the soundbar's settings, offered where its feature flags say it has them; speaker connections,
  firmware and model; turning the soundbar off, and switching back to the input it was on when a
  connection moved it to Bluetooth. The link comes from bluetooth-classic. A fake soundbar that
  answers like a G1 is included for tests.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>

Claude-Session: https://claude.ai/code/session_01CciW4UG1YNtAD3yvwo7sxt
