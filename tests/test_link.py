"""Tests for how the client opens the soundbar's link."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from bluetooth_classic import RfcommUnsupportedError, Security

from lg_soundbar_bluetooth import BluetoothUnsupported, client

ADDRESS = "00:11:22:33:44:55"
REQUEST = b"\x41\x54\x00\x0b\x00\x00"


async def test_the_link_asks_for_medium_security() -> None:
    with patch.object(client, "open_rfcomm", AsyncMock()) as open_rfcomm:
        await client._open_link(
            ADDRESS, 10, asyncio.Protocol, 5.0, write_on_connect=REQUEST
        )
    assert open_rfcomm.call_args.args[:2] == (ADDRESS, 10)
    assert open_rfcomm.call_args.kwargs == {
        "timeout": 5.0,
        "write_on_connect": REQUEST,
        "security": Security.MEDIUM,
    }


async def test_no_bluetooth_sockets_is_reported_as_unsupported() -> None:
    failing = AsyncMock(side_effect=RfcommUnsupportedError("no sockets"))
    with (
        patch.object(client, "open_rfcomm", failing),
        pytest.raises(BluetoothUnsupported),
    ):
        await client._open_link(
            ADDRESS, 10, asyncio.Protocol, 5.0, write_on_connect=REQUEST
        )
