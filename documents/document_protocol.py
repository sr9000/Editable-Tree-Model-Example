"""Narrow ``Document`` protocol -- the north-star façade for ``JsonTab``.
This module exists per ``plans/20-decouple-jsontab.md`` Step A1.
It defines the **minimal** surface that the rest of the application
(``app/``, ``undo/``, ``tree_actions/``, ``state/``) is *eventually*
allowed to depend on. The goal is to stop external code from reaching
into ``JsonTab.data_store.*``.
Importantly: this file is a **stub**. Nothing imports it yet. It is
introduced first so subsequent steps can migrate callers onto it one
at a time without churning the import graph in the same commit that
changes behaviour.
When a step migrates a caller, that caller should:
1. type its ``tab`` parameter as :class:`Document`, and
2. access only the attributes / signals declared here.
Anything beyond this surface is a leak that the plan is trying to
retire -- extend the protocol deliberately, do not paper over the leak.
Note on imports: the project's pre-commit hook forbids the
the typing-only guard symbol in production code (see
``.githooks/pre-commit``), so the dependent types are imported
eagerly. The imports chosen here intentionally do **not** create
cycles: ``documents.mutation_gateway`` is leaf-level (does not import
``documents.tab`` or this file), and ``validation.schema_source`` has
never depended on ``documents``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PySide6.QtCore import SignalInstance

from documents.mutation_gateway import DocumentMutationGateway
from validation.schema_source import SchemaSource


@runtime_checkable
class Document(Protocol):
    """Stable façade exposed by a JSON tab to the rest of the app.
    Notes
    -----
    * No Qt widget types appear in this protocol. ``QTreeView``,
      ``QLineEdit``, ``QUndoStack``, and the JSON model are
      intentionally hidden.
    * Tree edits go through :attr:`mutations`; viewport changes will
      go through the (forthcoming, Step D1) ``view_controller`` seam.
    * Signal attributes are typed as ``SignalInstance`` so callers can
      ``connect`` without importing the implementation class.
    """

    # -- identity / file state ----------------------------------------
    @property
    def file_path(self) -> str | None: ...
    @property
    def display_name(self) -> str: ...
    @property
    def save_format(self) -> str | None: ...
    @property
    def is_dirty(self) -> bool: ...
    @property
    def is_read_only(self) -> bool: ...

    # -- schema / validation identity ---------------------------------
    @property
    def schema_source(self) -> SchemaSource | None: ...
    @property
    def schema_ref(self) -> str | None: ...

    # -- mutation gateway (Phase B target) ----------------------------
    @property
    def mutations(self) -> DocumentMutationGateway: ...

    # -- signals (typed as SignalInstance for callers) ----------------
    dirtyChanged: SignalInstance
    schemaChanged: SignalInstance
    validationChanged: SignalInstance


__all__ = ["Document"]
