"""Soundbar state built from the frames the soundbar sends."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .const import (
    COMBINED_ARC_FUNCTIONS,
    DEFAULT_TONE_RANGE,
    FEATURE_FLAG_BYTES,
    FEATURE_LIST_EXTENDED_FLAGS,
    FEATURE_LIST_FIRMWARE_INFO,
    FEATURE_LIST_MIN_LENGTH,
    FIRMWARE_CHIPS,
    FIRMWARE_MANUAL_MODE_BIT,
    LEVEL_COMMANDS,
    SETTING_FEATURES,
    SOUND_MODES,
    SWITCH_COMMANDS,
    UNSIGNED_LEVEL_COMMANDS,
    Category,
    EqCommand,
    Feature,
    Feature2,
    Function,
    FunctionCommand,
    GeneralCommand,
    SpecialEq,
    UpdateCommand,
    UtilityCommand,
)
from .protocol import Frame

_LOGGER = logging.getLogger(__name__)

# Size of the supported-sound-mode bitmap that follows its sub-command byte.
SOUND_MODE_BITMAP_SIZE = 8

# Connection states answered for the current input.
CONNECT_STATE_MINORS = frozenset(
    {
        FunctionCommand.LG_OPT_CONNECT_STATE,
        FunctionCommand.LG_TV_CONNECT_STATE,
        FunctionCommand.OPTICAL_CONNECT_STATE,
        FunctionCommand.ARC_CONNECT_STATE,
    }
)

# Offsets in a FIRMWARE_INFO reply, each text preceded by its length.
FIRMWARE_MODEL = 35
FIRMWARE_TYPE_TEXT = 51
FIRMWARE_IMAGE_VERSION = 67


def _text(data: bytes) -> str:
    return data.decode("utf-8", "replace").replace("\x00", "").strip()


def _length_prefixed(payload: bytes, offset: int) -> str:
    if len(payload) <= offset:
        return ""
    return _text(payload[offset + 1 : offset + 1 + payload[offset]])


def _connected(value: int) -> bool | None:
    """Return a connection state; anything but 0 or 1 means not supported."""
    return {0: False, 1: True}.get(value)


def _flags(payload: bytes, size: int) -> frozenset[int]:
    """Return the flags set in the first size bytes, as byte * 8 + bit."""
    return frozenset(
        byte * 8 + bit
        for byte in range(size)
        for bit in range(8)
        if payload[byte] >> bit & 1
    )


def _signed(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


@dataclass(slots=True)
class Level:
    """A setting reported as a value with its own range."""

    value: int
    minimum: int
    maximum: int


@dataclass(slots=True)
class SoundbarState:
    """Everything the soundbar has reported so far."""

    function: int | None = None
    functions: list[int] = field(default_factory=list)
    volume: int | None = None
    volume_max: int | None = None
    muted: bool | None = None
    sound_mode: int | None = None
    sound_modes: list[int] = field(default_factory=list)
    night_mode: bool | None = None
    levels: dict[UtilityCommand, Level] = field(default_factory=dict)
    switches: dict[UtilityCommand, bool] = field(default_factory=dict)
    model_type: int | None = None
    # From MODEL_TYPE_INFO_NEW, as the LG app reads it: model type, model
    # number and option; None until reported.
    model_type_new: tuple[int, int, int] | None = None
    # From the feature list (00/06), each None until reported: whether the
    # extended feature flags (00/08) and firmware details (0c/00) can be asked
    # for, and whether the LG app offers its sleep timer and power off.
    extended_flags_available: bool | None = None
    firmware_info_available: bool | None = None
    sleep_timer_supported: bool | None = None
    power_off_supported: bool | None = None
    # Whether the soundbar is in emergency mode (left so by a failed firmware
    # update, needing the LG app's recovery update), or None until reported.
    emergency: bool | None = None
    # Extended feature flags (byte * 8 + bit), or None until reported.
    features: frozenset[int] | None = None
    # Second extended feature flags (00/24), or None until reported.
    features_2: frozenset[int] | None = None
    # Current audio format as text, such as "Dolby Atmos".
    audio_info: str | None = None
    bass: Level | None = None
    middle: Level | None = None
    treble: Level | None = None
    # True once the soundbar reports three tone bands rather than two.
    three_band: bool = False
    # The special sound mode in effect (a SpecialEq), or None if not reported.
    special_eq: int | None = None
    # Minutes until the soundbar turns itself off; 0 when the timer is off.
    sleep_timer: int | None = None
    woofer_connected: bool | None = None
    rear_connected: bool | None = None
    # Connection states the current input reported, by command.
    connect_states: dict[int, bool] = field(default_factory=dict)
    firmware_chips: list[int] = field(default_factory=list)
    # Whether the chips came from FIRMWARE_TYPE_NEW, whose chips the LG app
    # names by the type text in their details rather than by number.
    firmware_chips_new: bool = False
    # Image version by chip name, such as {"MAIN": "B210414A"}.
    firmware: dict[str, str] = field(default_factory=dict)
    # The model the firmware details name, such as "G1".
    model: str | None = None

    @property
    def special_mode(self) -> SpecialEq | None:
        """Return the special sound mode in effect, if any."""
        if self.special_eq is None or self.special_eq == SpecialEq.OFF:
            return None
        try:
            return SpecialEq(self.special_eq)
        except ValueError:
            return None

    def locked_by(self, command: UtilityCommand) -> SpecialEq | None:
        """Return the special mode that locks a setting, as the LG app does.

        Auto volume is locked during Dolby Atmos and DTS:X, dialog control is
        only available during DTS:X, and the center, rear and side levels are
        locked while an LG TV shares its sound mode.
        """
        if self.special_eq is None:
            return None
        mode = self.special_mode
        if command == UtilityCommand.AUTO_VOLUME and mode in (
            SpecialEq.DOLBY_ATMOS,
            SpecialEq.DTS_X,
        ):
            return mode
        if command == UtilityCommand.DIALOG_CONTROL and mode != SpecialEq.DTS_X:
            return mode or SpecialEq.OFF
        if (
            command
            in (
                UtilityCommand.CENTER_LEVEL,
                UtilityCommand.REAR_LEVEL,
                UtilityCommand.SIDE_LEVEL,
            )
            and mode == SpecialEq.TV_SOUND_SHARE
        ):
            return mode
        return None

    @property
    def night_mode_locked_by(self) -> SpecialEq | None:
        """Return the special mode that locks night mode, as the LG app does.

        Night mode is locked during Dolby Atmos and DTS:X unless the soundbar
        has the 2021 night mode flag.
        """
        mode = self.special_mode
        if mode in (SpecialEq.DOLBY_ATMOS, SpecialEq.DTS_X) and not self.supports(
            Feature.NIGHT_MODE_21Y
        ):
            return mode
        return None

    @property
    def input_connected(self) -> bool | None:
        """Return whether the current input's link (TV, cable) is connected."""
        if not self.connect_states:
            return None
        return any(self.connect_states.values())

    @property
    def firmware_version(self) -> str | None:
        """Return the firmware versions as the LG app lists them."""
        if not self.firmware:
            return None
        return ", ".join(f"{chip} {version}" for chip, version in self.firmware.items())

    def supports(self, feature: Feature) -> bool:
        """Return whether the soundbar reported a feature flag."""
        return self.features is not None and feature in self.features

    def supports_2(self, feature: Feature2) -> bool:
        """Return whether the soundbar reported a second extended feature flag."""
        return self.features_2 is not None and feature in self.features_2

    @property
    def asks_woofer_state(self) -> bool:
        """Return whether the subwoofer's connection state is asked for."""
        return self._asks_speaker_state(Feature2.SUBWOOFER_STATE, Feature.WOOFER_LEVEL)

    @property
    def asks_rear_state(self) -> bool:
        """Return whether the rear speakers' connection state is asked for."""
        return self._asks_speaker_state(Feature2.REAR_SPEAKER_STATE, Feature.REAR_LEVEL)

    def _asks_speaker_state(self, notify: Feature2, level: Feature) -> bool:
        """Return whether a speaker's connection state is asked for.

        The LG app asks only with the notify flag in the second extended
        feature list; this also asks when the soundbar has the speaker's
        level, as a G1 has no second list but reports its subwoofer. (That
        the level flag means a separate speaker, not a built-in one, is
        unconfirmed.) Until the flags are known, everything is asked for.
        """
        return (
            self.features is None or level in self.features or self.supports_2(notify)
        )

    def offers(self, command: UtilityCommand) -> bool:
        """Return whether the soundbar offers a setting, as the LG app judges it.

        Once the soundbar has reported its feature flags they decide, as only
        flagged settings are asked for then. Without flags, every setting is
        asked for, and one it answered is offered; a soundbar may answer for
        a setting it does not have (an LG G1 answered for auto display,
        overhead level and Neural:X when asked).
        """
        if command not in self.levels and command not in self.switches:
            return False
        if self.features is None or (feature := SETTING_FEATURES.get(command)) is None:
            return True
        return feature in self.features

    @property
    def offers_night_mode(self) -> bool:
        """Return whether the soundbar offers night mode."""
        if self.night_mode is None:
            return False
        return self.features is None or Feature.NIGHT_MODE in self.features

    @property
    def selectable_functions(self) -> list[int]:
        """Return the inputs to offer, combined the way the LG app shows them.

        A soundbar with OPT_HDMI_ARC_SUPPORT reports Optical, HDMI ARC and
        eARC separately but takes them as one input, selected with
        OPT_HDMI_ARC; the LG app shows that one "Optical/HDMI ARC" input.
        """
        if not self.supports(Feature.OPT_HDMI_ARC_SUPPORT) or not (
            COMBINED_ARC_FUNCTIONS & set(self.functions)
        ):
            return list(self.functions)
        selectable = [f for f in self.functions if f not in COMBINED_ARC_FUNCTIONS]
        return [*selectable, Function.OPT_HDMI_ARC]

    def apply(self, frame: Frame) -> bool:
        """Update the state from a frame and return whether anything changed."""
        before = self._snapshot()
        if frame.major == Category.GENERAL:
            self._apply_general(frame)
        elif frame.major == Category.UTILITY:
            self._apply_utility(frame)
        elif frame.major == Category.UPDATE:
            self._apply_update(frame)
        else:
            self._apply_function(frame)
        return self._snapshot() != before

    def _snapshot(self) -> str:
        # The dataclass repr covers every field, nested levels included.
        return repr(self)

    def _apply_general(self, frame: Frame) -> None:
        payload = frame.payload
        if not payload:
            return
        if frame.minor in (GeneralCommand.MODE, GeneralCommand.SET_MODE):
            if payload[0] != self.function:
                # Connection states belong to the input they were asked for.
                self.connect_states = {}
            self.function = payload[0]
        elif frame.minor == GeneralCommand.SUPPORTED_MODE:
            self.functions = list(payload)
        elif frame.minor == GeneralCommand.EMERGENCY_CHECK_COMMAND:
            self.emergency = payload[0] == 1
        elif frame.minor == GeneralCommand.MODEL_TYPE_INFO_NEW and len(payload) >= 4:
            self.model_type_new = (
                payload[0],
                payload[1] << 8 | payload[2],
                payload[3],
            )
        elif frame.minor == GeneralCommand.MODEL_TYPE_INFO:
            self.model_type = payload[0]
        elif (
            frame.minor == GeneralCommand.SUPPORTED_FEATURE_LISTS
            and len(payload) >= FEATURE_LIST_MIN_LENGTH
        ):
            self.extended_flags_available = bool(
                payload[0] & FEATURE_LIST_EXTENDED_FLAGS
            )
            self.firmware_info_available = bool(payload[0] & FEATURE_LIST_FIRMWARE_INFO)
            self.sleep_timer_supported = payload[1] == 1
            self.power_off_supported = payload[2] == 1
        elif frame.minor == GeneralCommand.EXTENDED_SUPPORTED_FEATURE_2_LISTS:
            self.features_2 = _flags(payload, len(payload))
        elif (
            frame.minor == GeneralCommand.EXTENDED_SUPPORTED_FEATURE_LISTS
            and len(payload) > FEATURE_FLAG_BYTES
        ):
            self.features = _flags(payload, FEATURE_FLAG_BYTES)

    def _apply_utility(self, frame: Frame) -> None:
        payload = frame.payload
        if not payload:
            return
        try:
            command = UtilityCommand(frame.minor)
        except ValueError:
            return
        if command in LEVEL_COMMANDS:
            convert = (lambda b: b) if command in UNSIGNED_LEVEL_COMMANDS else _signed
            values = [convert(b) for b in payload[:3]]
            if len(values) >= 3:
                self.levels[command] = Level(*values)
            elif (previous := self.levels.get(command)) is not None:
                # A short reply only updates a level whose range is known; as in
                # the LG app, a level without a reported range is not created.
                previous.value = values[0]
        elif command in SWITCH_COMMANDS:
            self.switches[command] = payload[0] == 1
        elif command == UtilityCommand.SLEEP_TIMER_SETTING and len(payload) >= 2:
            self.sleep_timer = payload[1] if payload[0] == 1 else 0
        elif command == UtilityCommand.SPECIAL_EQ:
            self.special_eq = None if payload[0] == 0xFF else payload[0]
        elif command == UtilityCommand.WOOFER_STATE:
            self.woofer_connected = _connected(payload[0])
        elif command == UtilityCommand.REAR_STATE:
            self.rear_connected = _connected(payload[0])

    def _apply_update(self, frame: Frame) -> None:
        """Read firmware details; nothing here changes the soundbar."""
        payload = frame.payload
        if frame.minor == UpdateCommand.FIRMWARE_TYPE and len(payload) == 3:
            self.firmware_chips = [
                bit
                for bit in range(8)
                if payload[1] >> bit & 1 and bit != FIRMWARE_MANUAL_MODE_BIT
            ]
            self.firmware_chips_new = False
        elif frame.minor == UpdateCommand.FIRMWARE_TYPE_NEW and len(payload) >= 3:
            # Chip numbers listed one by one from byte 2, rather than a mask.
            self.firmware_chips = list(payload[2:])
            self.firmware_chips_new = True
        elif frame.minor == UpdateCommand.FIRMWARE_INFO and len(payload) > 1:
            chip = payload[0]
            text = _length_prefixed(payload, FIRMWARE_TYPE_TEXT)
            if self.firmware_chips_new:
                name = text or FIRMWARE_CHIPS.get(chip)
            else:
                name = FIRMWARE_CHIPS.get(chip) or text
            if model := _length_prefixed(payload, FIRMWARE_MODEL):
                self.model = model
            if version := _length_prefixed(payload, FIRMWARE_IMAGE_VERSION):
                self.firmware[name or f"Chip {chip}"] = version

    def _apply_function(self, frame: Frame) -> None:
        payload = frame.payload
        minor = frame.minor
        if minor == FunctionCommand.VOLUME_CONTROL and len(payload) >= 2:
            self.volume_max = payload[0]
            self.volume = payload[1]
        elif minor == FunctionCommand.CURR_FEATURE_STATE and len(payload) >= 4:
            self.muted = bool(payload[1] & 1)
            self.volume_max = payload[2]
            self.volume = payload[3]
        elif minor == FunctionCommand.MUTE and payload:
            self.muted = payload[0] == 1
        elif minor == FunctionCommand.NIGHT_MODE and payload:
            self.night_mode = payload[0] == 1
        elif minor == FunctionCommand.EQ and payload:
            self._apply_eq(payload)
        elif minor == FunctionCommand.AUDIO_INFO:
            self.audio_info = _text(payload) or None
        elif (
            minor in CONNECT_STATE_MINORS
            and payload
            and (connected := _connected(payload[0])) is not None
        ):
            self.connect_states[minor] = connected

    def _apply_eq(self, payload: bytes) -> None:
        command, data = payload[0], payload[1:]
        if command == EqCommand.CURRENT_EQ_INDEX and data:
            self.sound_mode = data[0]
        elif command == EqCommand.USER_EQ_VALUE_3BAND and len(data) >= 3:
            self.three_band = True
            self.bass = self._tone(self.bass, _signed(data[0]))
            self.middle = self._tone(self.middle, _signed(data[1]))
            self.treble = self._tone(self.treble, _signed(data[2]))
        elif command == EqCommand.USER_EQ_VALUE_2BAND and len(data) >= 2:
            self.bass = self._tone(self.bass, _signed(data[0]))
            self.treble = self._tone(self.treble, _signed(data[1]))
        elif command == EqCommand.USER_EQ_MIN_MAX and len(data) >= 6:
            # Bass, middle and treble ranges.
            values = [_signed(b) for b in data[:6]]
            self.bass = self._range(self.bass, values[0], values[1])
            self.treble = self._range(self.treble, values[4], values[5])
            if self.three_band:
                self.middle = self._range(self.middle, values[2], values[3])
        elif command == EqCommand.SUPPORTED_EQ_NEW_LIST and data:
            self.sound_modes = list(data)
        elif (
            command == EqCommand.SUPPORTED_EQ_LIST
            and len(data) >= SOUND_MODE_BITMAP_SIZE
        ):
            # Big-endian bitmap: bit n is the nth entry of SOUND_MODES.
            bits = int.from_bytes(data[:SOUND_MODE_BITMAP_SIZE], "big")
            self.sound_modes = [
                value for n, (value, _) in enumerate(SOUND_MODES) if bits >> n & 1
            ]

    @staticmethod
    def _tone(previous: Level | None, value: int) -> Level:
        if previous is not None:
            return Level(value, previous.minimum, previous.maximum)
        # The LG app's range for any soundbar that reports none.
        return Level(value, *DEFAULT_TONE_RANGE)

    @staticmethod
    def _range(previous: Level | None, minimum: int, maximum: int) -> Level:
        return Level(0 if previous is None else previous.value, minimum, maximum)
