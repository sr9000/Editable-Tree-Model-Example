"""Typed ancestor-walk helper to find the owning ``Document`` tab of a widget.

Replaces ad-hoc parent-chain capability probing (``push_insert_rows`` /
``push_move_rows`` / ``edit_name_or_value_from_enter`` and similar) in
``tree_actions/*``. Uses ``isinstance(JsonTabWidgetMarker)`` (an
abstract marker base) so the OOP contract is explicit, a pre-commit
hook can forbid stringly-typed reflection, and ``tree_actions`` does
not import the concrete ``documents.tab`` module.

The return type is the :class:`documents.seams.document_protocol.Document`
protocol (per ``plans/21-promote-substates-to-controllers.md`` Phase
K3); every consumer in ``tree_actions/`` calls only Document-declared
attributes (Phase K1 audit).
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QObject

from documents.composition.marker import JsonTabWidgetMarker


def find_owning_tab(widget: object | None) -> "Document" | None:
    """Walk the Qt ``parent()`` chain and return the first owning tab found.

    Returns ``None`` when *widget* is not a Qt object or when no
    ``JsonTabWidgetMarker`` ancestor exists (e.g. headless test
    fixtures). The returned value is typed as
    :class:`documents.seams.document_protocol.Document` -- the structural
    façade exposed by every concrete ``JsonTab``.
    """
    node = widget
    while node is not None:
        if isinstance(node, JsonTabWidgetMarker):
            return cast("Document", node)
        if isinstance(node, QObject):
            node = node.parent()
        else:
            return None
    return None
