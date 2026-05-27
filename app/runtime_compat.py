"""Centralized runtime / Qt / PyInstaller / tzinfo compatibility shims.

This module is the **single** place in the production tree where
``getattr`` / ``hasattr`` may probe foreign runtime objects (PyInstaller's
``sys._MEIPASS``, ``QStyleHints`` color-scheme APIs that vary by Qt
version, ``QPalette.ColorRole.Accent`` introduced in Qt 6.6, ``tzinfo``
implementations that expose either ``.key`` or ``.zone``,
``importlib.resources.Traversable.__fspath__`` and ``QByteArray.data``
binding differences).

Every other module imports the typed helper it needs from here instead
of calling ``getattr`` / ``hasattr`` directly. Allowlisted by the
project-wide pre-commit hook (see ``plans/10-allowlist-and-precommit-hook.md``).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette


# ── PyInstaller / packaging ───────────────────────────────────────────────


def meipass_root() -> Path | None:
    """Return PyInstaller's one-file extraction root, or ``None`` from source."""
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str) and meipass:
        return Path(meipass)
    return None


def traversable_to_path(traversable: Any) -> Path | None:
    """Best-effort filesystem ``Path`` for an ``importlib.resources`` traversable.

    Returns ``None`` when the traversable is not backed by a real
    filesystem path (e.g. a packaged-zip entry).
    """
    fspath = getattr(traversable, "__fspath__", None)
    if not callable(fspath):
        return None
    try:
        raw = fspath()
    except (TypeError, OSError):
        return None
    if isinstance(raw, (str, bytes)):
        return Path(os.fsdecode(raw))
    return None


# ── Qt color scheme / palette ─────────────────────────────────────────────


def system_color_scheme(style_hints: Any) -> Qt.ColorScheme | None:
    """Return ``QStyleHints.colorScheme()`` when supported, else ``None``."""
    reader = getattr(style_hints, "colorScheme", None)
    if not callable(reader):
        return None
    return reader()


def color_scheme_setter(style_hints: Any):
    """Return ``QStyleHints.setColorScheme`` bound method when supported.

    Older Qt builds expose no setter — caller must handle ``None``.
    """
    setter = getattr(style_hints, "setColorScheme", None)
    return setter if callable(setter) else None


def color_scheme_changed_signal(style_hints: Any):
    """Return the ``QStyleHints.colorSchemeChanged`` signal or ``None``."""
    sig = getattr(style_hints, "colorSchemeChanged", None)
    # Qt signals are truthy descriptors; just return what we got.
    return sig if sig is not None else None


def has_color_scheme_changed_signal(style_hints: Any) -> bool:
    """``True`` when the binding exposes ``colorSchemeChanged``."""
    return hasattr(style_hints, "colorSchemeChanged")


def accent_color_role() -> QPalette.ColorRole | None:
    """Return ``QPalette.ColorRole.Accent`` when present (Qt 6.6+), else ``None``."""
    return getattr(QPalette.ColorRole, "Accent", None)


# ── Timezone names ────────────────────────────────────────────────────────


def tz_name(dt: datetime) -> str | None:
    """Return a stable IANA-like timezone identifier for *dt*.

    Handles both ``zoneinfo.ZoneInfo`` (``.key``) and ``pytz``-style
    (``.zone``) implementations; returns ``None`` when *dt* has no
    named timezone (e.g. naive or fixed-offset ``tzinfo``).
    """
    tz = dt.tzinfo
    if tz is None:
        return None
    name = getattr(tz, "key", None) or getattr(tz, "zone", None)
    return name if isinstance(name, str) else None


# ── QByteArray binding compatibility ──────────────────────────────────────


def qba_to_bytes(qba: Any) -> bytes:
    """Convert a ``QByteArray``-like buffer to ``bytes``.

    PySide returns ``QByteArray`` objects whose ``.data()`` yields
    ``bytes``; some bindings yield a buffer-protocol object that
    ``bytes(...)`` handles directly.
    """
    reader = getattr(qba, "data", None)
    if callable(reader):
        result = reader()
        if isinstance(result, (bytes, bytearray)):
            return bytes(result)
    return bytes(qba)
