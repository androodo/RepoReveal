"""Shared pytest fixtures."""

from pathlib import Path

import pytest

DEMO_ROOT = Path(__file__).resolve().parents[2] / "examples" / "demo_repository"


@pytest.fixture
def demo_root() -> Path:
    return DEMO_ROOT
