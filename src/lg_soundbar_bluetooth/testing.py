"""A fake LG soundbar for tests, used in place of a Bluetooth connection.

It answers the way an LG G1 does: pass ``FakeSoundbar().connector`` as the
client's ``connector`` to test an application without a soundbar.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from .protocol import Frame, FrameParser

ADDRESS = "AA:BB:CC:DD:EE:FF"


class FakeTransport(asyncio.Transport):
    """Records writes and hands them to a fake soundbar."""

    def __init__(self, soundbar: FakeSoundbar, protocol: asyncio.Protocol) -> None:
        super().__init__()
        self._soundbar = soundbar
        self._protocol = protocol
        self._parser = FrameParser()
        self.closed = False

    def write(self, data: bytes | bytearray | memoryview) -> None:
        """Hand each frame written to the fake soundbar and deliver its replies."""
        for frame in self._parser.feed(bytes(data)):
            self._soundbar.sent.append(frame)
            if len(self._soundbar.sent) == self._soundbar.drop_after:
                self.close()
                return
            for reply in self._soundbar.replies_to(frame):
                asyncio.get_running_loop().call_soon(
                    self._protocol.data_received, reply.encode()
                )

    def close(self, exc: Exception | None = None) -> None:
        """Close the connection, as the soundbar resetting it would."""
        if not self.closed:
            self.closed = True
            asyncio.get_running_loop().call_soon(self._protocol.connection_lost, exc)

    def is_closing(self) -> bool:
        """Return whether the connection is closed."""
        return self.closed


class FakeSoundbar:
    """Answers frames the way an LG G1 is expected to.

    The inputs, sound modes, levels and settings match what the LG app shows
    for a G1 connected to a TV by HDMI eARC.
    """

    def __init__(self) -> None:
        self.sent: list[Frame] = []
        self.function = 0xC4  # HDMI eARC
        self.switched_off_on: int | None = None
        # As a real G1 reports them: Optical (0xd0), not Optical/HDMI ARC.
        self.functions = [0x07, 0x09, 0x40, 0xC0, 0xD0]
        # The extended feature flags a real G1 sends (byte 3 bit 6 is
        # OPT_HDMI_ARC_SUPPORT). They leave out auto display, overhead level
        # and Neural:X, which it answered queries for when asked (they are
        # only asked for while the flags are not known).
        self.feature_flags = bytes.fromhex(
            "d48100df80a180050000000010000010000010000010"
        )
        # The feature list (00/06) a real G1 sends: extended feature flags and
        # firmware details available (byte 0), no sleep timer (byte 1), power
        # off offered (byte 2).
        self.feature_list = bytes.fromhex(
            "0c00010701001000050000000000000000000000000217f20500"
            "0000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000"
            "1000050000000000000000001000050000000000000000000000"
            "00"
        )
        # The second extended feature flags (00/24); a G1 has none, so it is
        # never asked. None means no reply.
        self.feature_flags_2: bytes | None = None
        self.volume = 15
        self.muted = False
        self.sound_mode = 0x90  # AI Sound Pro
        self.sound_modes = [0x90, 0x02, 0x37, 0x38, 0x89]
        self.night_mode = False
        # (value, minimum, maximum) as the soundbar sends them.
        self.levels: dict[int, tuple[int, int, int]] = {
            0x1B: (0, -15, 6),  # woofer
            0x26: (0, -6, 6),  # center
            0x21: (-3, -6, 6),  # rear
            0x2B: (0, 0, 6),  # dialog control
            0x1A: (0, 0, 30),  # AV sync, in 10 ms steps
            0x29: (0, -6, 6),  # overhead, answered when asked; a G1 has none
        }
        self.switches: dict[int, bool] = {
            0x09: False,  # DRC
            0x1C: False,  # auto volume
            0x1D: True,  # auto power
            0x19: True,  # TV remote
            0x22: True,  # surround
            0x1E: False,  # auto display, answered when asked; not offered
        }
        self.bass = 0
        self.middle = 0
        self.treble = 0
        # A G1 has two tone bands; some soundbars report three.
        self.three_band = False
        # Replies for queries a G1 may not answer; None means no reply.
        # A G1 has no sleep timer; others report minutes left, 0 for off.
        self.sleep_timer: int | None = None
        self.audio_info: str | None = None
        self.woofer_connected: int | None = 1
        # Special sound mode: 0 off, 1 Dolby Atmos, 2 DTS:X, 3 synced with TV.
        self.special_eq: int | None = None
        self.rear_connected: int | None = None
        # Firmware chips (MAIN and MICOM) and versions, as the LG app showed.
        self.firmware = {7: ("MAIN", "B210414A"), 5: ("MICOM", "M2103110")}
        self.model = "G1"
        self.silent = False
        # Close the connection after receiving this many frames, as a G1 did.
        self.drop_after: int | None = None
        self.transport: FakeTransport | None = None
        self.connections = 0
        # Switched off: connecting wakes it on Bluetooth, as a G1 with BT LOCK off.
        self.off = False
        # Like a G1, switch to Bluetooth when connected to while on another
        # input, after first reporting that input. Off by default so most
        # tests see the input they set.
        self.switch_to_bt_on_connect = False
        # With switch_to_bt_on_connect: move before the input is asked for,
        # reporting the move unasked, as a G1 did when the first query was
        # late.
        self.move_before_answering = False
        # Like a soundbar with an MTK chip still starting up: on connecting it
        # reports "started" (00/18 00) and ignores everything until it
        # reports "completed" (00/18 01) after this many seconds; None never.
        # A G1 has no MTK chip and never does this.
        self.mtk_boot_seconds: float | None = None
        self.mtk_booting = False
        # Answers the emergency check with 01, as a soundbar left in
        # emergency mode by a failed firmware update would.
        self.emergency = False
        # Input codes it ignores when asked to select them: a G1 ignores its
        # eARC code and only takes Optical/HDMI ARC (0xdf).
        self.ignored_modes: set[int] = {0xC4}
        # Codes it ignores the first time only.
        self.ignored_once: set[int] = set()
        # After the next input selected, move by itself to this input, as a
        # G1 moved to eARC after being switched back to HDMI.
        self.jump_after_select: int | None = None
        self._fresh = False
        # When set, a scan cannot ask BlueZ and finds nothing either way.
        self.bluez_unavailable = False
        self.extra: dict[tuple[int, int], list[Frame]] = {
            # The G1 answers the Neural:X query with two bytes.
            (0x0D, 0x2A): [Frame(0x0D, 0x2A, b"\x00\x00")],
        }

    def replies_to(self, frame: Frame) -> list[Frame]:
        """Return the frames a G1 sends in reply to a frame."""
        if self.silent or self.mtk_booting:
            return []
        key = (frame.major, frame.minor)
        if key in self.extra:
            return self.extra[key]
        fn = self.function
        payload = frame.payload
        if key == (0x00, 0x0B):
            if self._fresh and self.switch_to_bt_on_connect and fn != 0x07:
                self._fresh = False
                self.function = 0x07
                return [Frame(0x00, 0x0B, bytes([fn])), Frame(0x00, 0x0B, b"\x07")]
            self._fresh = False
            return [Frame(0x00, 0x0B, bytes([fn]))]
        if key == (0x00, 0x0A) and payload == b"\x00":
            asyncio.get_running_loop().call_soon(self.switch_off)
            return []
        if key == (0x00, 0x01) and payload[0] in self.ignored_modes:
            return []
        if key == (0x00, 0x01) and payload[0] in self.ignored_once:
            self.ignored_once.discard(payload[0])
            return []
        if key == (0x00, 0x01):
            # Like the G1, Optical/HDMI ARC is reported as HDMI eARC.
            self.function = 0xC4 if payload[0] == 0xDF else payload[0]
            if (jump := self.jump_after_select) is not None:
                self.jump_after_select = None
                # After the reply, as a G1 moved about a second later.
                asyncio.get_running_loop().call_later(0.01, self._jump, jump)
            return [Frame(0x00, 0x01, bytes([self.function]))]
        if key == (0x00, 0x04):
            return [Frame(0x00, 0x04, bytes(self.functions))]
        if key == (0x00, 0x16):
            # A G1 is not in emergency mode; it does not answer 00/15 or 00/17.
            return [Frame(0x00, 0x16, b"\x01" if self.emergency else b"\x00")]
        if key == (0x00, 0x06):
            return [Frame(0x00, 0x06, self.feature_list)]
        if key == (0x00, 0x24) and self.feature_flags_2 is not None:
            return [Frame(0x00, 0x24, self.feature_flags_2)]
        if key == (0x00, 0x08):
            return [Frame(0x00, 0x08, self.feature_flags)]
        if key == (0x0C, 0x07):
            # As a soundbar with the new firmware info flag answers: chip
            # numbers one by one.
            return [Frame(0x0C, 0x07, bytes([0x00, 0x00, *self.firmware]))]
        if key == (0x0C, 0x00):
            chips = sum(1 << chip for chip in self.firmware)
            return [Frame(0x0C, 0x00, bytes([0x00, chips, 0x00]))]
        if key == (0x0C, 0x01) and payload[0] in self.firmware:
            return [Frame(0x0C, 0x01, self._firmware_info(payload[0]))]
        if key == (0x0D, 0x14) and self.sleep_timer is not None:
            if payload:
                self.sleep_timer = payload[1] if payload[0] else 0
            return [
                Frame(0x0D, 0x14, bytes([int(self.sleep_timer > 0), self.sleep_timer]))
            ]
        if key == (0x0D, 0x2C) and self.special_eq is not None:
            return [Frame(0x0D, 0x2C, bytes([self.special_eq]))]
        if key == (0x0D, 0x25) and self.woofer_connected is not None:
            return [Frame(0x0D, 0x25, bytes([self.woofer_connected]))]
        if key == (0x0D, 0x43) and self.rear_connected is not None:
            return [Frame(0x0D, 0x43, bytes([self.rear_connected, 0x03]))]
        if frame.major == 0x0D and frame.minor in self.levels:
            if payload:
                _, low, high = self.levels[frame.minor]
                value = payload[0] - 0x100 if payload[0] & 0x80 else payload[0]
                self.levels[frame.minor] = (value, low, high)
            return [
                Frame(
                    0x0D, frame.minor, bytes(v & 0xFF for v in self.levels[frame.minor])
                )
            ]
        if frame.major == 0x0D and frame.minor in self.switches:
            if payload:
                self.switches[frame.minor] = payload[0] == 1
            return [Frame(0x0D, frame.minor, bytes([self.switches[frame.minor]]))]
        if frame.major != fn:
            return []
        if frame.minor == 0x03:
            return [
                Frame(fn, 0x03, bytes([0x00, int(self.muted), 40, self.volume])),
                Frame(fn, 0x1F, bytes([0x05, *self.sound_modes])),
                Frame(fn, 0x1F, bytes([0x00, self.sound_mode])),
                # A G1 also reports its bass and treble, without their range.
                self._tone_report(fn),
            ]
        if frame.minor == 0x72:
            if self.audio_info is None:
                return []
            return [Frame(fn, 0x72, self.audio_info.encode())]
        if frame.minor in (0x3F, 0x5F, 0x66, 0x52):
            # Connected through ARC; it says the other links are not supported.
            return [Frame(fn, frame.minor, b"\x01" if frame.minor == 0x66 else b"\xff")]
        if frame.minor == 0x4A:
            if payload:
                self.night_mode = payload[0] == 1
            return [Frame(fn, 0x4A, bytes([self.night_mode]))]
        if not payload:
            return []
        # The soundbar applies setters and echoes them.
        if frame.minor == 0x02:
            self.volume = payload[1]
        elif frame.minor == 0x1D:
            self.muted = payload[0] == 1
        elif frame.minor == 0x1F and payload[0] == 0x01:
            self.bass, self.middle, self.treble = (
                b - 0x100 if b & 0x80 else b for b in payload[1:4]
            )
        elif frame.minor == 0x1F and payload[0] == 0x03:
            self.bass = payload[1] - 0x100 if payload[1] & 0x80 else payload[1]
            self.treble = payload[2] - 0x100 if payload[2] & 0x80 else payload[2]
        elif frame.minor == 0x1F:
            self.sound_mode = payload[1]
        else:
            return []
        return [frame]

    @property
    def visible(self) -> bool | None:
        """Return what a scan for the soundbar finds."""
        return None if self.bluez_unavailable else not self.off

    def _jump(self, function: int) -> None:
        self.function = function
        if self.transport is not None and not self.transport.closed:
            self.transport._protocol.data_received(
                Frame(0x00, 0x0B, bytes([function])).encode()
            )

    def switch_off(self) -> None:
        """Switch off, resetting the connection as a G1 does."""
        self.off = True
        # The input it was on when switched off, which it then remembers.
        self.switched_off_on = self.function
        if self.transport is not None:
            self.transport.close(ConnectionResetError(104, "Connection reset by peer"))

    async def connector(
        self,
        address: str,
        protocol_factory: Callable[[], asyncio.Protocol],
        timeout: float,
        *,
        write_on_connect: bytes,
    ) -> tuple[asyncio.Transport, asyncio.Protocol]:
        """Connect to the fake soundbar, as the client's connector does."""
        self.connections += 1
        self._fresh = True
        if self.off:
            self.off = False
            self.function = 0x07
        protocol = protocol_factory()
        self.transport = FakeTransport(self, protocol)
        protocol.connection_made(self.transport)
        if (
            self.move_before_answering
            and self.switch_to_bt_on_connect
            and self.function != 0x07
        ):
            self._fresh = False
            self.function = 0x07
            protocol.data_received(Frame(0x00, 0x0B, b"\x07").encode())
        if self.mtk_boot_seconds is not None or self.mtk_booting:
            self.mtk_booting = True
            protocol.data_received(Frame(0x00, 0x18, b"\x00").encode())
            if self.mtk_boot_seconds is not None:
                asyncio.get_running_loop().call_later(
                    self.mtk_boot_seconds, self._finish_booting, protocol
                )
        if write_on_connect:
            self.transport.write(write_on_connect)
        return self.transport, protocol

    def _finish_booting(self, protocol: asyncio.Protocol) -> None:
        self.mtk_booting = False
        self.mtk_boot_seconds = None
        if self.transport is not None and not self.transport.closed:
            protocol.data_received(Frame(0x00, 0x18, b"\x01").encode())

    def _firmware_info(self, chip: int) -> bytes:
        """Return a FIRMWARE_INFO reply laid out as the LG app reads it."""
        name, version = self.firmware[chip]
        info = bytearray(100)
        info[0], info[1], info[2] = chip, 0x07, 0x02

        def put(offset: int, text: str) -> None:
            info[offset] = len(text)
            info[offset + 1 : offset + 1 + len(text)] = text.encode()

        put(3, "G1")
        put(19, "LG G1(XX)")
        put(35, self.model)
        put(51, name)
        put(67, version)
        put(83, "GB")
        return bytes(info)

    def _tone_report(self, fn: int) -> Frame:
        if self.three_band:
            bands = (self.bass, self.middle, self.treble)
            return Frame(fn, 0x1F, bytes([0x01, *(b & 0xFF for b in bands)]))
        return Frame(fn, 0x1F, bytes([0x03, self.bass & 0xFF, self.treble & 0xFF]))
