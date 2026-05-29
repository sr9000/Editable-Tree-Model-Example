"""Typed ancestor-walk helper to find the owning ``JsonTab`` of a widget.

Replaces ad-hoc parent-chain capability probing (``push_insert_rows`` /
``push_move_rows`` / ``edit_name_or_value_from_enter`` and similar) in
``tree_actions/*``. Uses ``isinstance(JsonTab)`` so the OOP contract is
explicit and a pre-commit hook can forbid stringly-typed reflection.

Lookup uses a marker base exported from ``documents.tab_marker`` so
``tree_actions`` never imports ``documents.tab``.
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QObject

from documents.tab_marker import JsonTabWidgetMarker


def find_owning_tab(widget: object | None) -> "JsonTab" | None:
    """Walk the Qt ``parent()`` chain and return the first ``JsonTab`` found.

    Returns ``None`` when *widget* is not a Qt object or when no
    ``JsonTab`` ancestor exists (e.g. headless test fixtures).
    """
    node = widget
    while node is not None:
        if isinstance(node, JsonTabWidgetMarker):
            return cast("JsonTab", node)
        if isinstance(node, QObject):
            node = node.parent()
        else:
            return None
    return None
