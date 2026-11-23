"""Tests for decoding soundbar replies into state."""

from __future__ import annotations

from lg_soundbar_bluetooth import (
    Feature,
    Feature2,
    Frame,
    Level,
    SoundbarState,
    SpecialEq,
    UtilityCommand,
)
from lg_soundbar_bluetooth.const import SOUND_MODES


def test_mode_and_supported_inputs() -> None:
    state = SoundbarState()
    assert state.apply(Frame(0x00, 0x0B, b"\xc3"))
    assert state.function == 0xC3
    assert state.apply(Frame(0x00, 0x04, b"\x07\xc3\xdf"))
    assert state.functions == [0x07, 0xC3, 0xDF]
    assert not state.apply(Frame(0x00, 0x0B, b"\xc3"))


def test_volume_snapshot_and_mute() -> None:
    state = SoundbarState()
    state.apply(Frame(0xC3, 0x03, bytes([0x00, 0x01, 40, 12])))
    assert (state.muted, state.volume_max, state.volume) == (True, 40, 12)
    state.apply(Frame(0xC3, 0x02, bytes([40, 20])))
    assert state.volume == 20
    state.apply(Frame(0xC3, 0x1D, b"\x00"))
    assert state.muted is False


def test_sound_modes() -> None:
    state = SoundbarState()
    state.apply(Frame(0xC3, 0x1F, b"\x00\x55"))
    assert state.sound_mode == 0x55
    state.apply(Frame(0xC3, 0x1F, b"\x05\x02\x55"))
    assert state.sound_modes == [0x02, 0x55]


def test_sound_mode_bitmap() -> None:
    state = SoundbarState()
    wanted = {2, 85, 144}
    bits = sum(1 << n for n, (value, _) in enumerate(SOUND_MODES) if value in wanted)
    state.apply(Frame(0xC3, 0x1F, b"\x02" + bits.to_bytes(8, "big")))
    assert set(state.sound_modes) == wanted


def test_levels_are_signed_with_range() -> None:
    state = SoundbarState()
    state.apply(Frame(0x0D, 0x1B, bytes([0xFD, 0xF4, 0x06])))
    assert state.levels[UtilityCommand.WOOFER_LEVEL] == Level(-3, -12, 6)
    state.apply(Frame(0x0D, 0x1B, bytes([0x02])))
    assert state.levels[UtilityCommand.WOOFER_LEVEL] == Level(2, -12, 6)
    state.apply(Frame(0x0D, 0x1A, bytes([0x96, 0x00, 0xC8])))
    assert state.levels[UtilityCommand.AV_SYNC] == Level(150, 0, 200)


def test_switches_and_night_mode() -> None:
    state = SoundbarState()
    state.apply(Frame(0x0D, 0x09, b"\x01"))
    state.apply(Frame(0xC3, 0x4A, b"\x01"))
    assert state.switches == {UtilityCommand.DRC_CONTROL: True}
    assert state.night_mode is True


def test_ignores_unknown_and_short_frames() -> None:
    state = SoundbarState()
    assert not state.apply(Frame(0x0D, 0x7F, b"\x01"))
    assert not state.apply(Frame(0xC3, 0x02, b"\x28"))
    assert not state.apply(Frame(0x0C, 0x01, b"\x01"))


def test_extended_feature_flags() -> None:
    state = SoundbarState()
    assert not state.supports(Feature.OPT_HDMI_ARC_SUPPORT)
    state.apply(Frame(0x00, 0x08, bytes([0x10, 0, 0, 0x40, 0, 0, 0, 0, 0, 0, 0])))
    assert state.supports(Feature.DRC_CONTROL)
    assert state.supports(Feature.OPT_HDMI_ARC_SUPPORT)
    assert not state.supports(Feature.AUTO_DISPLAY)


def test_short_extended_feature_list_is_ignored() -> None:
    state = SoundbarState()
    assert not state.apply(Frame(0x00, 0x08, bytes(10)))
    assert state.features is None


def test_feature_list() -> None:
    state = SoundbarState()
    assert state.extended_flags_available is None
    assert state.power_off_supported is None
    # The start of a real G1's feature list, padded to the length it sends.
    assert state.apply(Frame(0x00, 0x06, bytes([0x0C, 0x00, 0x01]) + bytes(102)))
    assert state.extended_flags_available is True
    assert state.firmware_info_available is True
    assert state.sleep_timer_supported is False
    assert state.power_off_supported is True
    state.apply(Frame(0x00, 0x06, bytes([0x00, 0x01, 0x00]) + bytes(62)))
    assert state.extended_flags_available is False
    assert state.firmware_info_available is False
    assert state.sleep_timer_supported is True
    assert state.power_off_supported is False


def test_short_feature_list_is_ignored() -> None:
    state = SoundbarState()
    assert not state.apply(Frame(0x00, 0x06, bytes([0x0C, 0x00, 0x01]) + bytes(61)))
    assert state.extended_flags_available is None


def test_emergency_check() -> None:
    state = SoundbarState()
    assert state.emergency is None
    state.apply(Frame(0x00, 0x16, b"\x00"))
    assert state.emergency is False
    state.apply(Frame(0x00, 0x16, b"\x01"))
    assert state.emergency is True


def test_second_extended_feature_flags() -> None:
    state = SoundbarState()
    assert not state.supports_2(Feature2.SUBWOOFER_STATE)
    state.apply(Frame(0x00, 0x24, bytes([0x01, 0x04, 0, 0, 0, 0x01])))
    assert state.supports_2(Feature2.SUBWOOFER_STATE)
    assert not state.supports_2(Feature2.REAR_SPEAKER_STATE)
    assert state.supports_2(Feature2.BUILT_IN_SUBWOOFER)
    assert state.supports_2(Feature2.REAR_CHANNEL_SWAP)


def test_selectable_functions_combine_optical_and_arc() -> None:
    state = SoundbarState(functions=[0x07, 0xC0, 0xD0, 0xC4])
    # Without the flag the inputs are listed as the soundbar reports them.
    assert state.selectable_functions == [0x07, 0xC0, 0xD0, 0xC4]
    state.features = frozenset({Feature.OPT_HDMI_ARC_SUPPORT})
    assert state.selectable_functions == [0x07, 0xC0, 0xDF]
    # A soundbar with no optical or ARC input gains none.
    state.functions = [0x07, 0xC0]
    assert state.selectable_functions == [0x07, 0xC0]


def test_offers_follows_feature_flags_once_reported() -> None:
    state = SoundbarState()
    state.apply(Frame(0x0D, 0x1E, b"\x00"))
    state.apply(Frame(0x0D, 0x09, b"\x01"))
    # Before the flags arrive, a setting is offered if the soundbar answered.
    assert state.offers(UtilityCommand.AUTO_DISPLAY)
    assert not state.offers(UtilityCommand.NEURAL_X)
    state.features = frozenset({Feature.DRC_CONTROL})
    assert state.offers(UtilityCommand.DRC_CONTROL)
    assert not state.offers(UtilityCommand.AUTO_DISPLAY)


def test_level_without_range_is_not_created() -> None:
    # The LG app ignores level replies without a range; so do we.
    state = SoundbarState()
    assert not state.apply(Frame(0x0D, 0x1A, bytes([0x14])))
    assert UtilityCommand.AV_SYNC not in state.levels
    state.apply(Frame(0x0D, 0x1A, bytes([0x00, 0x00, 0x1E])))
    # Once the range is known, a short reply updates the value.
    state.apply(Frame(0x0D, 0x1A, bytes([0x14])))
    assert state.levels[UtilityCommand.AV_SYNC] == Level(20, 0, 30)


def test_audio_format() -> None:
    state = SoundbarState()
    state.apply(Frame(0xD0, 0x72, b"Dolby Atmos\x00"))
    assert state.audio_info == "Dolby Atmos"
    state.apply(Frame(0xD0, 0x72, b""))
    assert state.audio_info is None


def test_tone_uses_the_app_range_until_one_is_reported() -> None:
    state = SoundbarState()
    state.apply(Frame(0xD0, 0x1F, bytes([0x03, 0xFE, 0x02])))
    assert state.bass == Level(-2, -5, 5)
    assert state.treble == Level(2, -5, 5)
    state.apply(Frame(0xD0, 0x1F, bytes([0x04, 0xFA, 0x06, 0, 0, 0xF9, 0x07])))
    assert state.bass == Level(-2, -6, 6)
    assert state.treble == Level(2, -7, 7)
    state.apply(Frame(0xD0, 0x1F, bytes([0x03, 0x01, 0x00])))
    assert state.bass == Level(1, -6, 6)


def test_sleep_timer_and_speaker_connections() -> None:
    state = SoundbarState()
    state.apply(Frame(0x0D, 0x14, bytes([0x01, 0x25])))
    assert state.sleep_timer == 37
    state.apply(Frame(0x0D, 0x14, bytes([0x00, 0x00])))
    assert state.sleep_timer == 0
    state.apply(Frame(0x0D, 0x25, b"\x01"))
    state.apply(Frame(0x0D, 0x43, b"\x00\x00"))
    assert (state.woofer_connected, state.rear_connected) == (True, False)
    # 0xff means the soundbar does not report it.
    state.apply(Frame(0x0D, 0x25, b"\xff"))
    assert state.woofer_connected is None


def test_input_connection_belongs_to_the_current_input() -> None:
    state = SoundbarState()
    state.apply(Frame(0x00, 0x0B, b"\xd0"))
    state.apply(Frame(0xD0, 0x3F, b"\xff"))
    assert state.input_connected is None
    state.apply(Frame(0xD0, 0x5F, b"\x01"))
    assert state.input_connected is True
    state.apply(Frame(0x00, 0x0B, b"\x07"))
    assert state.input_connected is None


def test_firmware_versions() -> None:
    def info(chip: int, name: str, version: str) -> bytes:
        data = bytearray(100)
        data[0], data[1] = chip, 0x07
        data[35], data[36:38] = 2, b"G1"
        data[51], data[52 : 52 + len(name)] = len(name), name.encode()
        data[67], data[68 : 68 + len(version)] = len(version), version.encode()
        return bytes(data)

    state = SoundbarState()
    # Bit 6 is a mode flag, not a chip.
    state.apply(Frame(0x0C, 0x00, bytes([0x00, 0xE0, 0x00])))
    assert state.firmware_chips == [5, 7]
    state.apply(Frame(0x0C, 0x01, info(5, "MICOM", "M2103110")))
    state.apply(Frame(0x0C, 0x01, info(7, "MAIN", "B210414A")))
    assert state.firmware_version == "MICOM M2103110, MAIN B210414A"
    assert state.model == "G1"


def test_three_tone_bands() -> None:
    state = SoundbarState()
    state.apply(Frame(0xD0, 0x1F, bytes([0x01, 0x01, 0xFF, 0x02])))
    assert state.three_band
    assert (state.bass, state.middle, state.treble) == (
        Level(1, -5, 5),
        Level(-1, -5, 5),
        Level(2, -5, 5),
    )
    state.apply(Frame(0xD0, 0x1F, bytes([0x04, 0xFA, 0x06, 0xFC, 0x04, 0xF9, 0x07])))
    assert state.middle == Level(-1, -4, 4)


def test_special_mode_locks_settings_as_the_app_does() -> None:
    state = SoundbarState()
    # Not reported: nothing is locked.
    assert state.locked_by(UtilityCommand.DIALOG_CONTROL) is None
    state.apply(Frame(0x0D, 0x2C, b"\x00"))
    assert state.special_mode is None
    # Dialog control is only available during DTS:X.
    assert state.locked_by(UtilityCommand.DIALOG_CONTROL) == SpecialEq.OFF
    state.apply(Frame(0x0D, 0x2C, b"\x01"))
    assert state.special_mode == SpecialEq.DOLBY_ATMOS
    assert state.locked_by(UtilityCommand.AUTO_VOLUME) == SpecialEq.DOLBY_ATMOS
    assert state.night_mode_locked_by == SpecialEq.DOLBY_ATMOS
    assert state.locked_by(UtilityCommand.REAR_LEVEL) is None
    state.apply(Frame(0x0D, 0x2C, b"\x02"))
    assert state.locked_by(UtilityCommand.DIALOG_CONTROL) is None
    state.apply(Frame(0x0D, 0x2C, b"\x03"))
    assert state.locked_by(UtilityCommand.CENTER_LEVEL) == SpecialEq.TV_SOUND_SHARE
    assert state.locked_by(UtilityCommand.AUTO_VOLUME) is None
    assert state.night_mode_locked_by is None


def test_night_mode_21y_flag_keeps_night_mode_during_atmos() -> None:
    state = SoundbarState(features=frozenset({Feature.NIGHT_MODE_21Y}))
    state.apply(Frame(0x0D, 0x2C, b"\x01"))
    assert state.night_mode_locked_by is None
