"""Shared platform helpers."""

from __future__ import annotations

import os


def is_windows() -> bool:
    """Return True when running on Windows."""
    return os.name == "nt"
