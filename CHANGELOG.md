# CHANGELOG


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
