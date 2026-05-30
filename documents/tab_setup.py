import functools
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QMessageBox

from delegates.edit_context import DefaultEditContext, EditResult
from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from documents.json_tab_ui import Ui_JsonTab
from documents.states.editing_controller import TreeAction
from tree.model import JsonTreeModel
from tree_actions.context_menu import show_context_menu
from tree_filter_proxy import TreeFilterProxy
from units import counts, format_bytes


class JsonTabEditContext(DefaultEditContext):
    """``DelegateEditContext`` implementation backed by a ``JsonTab``.

    Holds a weakref-style direct reference to the host tab (lifetime is
    coupled to the tab anyway because the delegate is parented to it).
    Routes commits through ``tab.mutations.commit_set_data`` so the seam
    published in Phase 0 is honoured, and exposes ``affix_mru`` /
    ``icon_provider`` / status callback collaborators owned by the tab.
    """

    def __init__(self, tab) -> None:
        super().__init__()
        self._tab = tab

    # ---- commit ----
    def commit(self, index, value, role=Qt.ItemDataRole.EditRole) -> EditResult:  # type: ignore[override]
        idx = QModelIndex(index) if isinstance(index, QPersistentModelIndex) else index
        if idx.model() is None:
            return EditResult(accepted=False)
        accepted = bool(self._tab.mutations.commit_set_data(idx, value, role))
        return EditResult(accepted=accepted)

    # ---- collaborators ----
    def notify_status(self, message: str, timeout_ms: int = 0) -> None:  # type: ignore[override]
        try:
            self._tab.show_status(message, timeout_ms)
        except Exception:
            pass

    def icon_provider(self):  # type: ignore[override]
        return self._tab.appearance.icon_provider

    def affix_mru(self):  # type: ignore[override]
        return self._tab.affix_mru

    # ---- confirmation dialogs (parented to a real widget) ----
    def confirm_large_text_edit(  # type: ignore[override]
        self,
        parent,
        *,
        text_len: int,
        limit: int,
        title: str,
        kind: str,
    ) -> bool:
        if text_len <= limit:
            return True
        answer = QMessageBox.warning(
            parent if parent is not None else self._tab,
            title,
            f"{kind} is {counts(text_len)} chars!\nLimit is {counts(limit)}.\nContinue editing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def confirm_large_binary_edit(self, parent, payload_size: int) -> bool:  # type: ignore[override]
        from state.edit_limits import get_binary_edit_warning_limit_bytes

        limit = get_binary_edit_warning_limit_bytes()
        if payload_size <= limit:
            return True
        answer = QMessageBox.warning(
            parent if parent is not None else self._tab,
            "Large binary value",
            f"Binary value is {format_bytes(payload_size)}!\n" f"Limit is {format_bytes(limit)}.\nContinue editing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes


def init_layout(tab: "JsonTab") -> None:
    tab.view_state.ui = Ui_JsonTab()
    tab.view_state.ui.setupUi(tab)
    tab.view_state.search_edit = tab.view_state.ui.searchEdit
    tab.view_state.view = tab.view_state.ui.treeView

    tab.view_state.view.setUniformRowHeights(True)
    tab.view_state.view.setAlternatingRowColors(True)
    tab.view_state.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    tab.view_state.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    tab.view_state.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    tab.view_state.view.setAnimated(False)
    tab.view_state.view.setAllColumnsShowFocus(True)
    tab.view_state.view.setDragEnabled(True)
    tab.view_state.view.setAcceptDrops(True)
    tab.view_state.view.setDropIndicatorShown(True)
    tab.view_state.view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
    tab.view_state.view.setDefaultDropAction(Qt.DropAction.MoveAction)
    tab.view_state.view.installEventFilter(tab)
    tab.view_state.view.viewport().installEventFilter(tab)
    initial_pt = tab.view_state.view.font().pointSize()
    tab._appearance.adopt_view_font_defaults(initial_pt)


def init_model(tab: "JsonTab", model_data: Any, show_root: bool) -> None:
    # ``undo_stack`` is owned by ``TabHistoryController`` (Phase 2.2); the
    # tab exposes it via a delegating property.

    tab.editing.model = JsonTreeModel(
        model_data, tab.view_state.view, show_root=show_root, icon_provider=tab.appearance.icon_provider
    )
    tab.model.attach_view(tab.view_state.view)
    tab.view_state.proxy = TreeFilterProxy(tab)
    tab.view_state.proxy.setSourceModel(tab.model)

    tab.view_state.view.setModel(tab.view_state.proxy)
    tab.model.modelReset.connect(tab.appearance.on_model_reset)


def init_validation_state(tab: "JsonTab", model_data: Any) -> None:
    doc_path = Path(tab.io.file_path).expanduser().resolve() if tab.io.file_path else None
    tab.validation.init_state(model_data, doc_path=doc_path)


def init_delegates_and_connections(tab: "JsonTab") -> None:
    edit_context = JsonTabEditContext(tab)
    tab._edit_context = edit_context  # kept for tests / debugging

    tab.view_state.name_delegate = NameDelegate(tab, theme=tab.appearance.theme, edit_context=edit_context)
    tab.view_state.type_delegate = JsonTypeDelegate(
        tab, theme=tab.appearance.theme, icon_provider=tab.appearance.icon_provider, edit_context=edit_context
    )
    tab.view_state.value_delegate = ValueDelegate(tab, theme=tab.appearance.theme, edit_context=edit_context)

    tab.view_state.view.setItemDelegateForColumn(0, tab.view_state.name_delegate)
    tab.view_state.view.setItemDelegateForColumn(1, tab.view_state.type_delegate)
    tab.view_state.view.setItemDelegateForColumn(2, tab.view_state.value_delegate)

    def _refresh_actions(*_args) -> None:
        tab.refresh_actions()

    tab.view_state.view.selectionModel().selectionChanged.connect(_refresh_actions)
    tab.view_state.view.selectionModel().currentChanged.connect(tab._on_current_changed)
    tab.model.typeChanged.connect(tab._on_type_changed)
    tab.view_state.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tab.view_state.view.customContextMenuRequested.connect(functools.partial(show_context_menu, tab.view_state.view))

    # Track user-initiated column resizes.  The guard flag prevents
    # programmatic resizes (resizeColumnToContents / setColumnWidth from
    # zoom helpers) from being mis-classified as user actions.
    def _on_section_resized(logical: int, _old: int, _new: int) -> None:
        if not tab.appearance.programmatic_column_resize:
            tab.appearance.user_sized_columns.add(logical)

    tab.view_state.view.header().sectionResized.connect(_on_section_resized)


def init_shortcuts(tab: "JsonTab") -> None:
    tab._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, tab.view_state.view)
    tab._copy_shortcut.activated.connect(lambda: tab._run_tree_action("Copied selection", {TreeAction.COPY_ONLY}))

    tab._cut_shortcut = QShortcut(QKeySequence.StandardKey.Cut, tab.view_state.view)
    tab._cut_shortcut.activated.connect(lambda: tab._run_tree_action("Cut selection", {TreeAction.CUT}))

    tab._paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, tab.view_state.view)
    tab._paste_shortcut.activated.connect(lambda: tab._run_tree_action("Pasted JSON", {TreeAction.PASTE}))

    # Step 10: Ctrl+Shift+V = multi-insert after each paired selected target.
    tab._paste_zip_shortcut = QShortcut(QKeySequence("Ctrl+Shift+V"), tab.view_state.view)
    tab._paste_zip_shortcut.activated.connect(
        lambda: tab._run_tree_action("Inserted at selection", {TreeAction.PASTE_ZIP})
    )

    tab._replace_zip_shortcut = QShortcut(QKeySequence("Ctrl+Alt+V"), tab.view_state.view)
    tab._replace_zip_shortcut.activated.connect(
        lambda: tab._run_tree_action("Replaced values at selection", {TreeAction.REPLACE_ZIP})
    )

    # Delete is owned by MainWindow's rowRemoveAction (Del). Keeping a second
    # per-tab Delete shortcut causes ambiguous shortcut warnings.

    tab._duplicate_shortcut = QShortcut(QKeySequence("Ctrl+D"), tab.view_state.view)
    tab._duplicate_shortcut.activated.connect(
        lambda: tab._run_tree_action("Duplicated selection", {TreeAction.DUPLICATE})
    )

    tab._move_up_shortcut = QShortcut(QKeySequence("Alt+Up"), tab.view_state.view)
    tab._move_up_shortcut.activated.connect(lambda: tab._run_tree_action("Moved up", {TreeAction.MOVE_UP}))

    tab._move_down_shortcut = QShortcut(QKeySequence("Alt+Down"), tab.view_state.view)
    tab._move_down_shortcut.activated.connect(lambda: tab._run_tree_action("Moved down", {TreeAction.MOVE_DOWN}))

    tab._move_out_up_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Up"), tab.view_state.view)
    tab._move_out_up_shortcut.activated.connect(
        lambda: tab._run_tree_action("Moved out of parent", {TreeAction.MOVE_OUT_UP})
    )

    tab._move_out_down_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Down"), tab.view_state.view)
    tab._move_out_down_shortcut.activated.connect(
        lambda: tab._run_tree_action("Moved out of parent", {TreeAction.MOVE_OUT_DOWN})
    )

    tab._sort_shortcut = QShortcut(QKeySequence("Ctrl+Alt+S"), tab.view_state.view)
    tab._sort_shortcut.activated.connect(lambda: tab._run_tree_action("Sorted keys", {TreeAction.SORT_KEYS}))

    tab._find_shortcut = QShortcut(QKeySequence.StandardKey.Find, tab.view_state.view)
    tab._find_shortcut.activated.connect(tab.view_state.search_edit.setFocus)

    # Zoom shortcuts are owned by MainWindow QAction entries (View menu).
    # Keeping a second per-tab QShortcut copy causes ambiguous shortcut warnings.


def init_search_filter(tab: "JsonTab") -> None:
    tab._filter_timer = QTimer(tab)
    tab._filter_timer.setSingleShot(True)
    tab._filter_timer.setInterval(300)
    tab._filter_timer.timeout.connect(lambda: tab.view_controller.apply_filter())
    tab.view_state.search_edit.textChanged.connect(lambda _text: tab._filter_timer.start())
