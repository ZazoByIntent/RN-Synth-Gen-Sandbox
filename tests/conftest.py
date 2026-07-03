"""Shared pytest fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def fixture_dir() -> Path:
    """Directory holding the miniature test dataset (empty until P1)."""
    return Path(__file__).parent / "fixtures"
