"""``Document`` protocol -- typed façade that JsonTab presents externally.

This module defines the **complete external surface** the rest of the
application (``app/``, ``undo/``, ``tree_actions/``, ``state/``) is
allowed to depend on. It is the north-star seam introduced by
``plans/20-decouple-jsontab.md`` Step A1 and fleshed out by
``plans/21-promote-substates-to-controllers.md`` Phase K1 to match the
current externally-accessed surface of :class:`documents.tab.JsonTab`.

Why this protocol exists
------------------------
* External callers should import :class:`Document` (not ``JsonTab``) so
  ``JsonTab``'s internal restructuring (Phases L-P of Plan 21) does not
  ripple through ``app/``, ``undo/``, ``tree_actions/``, ``state/``.
* Subsequent phases of Plan 21 will **shrink** this protocol as
  individual ``JsonTab`` properties retire in favour of controller
  access (e.g. ``tab.io``, ``tab.view``, ``tab.editing``,
  ``tab.validation``). K1 captures the *current* surface verbatim so
  later phases have a stable type target to delete from.
* The protocol is :func:`runtime_checkable` so ``isinstance(x, Document)``
  works in tab-lookup helpers (e.g. ``tree_actions/_tab_lookup.py``).

Audit method
------------
``grep -rhoE '\\btab\\.[a-zA-Z_]+' app/ undo/ tree_actions/ state/``
plus the equivalent ``self.tab.`` / ``self._tab.`` / ``widget.`` /
``target.`` flavours. Every distinct attribute is declared below.

Imports
-------
The project's pre-commit hook forbids the typing-only guard symbol
(see ``.githooks/pre-commit-ci``) outside the allowlist, so dependent
types are imported eagerly. The imports chosen
here intentionally do **not** create cycles -- none of them import
``documents.tab``:

* ``documents.mutation_gateway`` is leaf-level.
* ``documents.view_controller`` only imports Qt + tree primitives.
* ``documents.tab_validation`` only imports validation + io_formats.
* ``tree.view`` / ``tree.model`` / ``tree.item`` are pure tree code.
* ``state.affix_mru`` only imports settings + tree.item + units.
* ``validation.index`` / ``validation.schema_source`` are leaf-level.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, runtime_checkable

from PySide6.QtCore import QModelIndex, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QLineEdit

from documents.mutation_gateway import DocumentMutationGateway
from documents.states.io_controller import IoController
from documents.tab_validation import TabValidationController
from documents.view_controller import ViewController
from state.affix_mru import AffixMRU
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.model import JsonTreeModel
from tree.view import JsonTreeView
from validation.index import IssueIndex
from validation.issue import ValidationIssue
from validation.schema_source import SchemaSource


@runtime_checkable
class Document(Protocol):
    """Stable façade exposed by a JSON tab to the rest of the app.

    Members are grouped by axis (io / view / editing / validation /
    appearance / editability / signals) matching the controller
    decomposition that Plan 21 is building toward. The protocol stays
    flat (no nested namespaces) until each controller has absorbed its
    methods and we can collapse the per-attribute forwards into a single
    ``tab.<controller>`` access.

    Notes
    -----
    * Members prefixed with a single underscore are still externally
      reached (``app/``, ``undo/``, ``tree_actions/``, ``state/``).
      They are declared here so callers can be typed against
      :class:`Document`; Plan 21 phases N-O retire them.
    * Qt signals are typed as ``ClassVar[Signal]`` per Plan 21 §5.
    * Inherited :class:`QWidget` members (``parent()``, ``destroyed``,
      ``font()``, ``setFont()``, …) are not redeclared; callers that
      need them should narrow to :class:`QWidget` locally.
    """

    # =========================================================
    # Identity / file state  (axis: io)
    # =========================================================
    # Plan 21 L3: file path, save format and dirty flag are reached
    # through the IoController (``tab.io.file_path`` / ``.save_format`` /
    # ``.dirty``).  The former top-level ``file_path`` / ``save_format`` /
    # ``is_dirty`` forwards on JsonTab were dropped in this step.
    @property
    def io(self) -> IoController: ...
    def display_name(self) -> str: ...
    def save(self) -> bool: ...
    def save_as(self, path: str | None = ...) -> bool: ...

    # =========================================================
    # Schema / validation identity  (axis: validation)
    # =========================================================
    @property
    def schema_source(self) -> SchemaSource | None: ...
    @property
    def schema_ref(self) -> str | None: ...
    @property
    def issue_index(self) -> IssueIndex | None: ...
    @property
    def validation(self) -> TabValidationController: ...
    def goto_validation_issue(self, issue: ValidationIssue, *, edit: bool = ...) -> bool: ...

    # =========================================================
    # Mutation gateway  (axis: editing)
    # =========================================================
    @property
    def mutations(self) -> DocumentMutationGateway: ...
    @property
    def model(self) -> JsonTreeModel: ...
    @property
    def undo_stack(self) -> QUndoStack: ...
    @property
    def affix_mru(self) -> AffixMRU: ...
    @property
    def last_move_placed(self) -> list[tuple[tuple, int]]: ...

    # Narrow read helpers introduced by Plan 20 Phase E2 -- preferred
    # over reaching through ``model`` for structural reads.
    def root_index(self) -> QModelIndex: ...
    def root_item(self) -> JsonTreeItem: ...
    def root_data(self) -> Any: ...
    def row_count(self, parent: QModelIndex = ...) -> int: ...

    # Tree-action entry points (one keystroke ⇒ one undo).
    def insert_sibling_before(self) -> bool: ...
    def insert_sibling_after(self) -> bool: ...
    def insert_child(self) -> bool: ...
    def edit_name_or_value_from_enter(self) -> None: ...

    # Low-level diff / insert primitives still reached by ``undo/``.
    # Plan 21 Phase N5 retires these as ``EditingController`` methods.
    def _diff_apply(self, item: JsonTreeItem, target: Any, item_index: QModelIndex) -> bool: ...
    def _emit_row_changed(self, item_index: QModelIndex) -> None: ...
    def _insert_typed_item(
        self,
        parent_item: JsonTreeItem,
        parent_index: QModelIndex,
        position: int,
        value: Any,
        name: str | int | None = ...,
    ) -> bool: ...
    def _restore_selection_at_paths(self, placed: list[tuple[tuple, int]]) -> None: ...

    # =========================================================
    # View / viewport  (axis: view)
    # =========================================================
    @property
    def view(self) -> JsonTreeView: ...
    @property
    def view_controller(self) -> ViewController: ...
    @property
    def search_edit(self) -> QLineEdit: ...

    def apply_filter(self) -> None: ...
    def column_widths(self) -> list[int]: ...
    def set_column_widths(self, widths: list[int]) -> None: ...
    def resize_key_columns(self, force: bool = ...) -> None: ...
    def _collect_expanded_paths(self) -> list[tuple[int, ...]]: ...
    def _qualified_name(self, index: QModelIndex) -> str: ...

    # =========================================================
    # Appearance / editability  (cross-cutting controllers)
    # =========================================================
    @property
    def is_read_only(self) -> bool: ...
    def set_read_only(self, enabled: bool) -> None: ...

    def set_theme(self, theme: ThemeSpec, icon_provider: IconProvider | None = ...) -> None: ...
    def apply_font_profile(self, profile: Any) -> None: ...
    @property
    def zoom_pt(self) -> int: ...
    def _set_font_pt(self, pt: int) -> None: ...

    # =========================================================
    # Host messaging façade (status bar)
    # =========================================================
    def show_status(self, message: str, timeout_ms: int = ...) -> None: ...

    # =========================================================
    # Signals  (per Plan 21 §5: ClassVar[Signal])
    # =========================================================
    dirtyChanged: ClassVar[Signal]
    schemaChanged: ClassVar[Signal]
    validationChanged: ClassVar[Signal]


__all__ = ["Document"]
