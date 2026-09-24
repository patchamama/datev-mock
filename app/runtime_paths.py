"""Resolves the directory holding runtime state (settings.json,
datev_mock.db, certs/) whether running from a source checkout or a
PyInstaller-frozen executable.

PyInstaller's one-file mode extracts everything to a transient directory
(`sys._MEIPASS`) that is deleted after every run, so `Path(__file__)` inside
a frozen module resolves to a throwaway location -- persisted data must
instead live next to the .exe itself.
"""
from __future__ import annotations

import sys
from pathlib import Path


def base_dir() -> Path:
    """Directory holding settings.json, datev_mock.db, and certs/.

    A PyInstaller-frozen executable sets sys.frozen=True; in that case the
    base dir is the folder containing the .exe itself (so persisted data
    lives next to it, not inside the transient extraction temp dir). From
    a source checkout, it's the project root (two levels up from this file,
    same as before this refactor).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
