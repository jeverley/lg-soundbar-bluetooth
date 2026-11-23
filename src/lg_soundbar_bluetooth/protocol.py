"""Frame encoding and decoding for the LG soundbar Bluetooth serial protocol.

A frame is::

    41 54 | major | minor | length | payload... | checksum

The checksum is the two's complement of the length plus every payload byte,
so an empty payload has a checksum of zero.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

from .const import FRAME_HEADER

_LOGGER = logging.getLogger(__name__)

HEADER_SIZE = 5
MAX_PAYLOAD = 0xFF


def checksum(payload: bytes) -> int:
    """Return the checksum byte for a payload."""
    return -(len(payload) + sum(payload)) & 0xFF


@dataclass(frozen=True, slots=True)
class Frame:
    """A single protocol frame."""

    major: int
    minor: int
    payload: bytes = b""

    def __post_init__(self) -> None:
        """Validate the frame fields."""
        if not 0 <= self.major <= 0xFF or not 0 <= self.minor <= 0xFF:
            raise ValueError("major and minor must each fit in one byte")
        if len(self.payload) > MAX_PAYLOAD:
            raise ValueError(f"payload longer than {MAX_PAYLOAD} bytes")

    def encode(self) -> bytes:
        """Return the frame as bytes ready to send."""
        return (
            FRAME_HEADER
            + bytes((self.major, self.minor, len(self.payload)))
            + self.payload
            + bytes((checksum(self.payload),))
        )

    def __str__(self) -> str:
        """Return the frame in the hex form used in logs."""
        return self.encode().hex(" ")


@dataclass(slots=True)
class FrameParser:
    """Split a byte stream into frames.

    Bytes before a header are skipped, frames may arrive split across reads or
    several to a read, and frames with a bad checksum are dropped.
    """

    _buffer: bytearray = field(default_factory=bytearray)
    checksum_errors: int = 0
    discarded_bytes: int = 0

    def feed(self, data: bytes) -> Iterator[Frame]:
        """Add received bytes and yield every complete frame."""
        self._buffer.extend(data)
        while True:
            start = self._buffer.find(FRAME_HEADER)
            if start < 0:
                # Keep a trailing "A" in case the "T" arrives in the next read.
                keep = 1 if self._buffer.endswith(FRAME_HEADER[:1]) else 0
                self._discard(len(self._buffer) - keep)
                return
            if start:
                self._discard(start)
            if len(self._buffer) < HEADER_SIZE:
                return
            length = self._buffer[4]
            end = HEADER_SIZE + length + 1
            if len(self._buffer) < end:
                return
            payload = bytes(self._buffer[HEADER_SIZE : end - 1])
            if self._buffer[end - 1] != checksum(payload):
                self.checksum_errors += 1
                _LOGGER.debug(
                    "Dropping frame with bad checksum: %s",
                    self._buffer[:end].hex(" "),
                )
                # Resynchronise just past this header rather than trusting the
                # length byte of a corrupt frame.
                self._discard(len(FRAME_HEADER))
                continue
            frame = Frame(self._buffer[2], self._buffer[3], payload)
            del self._buffer[:end]
            yield frame

    def _discard(self, count: int) -> None:
        if count > 0:
            self.discarded_bytes += count
            del self._buffer[:count]
