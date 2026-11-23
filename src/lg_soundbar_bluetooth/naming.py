"""Display names for inputs and sound modes, matching the LG Soundbars integration.

Like that integration, only what the soundbar says it offers is listed, codes
without a known name are shown as "Unknown (n)" rather than dropped, and an
input reported under a different code from the one used to select it is shown
as its offered equivalent.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .const import (
    EQUIVALENT_FUNCTIONS,
    FUNCTION_NAMES,
    SOUND_MODE_NAMES,
    function_name,
    sound_mode_name,
)


def _offered_names(offered: Iterable[int], name_of: Callable[[int], str]) -> list[str]:
    return sorted({name_of(code) for code in offered})


def _resolve(
    name: str,
    offered: Iterable[int],
    name_of: Callable[[int], str],
    all_codes: Iterable[int],
) -> int:
    for code in offered:
        if name_of(code) == name:
            return code
    for code in all_codes:
        if name_of(code) == name:
            return code
    if name.startswith("Unknown (") and name.endswith(")"):
        digits = name[len("Unknown (") : -1]
        if digits.isdigit() and int(digits) <= 0xFF:
            return int(digits)
    raise ValueError(f"Unknown name: {name}")


def offered_function_names(offered: Iterable[int]) -> list[str]:
    """Return the sorted names of the offered inputs."""
    return _offered_names(offered, function_name)


def current_function_name(function: int | None, offered: Iterable[int]) -> str | None:
    """Return the name to show for the current input."""
    if function is None:
        return None
    offered = list(offered)
    if not offered or function in offered:
        return function_name(function)
    group = next((codes for codes in EQUIVALENT_FUNCTIONS if function in codes), ())
    equivalent = next((code for code in group if code in offered), function)
    return function_name(equivalent)


def function_for_name(name: str, offered: Iterable[int]) -> int:
    """Return the input code a name refers to."""
    return _resolve(name, offered, function_name, FUNCTION_NAMES)


def offered_sound_mode_names(offered: Iterable[int]) -> list[str]:
    """Return the sorted names of the offered sound modes."""
    return _offered_names(offered, sound_mode_name)


def sound_mode_for_name(name: str, offered: Iterable[int]) -> int:
    """Return the sound mode value a name refers to."""
    return _resolve(name, offered, sound_mode_name, SOUND_MODE_NAMES)
