# LG Soundbar Bluetooth

<p align="center">
  <a href="https://github.com/jeverley/lg-soundbar-bluetooth/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/jeverley/lg-soundbar-bluetooth/ci.yml?branch=main&label=CI&logo=github&style=flat-square" alt="CI Status" >
  </a>
  <a href="https://lg-soundbar-bluetooth.readthedocs.io">
    <img src="https://img.shields.io/readthedocs/lg-soundbar-bluetooth.svg?logo=read-the-docs&logoColor=fff&style=flat-square" alt="Documentation Status">
  </a>
  <a href="https://codecov.io/gh/jeverley/lg-soundbar-bluetooth">
    <img src="https://img.shields.io/codecov/c/github/jeverley/lg-soundbar-bluetooth.svg?logo=codecov&logoColor=fff&style=flat-square" alt="Test coverage percentage">
  </a>
</p>
<p align="center">
  <a href="https://python-poetry.org/">
    <img src="https://img.shields.io/badge/packaging-poetry-299bd7?style=flat-square" alt="Poetry">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/badge/code%20style-ruff-000000.svg?style=flat-square" alt="ruff">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat-square" alt="pre-commit">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/lg-soundbar-bluetooth/">
    <img src="https://img.shields.io/pypi/v/lg-soundbar-bluetooth.svg?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/lg-soundbar-bluetooth.svg?style=flat-square&logo=python&amp;logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/lg-soundbar-bluetooth.svg?style=flat-square" alt="License">
</p>

<!-- docs-start -->

Control LG soundbars over Bluetooth.

LG soundbars such as the G1 have no network connection, but they can be
controlled over Bluetooth Classic, through a serial link (RFCOMM, the Serial
Port Profile). This library speaks the soundbar's Bluetooth serial protocol,
in your own asyncio event loop:

- volume, mute, inputs and sound modes;
- the soundbar's settings (levels, dynamic range control, night mode,
  auto power and more), offered where its feature flags say it has them;
- the subwoofer and rear speakers' connection, firmware versions and the
  model;
- turning the soundbar off, and switching back to the input it was on when
  a connection moved it to Bluetooth.

The Bluetooth link comes from
[bluetooth-classic](https://github.com/jeverley/bluetooth-classic), which
opens it with [aio-rfcomm](https://github.com/dlech/aio-rfcomm). For LG soundbars
with Wi-Fi, see [temescal](https://github.com/google/python-temescal). The
protocol is documented in [docs/protocol.md](https://github.com/jeverley/lg-soundbar-bluetooth/blob/main/docs/protocol.md).

## Installation

Install this via pip (or your favourite package manager):

`pip install lg-soundbar-bluetooth`

It needs Linux with Bluetooth sockets in Python (as Home Assistant's Python
has), and Python 3.12 or newer. The soundbar must be paired first; to pair
from Python, use bluetooth-classic.

## Usage

```python
import asyncio

from lg_soundbar_bluetooth import LGSoundbar, function_name


async def main() -> None:
    soundbar = LGSoundbar("00:11:22:33:44:55")
    await soundbar.connect(keep_input=True)
    state = soundbar.state
    print(function_name(state.function), state.volume, state.sound_mode)
    await soundbar.set_volume(12)
    await soundbar.disconnect()


asyncio.run(main())
```

Connecting wakes a soundbar that is off, and moves one that is on to its
Bluetooth input; with `keep_input=True` the client switches it straight
back, makes sure it got there, and reports how in `input_restore`. `lg_soundbar_bluetooth.testing.FakeSoundbar` stands in for a soundbar
in tests.

### Finding and pairing a soundbar

```python
from bluetooth_classic import BluetoothClassic

from lg_soundbar_bluetooth import is_lg_soundbar


async def find() -> None:
    async with BluetoothClassic() as bluetooth:
        await bluetooth.discover()
        for device in await bluetooth.devices():
            if is_lg_soundbar(device.name, device.uuids, paired=device.paired):
                await bluetooth.pair(device.address)
                await bluetooth.trust(device.address)
```

## Contributing

See [CONTRIBUTING.md](https://github.com/jeverley/lg-soundbar-bluetooth/blob/main/CONTRIBUTING.md).

## Credits

Message formats were cross-checked against frames captured by
[websterwh/lg-s75qr](https://github.com/websterwh/lg-s75qr). No LG code is
included. The project layout and tooling follow the
[Bluetooth-Devices](https://github.com/Bluetooth-Devices) libraries, which
were created with
[browniebroke/cookiecutter-pypackage](https://github.com/browniebroke/cookiecutter-pypackage).
