"""Tests for the link the client opens to the soundbar."""

from __future__ import annotations

from bluetooth_classic import SERIAL_PORT, RfcommClient

from lg_soundbar_bluetooth import client

ADDRESS = "00:11:22:33:44:55"


def test_the_link_is_the_serial_port_service() -> None:
    received: list[bytes] = []
    link = client._rfcomm_client(
        ADDRESS, data_callback=received.append, disconnected_callback=print
    )
    assert isinstance(link, RfcommClient)
    assert (link.address, link.service) == (ADDRESS, SERIAL_PORT)
