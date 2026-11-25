"""Tests for how the client opens the soundbar's link."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from bluetooth_classic import SERIAL_PORT, parse_rfcomm_url

from lg_soundbar_bluetooth import client

ADDRESS = "00:11:22:33:44:55"
REQUEST = b"\x41\x54\x00\x0b\x00\x00"


async def test_the_link_is_the_serial_port_service_through_serialx() -> None:
    with patch.object(client, "create_serial_connection", AsyncMock()) as connect:
        await client._open_link(
            ADDRESS, asyncio.Protocol, 5.0, write_on_connect=REQUEST
        )
    _, factory, url = connect.call_args.args
    assert factory is asyncio.Protocol
    target = parse_rfcomm_url(url)
    assert (target.address, target.service) == (ADDRESS, SERIAL_PORT)
    assert connect.call_args.kwargs == {
        "baudrate": 9600,
        "connect_timeout": 5.0,
        "write_on_connect": REQUEST,
    }
