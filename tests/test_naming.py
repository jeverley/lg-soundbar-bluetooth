"""Tests for input and sound mode names."""

from __future__ import annotations

import pytest

from lg_soundbar_bluetooth import (
    current_function_name,
    function_for_name,
    offered_function_names,
    offered_sound_mode_names,
    sound_mode_for_name,
)


def test_function_names() -> None:
    offered = [0x07, 0xC3, 0xDF, 0xEE]
    assert offered_function_names(offered) == [
        "ARC",
        "Bluetooth",
        "Optical/HDMI ARC",
        "Unknown (238)",
    ]
    assert function_for_name("Optical/HDMI ARC", offered) == 0xDF
    assert function_for_name("Unknown (238)", offered) == 0xEE


def test_reported_code_maps_to_offered_equivalent() -> None:
    # Selecting Optical/HDMI ARC (0xdf) is reported back as Optical (0xd0).
    assert current_function_name(0xD0, [0x07, 0xDF]) == "Optical/HDMI ARC"
    # The G1 reports HDMI eARC (or Optical) while it is on Optical/HDMI ARC.
    assert current_function_name(0xD0, [0x07, 0x09, 0x40, 0xC0, 0xDF]) == (
        "Optical/HDMI ARC"
    )
    assert current_function_name(0xC4, [0x07, 0x09, 0x40, 0xC0, 0xDF]) == (
        "Optical/HDMI ARC"
    )
    assert current_function_name(0xC3, [0x07, 0xC3]) == "ARC"
    assert current_function_name(None, []) is None


def test_sound_mode_names_prefer_offered_value() -> None:
    # "Bass Blast" names two values; the offered one wins.
    assert sound_mode_for_name("Bass Blast", [0x51]) == 0x51
    assert sound_mode_for_name("Bass Blast", [0x37]) == 0x37
    assert offered_sound_mode_names([0x02, 0x55]) == ["Cinema", "Standard"]
    with pytest.raises(ValueError):
        sound_mode_for_name("Nope", [])


@pytest.mark.parametrize("name", ["Unknown (300)", "Unknown (x)", "HDMI 9"])
def test_unresolvable_function_names(name: str) -> None:
    with pytest.raises(ValueError):
        function_for_name(name, [0x07])
