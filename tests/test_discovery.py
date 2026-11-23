"""Tests for recognising LG soundbars."""

from __future__ import annotations

import pytest

from lg_soundbar_bluetooth import is_lg_soundbar, model_from_name

SPP = "00001101-0000-1000-8000-00805f9b34fb"
A2DP = "0000110b-0000-1000-8000-00805f9b34fb"
AVRCP = "0000110e-0000-1000-8000-00805f9b34fb"


@pytest.mark.parametrize(
    ("name", "uuids", "paired", "expected"),
    [
        # A scan sees only advertised services, never the serial port.
        ("LG G1(XX)", set(), False, True),
        ("LG G1(XX)", {A2DP, AVRCP}, False, True),
        ("LG-SN5Y", {A2DP}, False, True),
        # Once paired, the full service list is known.
        ("LG G1(XX)", {A2DP, SPP}, True, True),
        ("LG G1(XX)", {A2DP, SPP.upper()}, True, True),
        ("LG G1(XX)", {A2DP}, True, False),
        ("[LG] webOS TV", set(), False, False),
        ("TV", {SPP}, True, False),
        (None, {SPP}, True, False),
    ],
)
def test_is_lg_soundbar(
    name: str | None, uuids: set[str], paired: bool, expected: bool
) -> None:
    assert is_lg_soundbar(name, uuids, paired=paired) is expected


def test_model_from_name() -> None:
    assert model_from_name("LG G1(XX)") == "G1"
    assert model_from_name("LG-SN5Y") == "SN5Y"
    assert model_from_name("LG Soundbar") == "Soundbar"
    assert model_from_name("Other") is None
    assert model_from_name(None) is None
