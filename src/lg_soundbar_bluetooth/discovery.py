"""Recognising LG soundbars by their Bluetooth name and services."""

from __future__ import annotations

import re
from collections.abc import Collection

from .const import SPP_UUID

# The LG app lists a device as a soundbar when its name starts with one of
# these and it offers the serial port service.
NAME_PREFIXES = ("LG ", "LG-")
_MODEL_RE = re.compile(r"^LG[ -](?P<model>.+?)(?:\([0-9A-Za-z]+\))?$")


def is_lg_soundbar(name: str | None, uuids: Collection[str], *, paired: bool) -> bool:
    """Return whether a device looks like an LG soundbar, as the LG app judges it.

    A scan only sees the few services a device advertises (an LG G1 lists
    two audio services), never the serial port. The full list is read when
    the device is paired, so only paired devices must offer the serial port;
    unpaired ones are judged by name.
    """
    if not name or not name.startswith(NAME_PREFIXES):
        return False
    return not paired or SPP_UUID in {uuid.lower() for uuid in uuids}


def model_from_name(name: str | None) -> str | None:
    """Return the model from a soundbar's Bluetooth name, e.g. "G1" from "LG G1(XX)"."""
    if name and (match := _MODEL_RE.match(name)):
        return match.group("model").strip() or None
    return None
