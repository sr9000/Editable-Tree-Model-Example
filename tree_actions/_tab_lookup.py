"""Typed ancestor-walk helper to find the owning ``JsonTab`` of a widget.

Replaces ad-hoc ``hasattr(widget, "push_insert_rows")`` discovery in
``tree_actions/*``. Uses ``isinstance(JsonTab)`` so the OOP contract is
explicit and a pre-commit hook can forbid stringly-typed reflection.

The import of :class:`documents.tab.JsonTab` is deferred to call time
because ``documents.tab`` already pulls in ``tree_actions.*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from documents.tab import JsonTab


def find_owning_tab(widget: object | None) -> "JsonTab | None":
    """Walk the Qt ``parent()`` chain and return the first ``JsonTab`` found.

    Returns ``None`` when *widget* is not a Qt object or when no
    ``JsonTab`` ancestor exists (e.g. headless test fixtures).
    """
    # Lazy import: documents.tab imports tree_actions/* at module load.
    from documents.tab import JsonTab

    node = widget
    while node is not None:
        if isinstance(node, JsonTab):
            return node
        if isinstance(node, QObject):
            node = node.parent()
        else:
            return None
    return None
