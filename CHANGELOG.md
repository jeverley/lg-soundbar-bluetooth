# CHANGELOG


## v0.6.0 (2026-11-25)

### Features

- Open the link as bluetooth-classic 0.9's RfcommConnection
  ([`7eb8537`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/7eb853772763295014bfbe2ec936389613397919))

### Breaking Changes

- A link factory now returns a link shaped like RfcommConnection: open(write_on_open=), close(),
  is_open, opened_at, close_reason, and a closed_callback in place of disconnected_callback.
  FakeLink follows; its own way of ending the link from the soundbar's side is now drop().
  LGSoundbar's connect() and disconnect() are unchanged.


## v0.5.1 (2026-11-25)

### Bug Fixes

- Report a link dropped as it opens, and refuse commands while not connected
  ([`aa0d714`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/aa0d714fe7741a696fc69fac1e6ad83227867b10))


## v0.5.0 (2026-11-25)

### Bug Fixes

- Open the link through bluetooth-classic 0.8, without serialx
  ([`ae0a3c1`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/ae0a3c156ed330228c7943fe9f079f6e9384eec3))

### Features

- Connect through bluetooth-classic's RfcommClient
  ([`f394aae`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/f394aae56e3e21888adee23ac2e19bc99a97681c))

### Breaking Changes

- LGSoundbar's connector option is replaced by link_factory, which returns a link shaped like
  RfcommClient, and FakeSoundbar.connector by FakeSoundbar.link_factory (FakeSoundbar.transport is
  now FakeSoundbar.link). The client's own EBUSY retry is gone.


## v0.4.3 (2026-11-25)

### Bug Fixes

- Open the link through serialx directly
  ([`a40d33d`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/a40d33d0118ca32d5111cb1aed668a078c784c9d))


## v0.4.2 (2026-11-25)

### Bug Fixes

- Drop the RFCOMM channel, which links no longer report
  ([`8966ae7`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/8966ae76c404c4abd61fe0df2ab7621239f11bef))


## v0.4.1 (2026-11-25)

### Bug Fixes

- Use bluetooth-classic 0.7, which opens links with aio-rfcomm
  ([`e757c3c`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/e757c3c89c471a8d9afdb2d8808b3df4cb03e9c0))


## v0.4.0 (2026-11-24)

### Features

- Connect through BlueZ's profile API, with no channel of our own
  ([`ac4c28a`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/ac4c28ab150ee834a96b8d440d4e5c96d7c0a6a5))


## v0.3.0 (2026-11-24)

### Bug Fixes

- Only fall back from the stored channel when nothing answered on it
  ([`9324366`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/9324366dd801ec5ea5897d878af2018154e2ac6a))

### Features

- Connect to the Serial Port service, with the last channel as a hint
  ([`4526e36`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/4526e36fdc37525c5735d1b570bd3628791ce9f8))


## v0.2.1 (2026-11-24)

### Bug Fixes

- Report a link dropped while putting the input back, and connect once
  ([`85d7ad3`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/85d7ad373ab256699d691a1b72bb416edb7f6221))


## v0.2.0 (2026-11-24)

### Features

- Make sure the input is put back after connecting
  ([`497906c`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/497906c80950add4d943591ec90e3a31e2ef8983))


## v0.1.0 (2026-11-24)

### Features

- Control LG soundbars over Bluetooth
  ([`be7c621`](https://github.com/jeverley/lg-soundbar-bluetooth/commit/be7c621bea25c41827c88a3aa96c06a47d65da4d))
