"""Tests for how the client opens the soundbar's link."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from bluetooth_classic import SERIAL_PORT

from lg_soundbar_bluetooth import client

ADDRESS = "00:11:22:33:44:55"
REQUEST = b"\x41\x54\x00\x0b\x00\x00"


async def test_the_link_is_the_serial_port_service() -> None:
    with patch.object(client, "open_rfcomm", AsyncMock()) as open_rfcomm:
        await client._open_link(
            ADDRESS, asyncio.Protocol, 5.0, write_on_connect=REQUEST
        )
    assert open_rfcomm.call_args.args == (ADDRESS, asyncio.Protocol)
    assert open_rfcomm.call_args.kwargs == {
        "service": SERIAL_PORT,
        "timeout": 5.0,
        "write_on_connect": REQUEST,
    }
