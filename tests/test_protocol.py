"""Tests for frame encoding and parsing."""

from __future__ import annotations

import pytest

from lg_soundbar_bluetooth import Frame, FrameParser, checksum

# Frames captured from LG's app talking to an LG soundbar (websterwh/lg-s75qr),
# and the same frames as built by the LG Sound Bar app's packet code.
CAPTURED = {
    "415400010107f8": Frame(0x00, 0x01, b"\x07"),
    "415400010140bf": Frame(0x00, 0x01, b"\x40"),
    "4154000101c03f": Frame(0x00, 0x01, b"\xc0"),
    "4154000101df20": Frame(0x00, 0x01, b"\xdf"),
}


@pytest.mark.parametrize(("encoded", "frame"), CAPTURED.items())
def test_encode_matches_captures(encoded: str, frame: Frame) -> None:
    assert frame.encode().hex() == encoded


def test_empty_payload_has_zero_checksum() -> None:
    assert checksum(b"") == 0
    assert Frame(0x00, 0x0B).encode() == bytes.fromhex("4154000b0000")


def test_frame_rejects_bad_fields() -> None:
    with pytest.raises(ValueError):
        Frame(0x100, 0)
    with pytest.raises(ValueError):
        Frame(0, 0, bytes(256))


def test_parser_handles_fragments_and_concatenation() -> None:
    parser = FrameParser()
    data = Frame(0x00, 0x0B, b"\xc3").encode() + Frame(0xC3, 0x02, b"\x28\x0f").encode()
    frames: list[Frame] = []
    for byte in data:
        frames.extend(parser.feed(bytes([byte])))
    assert frames == [Frame(0x00, 0x0B, b"\xc3"), Frame(0xC3, 0x02, b"\x28\x0f")]
    assert list(parser.feed(data)) == frames


def test_parser_skips_noise_and_bad_checksums() -> None:
    parser = FrameParser()
    good = Frame(0x0D, 0x1B, b"\xfd").encode()
    bad = bytearray(good)
    bad[-1] ^= 0xFF
    frames = list(parser.feed(b"\x00\x41\x99" + bytes(bad) + b"junk" + good))
    assert frames == [Frame(0x0D, 0x1B, b"\xfd")]
    assert parser.checksum_errors == 1
    assert parser.discarded_bytes > 0


def test_parser_keeps_split_header() -> None:
    parser = FrameParser()
    frame = Frame(0x00, 0x0B, b"\x07").encode()
    assert list(parser.feed(b"xx" + frame[:1])) == []
    assert list(parser.feed(frame[1:])) == [Frame(0x00, 0x0B, b"\x07")]
