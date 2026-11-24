# CHANGELOG


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
