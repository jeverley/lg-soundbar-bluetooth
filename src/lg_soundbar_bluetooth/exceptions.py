"""Exceptions raised by the LG soundbar Bluetooth library."""

from __future__ import annotations


class LGSoundbarError(Exception):
    """Base class for library errors."""


class CannotConnect(LGSoundbarError):
    """The soundbar could not be reached or did not answer."""


class HandshakeFailed(CannotConnect):
    """The soundbar accepted the connection but did not complete the handshake."""


class NotConnected(LGSoundbarError):
    """A command was sent while the soundbar was not connected."""
