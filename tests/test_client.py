"""Tests for the async client against a scripted soundbar."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest
from bluetooth_classic import ServiceLookupError

from lg_soundbar_bluetooth import (
    CannotConnect,
    Feature,
    Frame,
    GeneralCommand,
    HandshakeFailed,
    InputRestore,
    Level,
    LGSoundbar,
    NotConnected,
    UtilityCommand,
)
from lg_soundbar_bluetooth.testing import ADDRESS, FakeSoundbar


def make_client(
    soundbar: FakeSoundbar, channel: int | None = 2, **kwargs: Any
) -> LGSoundbar:
    return LGSoundbar(
        ADDRESS,
        channel,
        connector=kwargs.pop("connector", soundbar.connector),
        send_interval=0,
        settle_quiet=0.05,
        settle_max=0.5,
        ask_timeout=kwargs.pop("ask_timeout", 0.2),
        switch_wait=kwargs.pop("switch_wait", 0.2),
        **kwargs,
    )


async def test_connect_runs_handshake_and_reads_state(soundbar: FakeSoundbar) -> None:
    client = make_client(soundbar)
    await client.connect()

    assert client.connected
    # The input first and alone, then the LG app's opening messages and its
    # steps in its order. The flags are not asked for again.
    assert soundbar.sent[:10] == [
        Frame(0x00, 0x0B),
        Frame(0x00, 0x15),
        Frame(0x00, 0x16),
        Frame(0x00, 0x17, b"\x1f"),
        Frame(0xC4, 0x03),
        Frame(0x00, 0x19),
        Frame(0x00, 0x04),
        Frame(0xC4, 0x66),
        Frame(0x00, 0x06),
        Frame(0x00, 0x08),
    ]
    assert soundbar.sent.count(Frame(0x00, 0x08)) == 1
    assert client.state.emergency is False
    assert Frame(0xC4, 0x03) in soundbar.sent
    state = client.state
    assert state.function == 0xC4
    assert state.functions == [0x07, 0x09, 0x40, 0xC0, 0xD0]
    assert state.supports(Feature.OPT_HDMI_ARC_SUPPORT)
    assert state.selectable_functions == [0x07, 0x09, 0x40, 0xC0, 0xDF]
    assert (state.volume, state.volume_max, state.muted) == (15, 40, False)
    assert state.sound_mode == 0x90
    assert state.sound_modes == [0x90, 0x02, 0x37, 0x38, 0x89]
    assert state.night_mode is False
    assert state.levels[UtilityCommand.WOOFER_LEVEL] == Level(0, -15, 6)
    assert state.levels[UtilityCommand.REAR_LEVEL] == Level(-3, -6, 6)
    assert state.levels[UtilityCommand.AV_SYNC] == Level(0, 0, 30)
    assert state.switches[UtilityCommand.AUTO_POWER] is True
    # The G1 answers for settings it does not have; its flags rule them out.
    for command in (
        UtilityCommand.AUTO_DISPLAY,
        UtilityCommand.UPWARD_LEVEL,
        UtilityCommand.NEURAL_X,
    ):
        assert not state.offers(command)
    for command in (
        UtilityCommand.DRC_CONTROL,
        UtilityCommand.WOOFER_LEVEL,
        UtilityCommand.DIALOG_CONTROL,
        UtilityCommand.SURROUND_SETTING,
    ):
        assert state.offers(command)
    assert state.offers_night_mode


async def test_commands_use_current_input_as_major(soundbar: FakeSoundbar) -> None:
    client = make_client(soundbar)
    await client.connect()
    soundbar.sent.clear()

    await client.set_volume(20)
    await client.set_volume(99)
    await client.set_mute(True)
    await client.set_sound_mode(0x02)
    await client.set_night_mode(True)
    await client.set_level(UtilityCommand.WOOFER_LEVEL, -3)
    await client.set_switch(UtilityCommand.AUTO_VOLUME, True)
    await client.power_off()

    assert [f.encode().hex(" ") for f in soundbar.sent] == [
        "41 54 c4 02 02 28 14 c2",
        "41 54 c4 02 02 28 28 ae",
        "41 54 c4 1d 01 01 fe",
        "41 54 c4 1f 02 00 02 fc",
        "41 54 c4 4a 01 01 fe",
        "41 54 0d 1b 01 fd 02",
        "41 54 0d 1c 01 01 fe",
        "41 54 00 0a 01 00 ff",
    ]
    await asyncio.sleep(0)
    assert client.state.volume == 40
    assert client.state.muted is True
    assert client.state.levels[UtilityCommand.WOOFER_LEVEL].value == -3


async def test_select_input_refreshes_new_input(soundbar: FakeSoundbar) -> None:
    client = make_client(soundbar)
    await client.connect()
    soundbar.sent.clear()

    await client.select_function(0x07)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert soundbar.sent[0] == Frame(0x00, 0x01, b"\x07")
    assert client.state.function == 0x07
    assert Frame(0x07, 0x03) in soundbar.sent


async def test_watchdog_is_answered(soundbar: FakeSoundbar) -> None:
    client = make_client(soundbar)
    await client.connect()
    soundbar.sent.clear()
    assert soundbar.transport is not None

    soundbar.transport._protocol.data_received(Frame(0x00, 0x02).encode())

    assert soundbar.sent == [Frame(0x00, 0x02)]


async def test_callbacks_on_change_and_disconnect(soundbar: FakeSoundbar) -> None:
    client = make_client(soundbar)
    await client.connect()
    calls = []
    remove = client.register_callback(lambda: calls.append(client.connected))

    await client.set_volume(10)
    await asyncio.sleep(0)
    assert calls == [True]

    await client.disconnect()
    await asyncio.sleep(0)
    assert calls == [True, False]
    assert not client.connected

    remove()
    with pytest.raises(NotConnected):
        await client.set_volume(5)


async def test_silent_device_fails_handshake(
    soundbar: FakeSoundbar, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("lg_soundbar_bluetooth.client.HANDSHAKE_TIMEOUT", 0.05)
    soundbar.silent = True
    client = make_client(soundbar)

    with pytest.raises(CannotConnect):
        await client.connect()
    assert soundbar.transport is not None and soundbar.transport.closed
    assert not client.connected


async def test_soundbar_closing_during_handshake_cannot_connect(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.drop_after = 2
    # No channel to fall back from: only one connection is made.
    client = make_client(soundbar, channel=None)

    with pytest.raises(CannotConnect, match="closed the connection"):
        await client.connect()
    assert not client.connected


async def test_without_a_channel_the_service_is_looked_up(
    soundbar: FakeSoundbar,
) -> None:
    tried = []

    async def connector(address, channel, factory, timeout, **kwargs):
        tried.append(channel)
        return await soundbar.connector(address, channel, factory, timeout, **kwargs)

    client = make_client(soundbar, channel=None, connector=connector)
    await client.connect()
    # The connector looks it up; the channel it used is kept.
    assert tried == [None]
    assert client.channel == 10


async def test_the_channel_used_is_kept(soundbar: FakeSoundbar) -> None:
    async def connector(address, channel, factory, timeout, **kwargs):
        # The soundbar refused the channel given: the connector looked the
        # service up and connected to the channel found.
        return await soundbar.connector(address, None, factory, timeout, **kwargs)

    client = make_client(soundbar, channel=2, connector=connector)
    await client.connect()
    assert client.channel == 10


async def test_a_failed_lookup_cannot_connect(soundbar: FakeSoundbar) -> None:
    async def connector(address, channel, factory, timeout, **kwargs):
        raise ServiceLookupError(f"{address} does not offer service 1101")

    client = make_client(soundbar, channel=None, connector=connector)
    with pytest.raises(CannotConnect):
        await client.connect()
    assert client.channel is None


async def test_unreachable_soundbar_cannot_connect(soundbar: FakeSoundbar) -> None:
    tried = []

    async def connector(address, channel, factory, timeout, **kwargs):
        tried.append(channel)
        raise OSError(112, "Host is down")

    client = make_client(soundbar, connector=connector)
    with pytest.raises(CannotConnect):
        await client.connect()
    assert tried == [2]
    # Kept: the soundbar was off, the channel did not move.
    assert client.channel == 2


async def test_busy_channel_is_retried(
    soundbar: FakeSoundbar, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("lg_soundbar_bluetooth.client.BUSY_DELAY", 0)
    attempts = []

    async def connector(address, channel, factory, timeout, **kwargs):
        attempts.append(channel)
        if len(attempts) < 3:
            raise OSError(16, "Resource busy")
        return await soundbar.connector(address, channel, factory, timeout, **kwargs)

    client = make_client(soundbar, connector=connector)
    await client.connect()
    assert attempts == [2, 2, 2]
    assert client.connected


async def test_disconnect_waits_for_close(soundbar: FakeSoundbar) -> None:
    client = make_client(soundbar)
    await client.connect()
    await client.disconnect()
    assert soundbar.transport is not None and soundbar.transport.closed
    assert not client.connected


async def test_connection_dropping_while_reporting_fails_connect(
    soundbar: FakeSoundbar,
) -> None:
    # Count the frames a normal connection sends, then drop on the last one:
    # nothing more is sent, so only the wait for replies sees the drop.
    await make_client(soundbar).connect()
    frames = len(soundbar.sent)
    soundbar.sent.clear()
    soundbar.drop_after = frames
    client = make_client(soundbar, channel=None)

    with pytest.raises(HandshakeFailed):
        await client.connect()
    assert not client.connected


async def test_a_channel_that_does_not_answer_is_looked_up_again(
    soundbar: FakeSoundbar,
) -> None:
    tried = []

    async def connector(address, channel, factory, timeout, **kwargs):
        tried.append(channel)
        # Another service now answers on the old channel, but never as a
        # soundbar.
        soundbar.silent = channel is not None
        return await soundbar.connector(address, channel, factory, timeout, **kwargs)

    client = make_client(soundbar, channel=2, connector=connector)
    with patch("lg_soundbar_bluetooth.client.HANDSHAKE_TIMEOUT", 0.05):
        await client.connect()
    assert tried == [2, None]
    assert client.connected
    assert client.channel == 10


async def test_a_handshake_failure_after_a_lookup_is_not_retried(
    soundbar: FakeSoundbar,
) -> None:
    tried = []

    async def connector(address, channel, factory, timeout, **kwargs):
        tried.append(channel)
        soundbar.silent = True
        return await soundbar.connector(address, channel, factory, timeout, **kwargs)

    client = make_client(soundbar, channel=2, connector=connector)
    with (
        patch("lg_soundbar_bluetooth.client.HANDSHAKE_TIMEOUT", 0.05),
        pytest.raises(HandshakeFailed),
    ):
        await client.connect()
    assert tried == [2, None]
    # Not kept, so the next connect looks the service up straight away.
    assert client.channel is None


async def test_connect_reads_firmware_and_extras(soundbar: FakeSoundbar) -> None:
    client = make_client(soundbar)
    await client.connect()
    state = client.state
    assert state.firmware_version == "MICOM M2103110, MAIN B210414A"
    assert Frame(0x0C, 0x01, bytes([0x05, 0x07])) in soundbar.sent
    assert state.bass is not None and state.bass.value == 0
    assert state.sleep_timer is None
    assert state.woofer_connected is True
    assert state.rear_connected is None
    assert state.input_connected is True
    assert state.audio_info is None


async def test_tone_and_sleep_timer_commands(soundbar: FakeSoundbar) -> None:
    soundbar.sleep_timer = 0
    client = make_client(soundbar)
    await client.connect()
    soundbar.sent.clear()

    await client.set_tone(-2, 3)
    await client.set_sleep_timer(30)
    await client.set_sleep_timer(0)
    await asyncio.sleep(0)

    assert soundbar.sent == [
        Frame(0xC4, 0x1F, bytes([0x03, 0xFE, 0x03])),
        Frame(0x0D, 0x14, bytes([0x01, 30])),
        Frame(0x0D, 0x14, bytes([0x00, 0x00])),
    ]
    with pytest.raises(ValueError):
        await client.set_sleep_timer(300)


def test_rejects_bad_address() -> None:
    with pytest.raises(ValueError):
        LGSoundbar("not-an-address")
    assert LGSoundbar("aa-bb-cc-dd-ee-ff").address == ADDRESS


async def test_connect_waits_for_each_step_like_the_app(
    soundbar: FakeSoundbar,
) -> None:
    # Supported inputs is only asked once the current state has answered.
    original = soundbar.replies_to
    answered_state = False

    def replies(frame: Frame) -> list[Frame]:
        nonlocal answered_state
        if frame == Frame(0x00, 0x04):
            assert answered_state
        replies = original(frame)
        if frame.minor == 0x03 and replies:
            answered_state = True
        return replies

    soundbar.replies_to = replies  # type: ignore[method-assign]
    client = make_client(soundbar)
    await client.connect()
    assert client.connected


async def test_connect_skips_the_extended_flags_when_the_feature_list_says_so(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.feature_list = bytes([0x04, 0x00, 0x01]) + soundbar.feature_list[3:]
    client = make_client(soundbar)
    await client.connect()
    assert Frame(0x00, 0x08) not in soundbar.sent
    assert client.state.features is None
    assert client.state.extended_flags_available is False


async def test_connect_asks_a_step_three_times_then_carries_on(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.extra[(0x00, 0x04)] = []
    client = make_client(soundbar, ask_timeout=0.05)
    await client.connect()
    assert client.connected
    assert soundbar.sent.count(Frame(0x00, 0x04)) == 3
    # The later steps still ran.
    assert Frame(0x00, 0x08) in soundbar.sent


async def test_connect_asks_only_for_what_the_flags_offer(
    soundbar: FakeSoundbar,
) -> None:
    client = make_client(soundbar)
    await client.connect()
    asked = {(f.major, f.minor) for f in soundbar.sent}
    # A G1's flags leave out auto display, overhead level, side level,
    # Neural:X and the audio format; the sleep timer is never asked for.
    for minor in (0x1E, 0x29, 0x28, 0x2A, 0x14):
        assert (0x0D, minor) not in asked
    assert (0xC4, 0x72) not in asked
    # Flagged settings, the subwoofer and rear speakers (by their levels)
    # and the firmware (by the feature list) are.
    for minor in (0x09, 0x1B, 0x21, 0x2C, 0x25, 0x43):
        assert (0x0D, minor) in asked
    assert (0x0C, 0x00) in asked
    # No second extended feature list on a G1.
    assert (0x00, 0x24) not in asked
    assert UtilityCommand.AUTO_DISPLAY not in client.state.switches


async def test_connect_asks_for_the_second_feature_list_when_flagged(
    soundbar: FakeSoundbar,
) -> None:
    flags = bytearray(soundbar.feature_flags)
    flags[9] |= 0x80
    # Without the level flags, the speaker states follow the second list.
    flags[3] &= ~0x84
    soundbar.feature_flags = bytes(flags)
    soundbar.feature_flags_2 = bytes([0x02])
    client = make_client(soundbar)
    await client.connect()
    asked = {(f.major, f.minor) for f in soundbar.sent}
    assert (0x00, 0x24) in asked
    assert (0x0D, 0x43) in asked
    assert (0x0D, 0x25) not in asked


async def test_connect_without_firmware_updates_skips_the_firmware(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.feature_list = bytes([0x08]) + soundbar.feature_list[1:]
    client = make_client(soundbar)
    await client.connect()
    assert (0x0C, 0x00) not in {(f.major, f.minor) for f in soundbar.sent}


async def test_connect_reads_the_new_firmware_chips_when_flagged(
    soundbar: FakeSoundbar,
) -> None:
    flags = bytearray(soundbar.feature_flags)
    flags[9] |= 0x40
    soundbar.feature_flags = bytes(flags)
    # Numbers the old list names differently; the type text decides.
    soundbar.firmware = {7: ("WirelessRx", "R100"), 12: ("DSP2", "D200")}
    client = make_client(soundbar)
    await client.connect()
    asked = {(f.major, f.minor) for f in soundbar.sent}
    assert (0x0C, 0x07) in asked
    assert (0x0C, 0x00) not in asked
    assert client.state.firmware == {"WirelessRx": "R100", "DSP2": "D200"}


async def test_connect_asks_later_steps_once_after_one_went_unanswered(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.extra[(0x00, 0x04)] = []
    soundbar.extra[(0x00, 0x06)] = []
    client = make_client(soundbar, ask_timeout=0.05)
    await client.connect()
    assert soundbar.sent.count(Frame(0x00, 0x04)) == 3
    assert soundbar.sent.count(Frame(0x00, 0x06)) == 1


async def test_frames_waiting_when_the_connection_opens_are_handled(
    soundbar: FakeSoundbar,
) -> None:
    # The soundbar moved before the client took the connection over; the
    # move is still timed and switched back from at once.
    soundbar.switch_to_bt_on_connect = True
    soundbar.move_before_answering = True
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert "moved before answering" in client.timings
    assert client.connected


async def test_connect_waits_for_a_soundbar_still_starting_up(
    soundbar: FakeSoundbar,
) -> None:
    # An MTK soundbar reports it is still starting up and ignores the
    # start-up; once it reports it is done, the start-up runs again.
    soundbar.mtk_boot_seconds = 0.1
    client = make_client(soundbar)
    await client.connect()
    assert client.connected
    assert soundbar.sent.count(Frame(0x00, 0x0B)) == 2
    assert client.state.function == 0xC4
    assert client.state.features is not None
    timings = client.timings
    assert timings["starting up"] <= timings["started up"]


async def test_connect_gives_up_on_a_soundbar_that_does_not_start_up(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.mtk_booting = True
    client = make_client(soundbar)
    with (
        patch("lg_soundbar_bluetooth.client.MTK_BOOT_TIMEOUT", 0.1),
        pytest.raises(HandshakeFailed, match="did not finish starting up"),
    ):
        await client.connect()
    assert not client.connected


async def test_connect_stops_the_start_up_in_emergency_mode(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.emergency = True
    client = make_client(soundbar)
    await client.connect()
    assert client.connected
    assert client.state.emergency is True
    asked = [(f.major, f.minor) for f in soundbar.sent]
    # Only the firmware is asked for after the emergency check, as by the app.
    assert (0x0C, 0x00) in asked
    for skipped in ((0x00, 0x04), (0x00, 0x06), (0x00, 0x08), (0x0D, 0x09)):
        assert skipped not in asked
    assert "emergency" in client.timings


async def test_connect_sends_nothing_until_the_input_is_reported(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.extra[(0x00, 0x0B)] = []
    client = make_client(soundbar, channel=None)
    with (
        patch("lg_soundbar_bluetooth.client.HANDSHAKE_TIMEOUT", 0.2),
        pytest.raises(HandshakeFailed),
    ):
        await client.connect()
    assert soundbar.sent == [Frame(0x00, 0x0B)]
    assert set(client.timings) == {"connecting"}


async def test_connect_records_handshake_timings(soundbar: FakeSoundbar) -> None:
    soundbar.switch_to_bt_on_connect = True
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    timings = client.timings
    assert list(timings) == [
        "connecting",
        "first input",
        "moved",
        "flags",
        "switched back",
        "ready",
    ]
    steps = [value for step, value in timings.items() if step != "connecting"]
    assert steps == sorted(steps)


async def test_connect_switches_straight_back_from_bluetooth(
    soundbar: FakeSoundbar,
) -> None:
    # On eARC; a soundbar that is on moves to Bluetooth as the connection
    # opens.
    soundbar.switch_to_bt_on_connect = True
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.initial_function == 0xC4
    # Selected as the LG app does, as Optical/HDMI ARC, once the feature
    # flags said Optical, ARC and eARC are one input.
    assert client.restored_input == 0xDF
    assert client.state.function == 0xC4
    assert Frame(0x00, 0x01, b"\xc4") not in soundbar.sent
    assert soundbar.sent.count(Frame(0x00, 0x01, b"\xdf")) == 1
    switch = soundbar.sent.index(Frame(0x00, 0x01, b"\xdf"))
    assert switch > soundbar.sent.index(Frame(0x00, 0x08))
    assert switch < soundbar.sent.index(Frame(0x0C, 0x00))
    # The new input's details were read again afterwards.
    assert Frame(0xC4, 0x03) in soundbar.sent[switch:]


async def test_connect_switches_other_inputs_straight_back(
    soundbar: FakeSoundbar,
) -> None:
    # On HDMI: its own code, sent at once, before the feature flags.
    soundbar.function = 0xC0
    soundbar.switch_to_bt_on_connect = True
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.restored_input == 0xC0
    assert client.state.function == 0xC0
    switch = soundbar.sent.index(Frame(0x00, 0x01, b"\xc0"))
    assert switch < soundbar.sent.index(Frame(0x00, 0x08))


async def test_connect_notes_a_move_before_answering(soundbar: FakeSoundbar) -> None:
    soundbar.switch_to_bt_on_connect = True
    soundbar.move_before_answering = True
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.moved_before_answering
    assert client.initial_function == 0x07
    assert client.restored_input is None
    assert "moved before answering" in client.timings
    assert "connecting" in client.timings


async def test_connect_on_bluetooth_is_not_a_move_before_answering(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.function = 0x07
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert not client.moved_before_answering
    assert "moved before answering" not in client.timings


async def test_connect_selects_the_input_again_if_the_soundbar_leaves_it(
    soundbar: FakeSoundbar,
) -> None:
    # On HDMI; after being switched back it moves itself to eARC, as a G1
    # did with a TV on eARC.
    soundbar.function = 0xC0
    soundbar.switch_to_bt_on_connect = True
    soundbar.jump_after_select = 0xC4
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert soundbar.sent.count(Frame(0x00, 0x01, b"\xc0")) == 2
    assert client.state.function == 0xC0
    assert "switched back again" in client.timings


async def test_connect_selects_the_input_again_once_while_starting_up(
    soundbar: FakeSoundbar,
) -> None:
    # It leaves HDMI again after the second selection; the start-up does not
    # select it a third time, but the check after it does, and it sticks.
    soundbar.function = 0xC0
    soundbar.switch_to_bt_on_connect = True
    soundbar.jump_after_select = 0xC4
    original = soundbar.replies_to
    selections = 0

    def jump_twice(frame: Frame) -> list[Frame]:
        nonlocal selections
        if frame == Frame(0x00, 0x01, b"\xc0"):
            selections += 1
            if selections == 2:
                soundbar.jump_after_select = 0x40
        return original(frame)

    soundbar.replies_to = jump_twice  # type: ignore[method-assign]
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert soundbar.sent.count(Frame(0x00, 0x01, b"\xc0")) == 3
    assert client.state.function == 0xC0
    assert client.input_restore == InputRestore(0xC0, True, 0xC0, True, 1)


async def test_input_restore_when_the_switch_back_takes(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.function = 0xC0
    soundbar.switch_to_bt_on_connect = True
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.input_restore == InputRestore(0xC0, True, 0xC0, True, 0)
    assert soundbar.sent.count(Frame(0x00, 0x01, b"\xc0")) == 1


async def test_input_restore_selects_again_when_ignored(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.function = 0xC0
    soundbar.switch_to_bt_on_connect = True
    soundbar.ignored_once = {0xC0}
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.input_restore == InputRestore(0xC0, True, 0xC0, True, 1)
    assert client.state.function == 0xC0


async def test_input_restore_gives_up(soundbar: FakeSoundbar) -> None:
    soundbar.function = 0xC0
    soundbar.switch_to_bt_on_connect = True
    soundbar.ignored_modes = {0xC0}
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.input_restore == InputRestore(0xC0, True, 0xC0, False, 2)
    assert soundbar.sent.count(Frame(0x00, 0x01, b"\xc0")) == 3


async def test_input_restore_when_the_connection_did_not_move_it(
    soundbar: FakeSoundbar,
) -> None:
    soundbar.function = 0xC0
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.input_restore == InputRestore(0xC0, False, None, True, 0)
    assert Frame(0x00, 0x01, b"\xc0") not in soundbar.sent


async def test_input_restore_on_bluetooth(soundbar: FakeSoundbar) -> None:
    soundbar.function = 0x07
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.input_restore == InputRestore(0x07, False, None, True, 0)


async def test_no_input_restore_without_keep_input(soundbar: FakeSoundbar) -> None:
    client = make_client(soundbar)
    await client.connect()
    assert client.input_restore is None


async def test_connect_switches_back_with_remembered_flags(
    soundbar: FakeSoundbar,
) -> None:
    # On eARC; it moves before this connection's flags arrive, which are
    # held back. The flags from an earlier connection decide at once.
    soundbar.switch_to_bt_on_connect = True
    soundbar.extra[(0x00, 0x08)] = []
    client = make_client(soundbar, known_features={3 * 8 + 6})
    await client.connect(keep_input=True)
    assert client.restored_input == 0xDF
    assert soundbar.sent.count(Frame(0x00, 0x01, b"\xdf")) == 1
    # Only what this connection reported is in the state.
    assert client.state.features is None


async def test_connect_remembers_the_flags_for_the_next_connection(
    soundbar: FakeSoundbar,
) -> None:
    client = make_client(soundbar)
    assert client.known_features is None
    await client.connect()
    assert client.known_features == client.state.features


async def test_connect_leaves_the_input_without_restore(soundbar: FakeSoundbar) -> None:
    soundbar.switch_to_bt_on_connect = True
    client = make_client(soundbar)
    await client.connect()
    assert client.restored_input is None
    assert client.state.function == 0x07


async def test_switch_back_without_feature_flags_uses_the_input_code(
    soundbar: FakeSoundbar,
) -> None:
    # On Optical; the soundbar never reports its extended feature flags and
    # none are remembered, so the start-up switches back with Optical's code.
    soundbar.function = 0xD0
    soundbar.switch_to_bt_on_connect = True
    soundbar.extra[(0x00, GeneralCommand.EXTENDED_SUPPORTED_FEATURE_LISTS)] = []
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.input_restore == InputRestore(0xD0, True, 0xD0, True, 0)
    assert soundbar.sent.count(Frame(0x00, 0x01, b"\xd0")) == 1


async def test_input_restore_after_a_move_after_the_start_up(
    soundbar: FakeSoundbar,
) -> None:
    # Moved to Bluetooth only after the start-up, so nothing was sent then;
    # without flags the input's own code is selected.
    soundbar.function = 0xD0
    soundbar.extra[(0x00, GeneralCommand.EXTENDED_SUPPORTED_FEATURE_LISTS)] = []
    client = make_client(soundbar)
    await client.connect()
    client.state.function = 0x07
    restore = await client._restore_input()
    assert restore == InputRestore(0xD0, True, None, True, 1)
    assert Frame(0x00, 0x01, b"\xd0") in soundbar.sent


async def test_input_restore_when_the_soundbar_switches_off(
    soundbar: FakeSoundbar,
) -> None:
    # It ignores the switch back, then is switched off while it is retried.
    soundbar.function = 0xC0
    soundbar.switch_to_bt_on_connect = True
    soundbar.ignored_modes = {0xC0}
    original = soundbar.replies_to
    selections = 0

    def switch_off_on_retry(frame: Frame) -> list[Frame]:
        nonlocal selections
        if frame == Frame(0x00, 0x01, b"\xc0"):
            selections += 1
            if selections == 2:
                asyncio.get_running_loop().call_soon(soundbar.switch_off)
        return original(frame)

    soundbar.replies_to = switch_off_on_retry  # type: ignore[method-assign]
    client = make_client(soundbar)
    await client.connect(keep_input=True)
    assert client.input_restore is not None
    assert not client.input_restore.reached
    assert not client.connected


async def test_overlapping_connects_open_one_connection(
    soundbar: FakeSoundbar,
) -> None:
    original = soundbar.connector

    async def slow_connector(*args: Any, **kwargs: Any) -> Any:
        # Opening a Bluetooth link takes a while.
        await asyncio.sleep(0.05)
        return await original(*args, **kwargs)

    client = make_client(soundbar, connector=slow_connector)
    await asyncio.gather(client.connect(), client.connect())
    assert soundbar.connections == 1
    assert client.connected
