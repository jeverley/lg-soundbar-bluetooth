"""Fixtures for the library tests."""

from __future__ import annotations

import pytest

from lg_soundbar_bluetooth.testing import FakeSoundbar


@pytest.fixture
def soundbar() -> FakeSoundbar:
    """Return a fake soundbar."""
    return FakeSoundbar()
