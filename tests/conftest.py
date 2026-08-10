"""Shared fixtures for manthey-precommit-hooks tests."""
from __future__ import annotations

from pathlib import Path

import pytest


def _package_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_py_file(tmp_path: Path) -> Path:
    """Create a temporary .py file and return its path."""
    return tmp_path / 'test_input.py'
