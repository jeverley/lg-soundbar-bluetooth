"""Command tables for the LG soundbar Bluetooth serial protocol.

Every frame carries a major byte and a minor byte. The major byte is either a
category (general, utility, update) or the code of an input function; commands
that act on the current input (volume, mute, sound mode, night mode) are sent
with the current input's code as their major byte.
"""

from __future__ import annotations

from enum import IntEnum

SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"

FRAME_HEADER = b"AT"


class Category(IntEnum):
    """Major bytes that name a category rather than an input."""

    GENERAL = 0x00
    UPDATE = 0x0C
    UTILITY = 0x0D


class Function(IntEnum):
    """Input functions; also the major byte of commands for that input."""

    CD = 0x10
    BLUETOOTH = 0x07
    LG_TV = 0x09
    USB_1 = 0x40
    USB_2 = 0x41
    AUX = 0x50
    PORTABLE = 0x60
    FM = 0x81
    AM = 0x82
    DAB = 0x83
    TV_REAR = 0xB0
    TV_WOOFER = 0xB1
    HDMI_1 = 0xC0
    HDMI_2 = 0xC1
    HDMI_3 = 0xC2
    ARC = 0xC3
    EARC = 0xC4
    OPTICAL_1 = 0xD0
    OPTICAL_2 = 0xD1
    OPT_HDMI_ARC = 0xDF


class GeneralCommand(IntEnum):
    """Minor bytes used with the general category."""

    SET_MODE = 0x01
    WATCH_DOG = 0x02
    SUPPORTED_MODE = 0x04
    SUPPORTED_FEATURE_LISTS = 0x06
    STORAGE_STATE = 0x07
    EXTENDED_SUPPORTED_FEATURE_LISTS = 0x08
    POWER_CONTROL = 0x0A
    MODE = 0x0B
    ANDROID_CHECK_COMMAND = 0x15
    EMERGENCY_CHECK_COMMAND = 0x16
    SUPPORTED_FIRMWARE_CHIP_TYPE = 0x17
    MTK_BOOT_STATE = 0x18
    MODEL_TYPE_INFO = 0x19
    BT_ADDRESS_SUPPORT = 0x20
    MODEL_TYPE_INFO_NEW = 0x23
    EXTENDED_SUPPORTED_FEATURE_2_LISTS = 0x24


class FunctionCommand(IntEnum):
    """Minor bytes used with an input function's major byte."""

    VOLUME_CONTROL = 0x02
    CURR_FEATURE_STATE = 0x03
    MUTE = 0x1D
    EQ = 0x1F
    LG_OPT_CONNECT_STATE = 0x3F
    NIGHT_MODE = 0x4A
    LG_TV_CONNECT_STATE = 0x52
    OPTICAL_CONNECT_STATE = 0x5F
    ARC_CONNECT_STATE = 0x66
    AUDIO_INFO = 0x72


class UpdateCommand(IntEnum):
    """Minor bytes used with the update category (read-only queries only)."""

    FIRMWARE_TYPE = 0x00
    FIRMWARE_INFO = 0x01
    FIRMWARE_TYPE_NEW = 0x07


# Second byte of a FIRMWARE_INFO query: ask for every field.
FIRMWARE_INFO_ALL = 0x07

# Chips named by the bits of a FIRMWARE_TYPE reply, as the LG app names them;
# each chip's number is its bit position.
FIRMWARE_CHIPS: dict[int, str] = {
    0: "PEQ",
    1: "TOUCH",
    2: "DSP",
    3: "SUB",
    4: "DJ Sound",
    5: "MICOM",
    7: "MAIN",
}
# Bit 6 of a FIRMWARE_TYPE reply is a mode flag, not a chip.
FIRMWARE_MANUAL_MODE_BIT = 6

# Which connection state the LG app asks for on each input.
CONNECT_STATE_COMMANDS: dict[int, tuple[int, ...]] = {
    Function.ARC: (FunctionCommand.ARC_CONNECT_STATE,),
    Function.EARC: (FunctionCommand.ARC_CONNECT_STATE,),
    Function.OPTICAL_1: (
        FunctionCommand.LG_OPT_CONNECT_STATE,
        FunctionCommand.OPTICAL_CONNECT_STATE,
    ),
    Function.OPTICAL_2: (
        FunctionCommand.LG_OPT_CONNECT_STATE,
        FunctionCommand.OPTICAL_CONNECT_STATE,
    ),
    Function.OPT_HDMI_ARC: (
        FunctionCommand.LG_OPT_CONNECT_STATE,
        FunctionCommand.OPTICAL_CONNECT_STATE,
        FunctionCommand.ARC_CONNECT_STATE,
    ),
    Function.LG_TV: (FunctionCommand.LG_TV_CONNECT_STATE,),
}


class SpecialEq(IntEnum):
    """A special sound mode the soundbar switched to, overriding the chosen one.

    The soundbar engages Dolby Atmos or DTS:X processing for such content, and
    TV sound mode share when an LG TV controls the sound mode. The LG app then
    shows it as the sound effect and locks some settings.
    """

    OFF = 0
    DOLBY_ATMOS = 1
    DTS_X = 2
    TV_SOUND_SHARE = 3


SPECIAL_EQ_NAMES: dict[int, str] = {
    SpecialEq.DOLBY_ATMOS: "Dolby Atmos",
    SpecialEq.DTS_X: "DTS:X",
    SpecialEq.TV_SOUND_SHARE: "Synced with TV",
}


# The LG app's tone control range when a soundbar reports none, for any model.
DEFAULT_TONE_RANGE = (-5, 5)

# Sleep timer choices the LG app offers, in minutes.
SLEEP_TIMER_CHOICES: tuple[int, ...] = (
    10,
    20,
    30,
    40,
    50,
    60,
    70,
    80,
    90,
    120,
    150,
    180,
)


class UtilityCommand(IntEnum):
    """Minor bytes used with the utility category."""

    DRC_CONTROL = 0x09
    SLEEP_TIMER_SETTING = 0x14
    TV_REMOTE_CONTROL_USE = 0x19
    AV_SYNC = 0x1A
    WOOFER_LEVEL = 0x1B
    AUTO_VOLUME = 0x1C
    AUTO_POWER = 0x1D
    AUTO_DISPLAY = 0x1E
    REAR_LEVEL = 0x21
    SURROUND_SETTING = 0x22
    WOOFER_STATE = 0x25
    CENTER_LEVEL = 0x26
    SIDE_LEVEL = 0x27
    UPWARD_LEVEL = 0x29
    NEURAL_X = 0x2A
    DIALOG_CONTROL = 0x2B
    SPECIAL_EQ = 0x2C
    REAR_STATE = 0x43


class Feature(IntEnum):
    """Flags in the extended feature list, numbered byte * 8 + bit."""

    DRC_CONTROL = 0 * 8 + 4
    TONE_CONTROL = 1 * 8 + 0
    NIGHT_MODE = 1 * 8 + 7
    TV_REMOTE_CONTROL_USE = 3 * 8 + 0
    AV_SYNC = 3 * 8 + 1
    WOOFER_LEVEL = 3 * 8 + 2
    AUTO_VOLUME = 3 * 8 + 3
    AUTO_POWER = 3 * 8 + 4
    AUTO_DISPLAY = 3 * 8 + 5
    # Optical, HDMI ARC and eARC are one input, selected with OPT_HDMI_ARC.
    OPT_HDMI_ARC_SUPPORT = 3 * 8 + 6
    REAR_LEVEL = 3 * 8 + 7
    NIGHT_TIME = 4 * 8 + 7
    SURROUND_SETTING = 5 * 8 + 0
    SIDE_LEVEL = 5 * 8 + 6
    CENTER_LEVEL = 5 * 8 + 7
    UPWARD_LEVEL = 6 * 8 + 5
    NEURAL_X = 6 * 8 + 6
    DIALOG_CONTROL = 6 * 8 + 7
    SPECIAL_EQ = 7 * 8 + 0
    NIGHT_MODE_21Y = 7 * 8 + 6
    MODEL_TYPE_NEW = 9 * 8 + 1
    AUDIO_INFO = 9 * 8 + 2
    FIRMWARE_INFO_NEW = 9 * 8 + 6
    # The second extended feature list (00/24) can be asked for.
    EXTENDED_FEATURES_2 = 9 * 8 + 7


# The feature flag each setting needs, as the LG app checks before offering it.
SETTING_FEATURES: dict[UtilityCommand, Feature] = {
    UtilityCommand.DRC_CONTROL: Feature.DRC_CONTROL,
    UtilityCommand.TV_REMOTE_CONTROL_USE: Feature.TV_REMOTE_CONTROL_USE,
    UtilityCommand.AV_SYNC: Feature.AV_SYNC,
    UtilityCommand.WOOFER_LEVEL: Feature.WOOFER_LEVEL,
    UtilityCommand.AUTO_VOLUME: Feature.AUTO_VOLUME,
    UtilityCommand.AUTO_POWER: Feature.AUTO_POWER,
    UtilityCommand.AUTO_DISPLAY: Feature.AUTO_DISPLAY,
    UtilityCommand.REAR_LEVEL: Feature.REAR_LEVEL,
    UtilityCommand.SURROUND_SETTING: Feature.SURROUND_SETTING,
    UtilityCommand.SIDE_LEVEL: Feature.SIDE_LEVEL,
    UtilityCommand.CENTER_LEVEL: Feature.CENTER_LEVEL,
    UtilityCommand.UPWARD_LEVEL: Feature.UPWARD_LEVEL,
    UtilityCommand.NEURAL_X: Feature.NEURAL_X,
    UtilityCommand.DIALOG_CONTROL: Feature.DIALOG_CONTROL,
}

# Number of flag bytes at the start of the extended feature list.
FEATURE_FLAG_BYTES = 10

# The LG app only reads a feature list (00/06) of at least this many bytes.
FEATURE_LIST_MIN_LENGTH = 65
# Feature list byte 0: firmware details (0c/00) can be asked for.
FEATURE_LIST_FIRMWARE_INFO = 0x04
# Feature list byte 0: the extended feature flags (00/08) can be asked for.
FEATURE_LIST_EXTENDED_FLAGS = 0x08


class Feature2(IntEnum):
    """Flags in the second extended feature list (00/24), byte * 8 + bit."""

    SUBWOOFER_STATE = 0 * 8 + 0
    REAR_SPEAKER_STATE = 0 * 8 + 1
    SPEAKER_MUTE_SOUND_CHECK = 0 * 8 + 2
    BUILT_IN_SUBWOOFER = 1 * 8 + 2
    LED_DISPLAY = 1 * 8 + 5
    UP_MIXER = 3 * 8 + 5
    WOW_INTERFACE = 3 * 8 + 6
    WOW_ORCHESTRA = 4 * 8 + 2
    REAR_CHANNEL_SWAP = 5 * 8 + 0
    BLE_ADDRESS = 5 * 8 + 3
    THINQ_APP = 5 * 8 + 4
    USAGE_STATISTICS = 5 * 8 + 5


# Inputs shown as the single Optical/HDMI ARC input when a soundbar has
# OPT_HDMI_ARC_SUPPORT, as the LG app does.
COMBINED_ARC_FUNCTIONS: frozenset[int] = frozenset(
    {Function.OPTICAL_1, Function.ARC, Function.EARC, Function.OPT_HDMI_ARC}
)


class EqCommand(IntEnum):
    """First payload byte of an EQ frame."""

    CURRENT_EQ_INDEX = 0x00
    USER_EQ_VALUE_3BAND = 0x01
    SUPPORTED_EQ_LIST = 0x02
    USER_EQ_VALUE_2BAND = 0x03
    USER_EQ_MIN_MAX = 0x04
    SUPPORTED_EQ_NEW_LIST = 0x05


# Settings answered as (value, minimum, maximum).
LEVEL_COMMANDS: frozenset[UtilityCommand] = frozenset(
    {
        UtilityCommand.AV_SYNC,
        UtilityCommand.WOOFER_LEVEL,
        UtilityCommand.REAR_LEVEL,
        UtilityCommand.CENTER_LEVEL,
        UtilityCommand.SIDE_LEVEL,
        UtilityCommand.UPWARD_LEVEL,
        UtilityCommand.DIALOG_CONTROL,
    }
)

# Levels whose bytes are unsigned; the others are signed.
UNSIGNED_LEVEL_COMMANDS: frozenset[UtilityCommand] = frozenset({UtilityCommand.AV_SYNC})

# Settings answered as a single on/off byte.
SWITCH_COMMANDS: frozenset[UtilityCommand] = frozenset(
    {
        UtilityCommand.DRC_CONTROL,
        UtilityCommand.AUTO_VOLUME,
        UtilityCommand.AUTO_POWER,
        UtilityCommand.AUTO_DISPLAY,
        UtilityCommand.SURROUND_SETTING,
        UtilityCommand.NEURAL_X,
        UtilityCommand.TV_REMOTE_CONTROL_USE,
    }
)

# Bitmask of firmware chip types the app says it supports during the handshake.
SUPPORTED_CHIP_TYPES = 0x1F

# The LG app assumes this maximum volume until the soundbar reports its own.
DEFAULT_VOLUME_MAX = 40

# Display names follow the existing LG Soundbars integration where it has a
# name for the same input, so automations read the same across both.
FUNCTION_NAMES: dict[int, str] = {
    Function.BLUETOOTH: "Bluetooth",
    Function.LG_TV: "LG TV",
    Function.USB_1: "USB",
    Function.USB_2: "USB2",
    Function.AUX: "Aux",
    Function.PORTABLE: "Portable",
    Function.CD: "CD",
    Function.FM: "FM",
    Function.AM: "AM",
    Function.DAB: "DAB",
    Function.TV_REAR: "TV Rear",
    Function.TV_WOOFER: "TV Woofer",
    Function.HDMI_1: "HDMI",
    Function.HDMI_2: "HDMI2",
    Function.HDMI_3: "HDMI3",
    Function.ARC: "ARC",
    Function.EARC: "E-ARC",
    Function.OPTICAL_1: "Optical",
    Function.OPTICAL_2: "Optical2",
    Function.OPT_HDMI_ARC: "Optical/HDMI ARC",
}

# Inputs a soundbar may report under a different code from the one used to
# select them; selecting Optical/HDMI ARC (0xdf) is reported back as 0xd0.
EQUIVALENT_FUNCTIONS: tuple[tuple[int, ...], ...] = (
    (
        Function.OPT_HDMI_ARC,
        Function.EARC,
        Function.ARC,
        Function.OPTICAL_1,
        Function.OPTICAL_2,
    ),
    (Function.HDMI_1, Function.HDMI_2, Function.HDMI_3),
    (Function.USB_1, Function.USB_2),
    (Function.BLUETOOTH, Function.PORTABLE),
)

# Sound modes in the order the soundbar's supported-list bitmap uses them.
# Each entry is (value, display name); names follow the existing LG Soundbars
# integration where it has one for the same mode, otherwise the LG app's.
SOUND_MODES: tuple[tuple[int, str], ...] = (
    (0, "Bypass"),
    (1, "Natural"),
    (2, "Standard"),
    (3, "Natural Plus"),
    (4, "Cumbia"),
    (5, "Afro"),
    (6, "Music Retouch"),
    (7, "Loudness"),
    (17, "Dangdut"),
    (18, "Arabic"),
    (19, "Persian"),
    (20, "India"),
    (21, "Regueton"),
    (22, "Samba"),
    (23, "Salsa"),
    (24, "Merengue"),
    (25, "RSD"),
    (26, "Forro"),
    (27, "Funk"),
    (28, "Sertanejo"),
    (29, "Football"),
    (48, "Auto EQ"),
    (49, "User"),
    (50, "Rock"),
    (51, "Pop"),
    (52, "Jazz"),
    (53, "Classic"),
    (54, "MP3-OPT"),
    (55, "Bass Blast"),
    (56, "Music"),
    (81, "Bass Blast"),
    (82, "Clear Voice"),
    (83, "Night"),
    (84, "Game"),
    (85, "Cinema"),
    (86, "3D Sound"),
    (87, "MP3 Upscaler"),
    (113, "Virtual"),
    (114, "PL2 Movie"),
    (115, "PL2 Music"),
    (116, "PL2 Matrix"),
    (30, "Flat"),
    (31, "Boost"),
    (32, "Treble and Bass"),
    (117, "User"),
    (118, "Bass"),
    (57, "Voice"),
    (33, "Axe"),
    (34, "Tecno Brega"),
    (35, "Banda"),
    (129, "Adaptive Sound Control"),
    (130, "Adaptive Sound Control"),
    (131, "DTS Virtual X"),
    (132, "On"),
    (133, "Off"),
    (134, "Bass Blast+"),
    (135, "Meridian"),
    (136, "Sound Boost"),
    (137, "Movie"),
    (144, "AI Sound Pro"),
    (145, "Custom"),
    (146, "Sports"),
    (151, "Clear Voice Pro"),
)

SOUND_MODE_NAMES: dict[int, str] = dict(SOUND_MODES)


def function_name(code: int) -> str:
    """Return the display name of an input function code."""
    return FUNCTION_NAMES.get(code, f"Unknown ({code})")


def sound_mode_name(value: int) -> str:
    """Return the display name of a sound mode value."""
    return SOUND_MODE_NAMES.get(value, f"Unknown ({value})")
