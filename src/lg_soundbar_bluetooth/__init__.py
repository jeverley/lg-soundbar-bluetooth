"""Control LG soundbars over Bluetooth."""

__version__ = "0.1.0"

from bluetooth_classic import normalize_address, rfcomm_supported

from .client import LGSoundbar
from .const import (
    LEVEL_COMMANDS,
    SETTING_FEATURES,
    SLEEP_TIMER_CHOICES,
    SPECIAL_EQ_NAMES,
    SPP_UUID,
    SWITCH_COMMANDS,
    Category,
    Feature,
    Feature2,
    Function,
    FunctionCommand,
    GeneralCommand,
    SpecialEq,
    UtilityCommand,
    function_name,
    sound_mode_name,
)
from .discovery import is_lg_soundbar, model_from_name
from .exceptions import (
    BluetoothUnsupported,
    CannotConnect,
    HandshakeFailed,
    LGSoundbarError,
    NotConnected,
)
from .naming import (
    current_function_name,
    function_for_name,
    offered_function_names,
    offered_sound_mode_names,
    sound_mode_for_name,
)
from .protocol import Frame, FrameParser, checksum
from .state import Level, SoundbarState

__all__ = [
    "LEVEL_COMMANDS",
    "SETTING_FEATURES",
    "SLEEP_TIMER_CHOICES",
    "SPECIAL_EQ_NAMES",
    "SPP_UUID",
    "SWITCH_COMMANDS",
    "BluetoothUnsupported",
    "CannotConnect",
    "Category",
    "Feature",
    "Feature2",
    "Frame",
    "FrameParser",
    "Function",
    "FunctionCommand",
    "GeneralCommand",
    "HandshakeFailed",
    "LGSoundbar",
    "LGSoundbarError",
    "Level",
    "NotConnected",
    "SoundbarState",
    "SpecialEq",
    "UtilityCommand",
    "checksum",
    "current_function_name",
    "function_for_name",
    "function_name",
    "is_lg_soundbar",
    "model_from_name",
    "normalize_address",
    "offered_function_names",
    "offered_sound_mode_names",
    "rfcomm_supported",
    "sound_mode_for_name",
    "sound_mode_name",
]
