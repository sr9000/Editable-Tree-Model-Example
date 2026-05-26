import functools
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QLineEdit, QMessageBox, QVBoxLayout

from delegates.edit_context import DefaultEditContext, EditResult
from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from tree.model import JsonTreeModel
from tree.view import JsonTreeView
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
        cb = getattr(self._tab, "_status_message_callback", None)
        if cb is None:
            return
        try:
            cb(message, timeout_ms)
        except Exception:
            pass

    def icon_provider(self):  # type: ignore[override]
        return getattr(self._tab, "_icon_provider", None)

    def affix_mru(self):  # type: ignore[override]
        return getattr(self._tab, "affix_mru", None)

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
            f"Binary value is {format_bytes(payload_size)}!\n"
            f"Limit is {format_bytes(limit)}.\nContinue editing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes


def init_layout(tab) -> None:
    tab.layout = QVBoxLayout(tab)

    tab.search_edit = QLineEdit(tab)
    tab.search_edit.setPlaceholderText("Filter (Ctrl+F)")

    tab.view = JsonTreeView(tab)
    tab.view.setUniformRowHeights(True)
    tab.view.setAlternatingRowColors(True)
    tab.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    tab.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    tab.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    tab.view.setAnimated(False)
    tab.view.setAllColumnsShowFocus(True)
    tab.view.setDragEnabled(True)
    tab.view.setAcceptDrops(True)
    tab.view.setDropIndicatorShown(True)
    tab.view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
    tab.view.setDefaultDropAction(Qt.DropAction.MoveAction)
    tab.view.installEventFilter(tab)
    tab.view.viewport().installEventFilter(tab)
    initial_pt = tab.view.font().pointSize()
    tab._default_font_pt = initial_pt if initial_pt > 0 else 10
    tab._font_pt = tab._default_font_pt

    # Tracks which columns the user has manually resized (drag or persisted state).
    tab._user_sized_columns = set()  # set[int]
    # Guard: True while code is programmatically resizing columns so the
    # sectionResized handler does not mis-classify that as a user action.
    tab._programmatic_column_resize = False

    tab.layout.addWidget(tab.search_edit)
    tab.layout.addWidget(tab.view)


def init_model(tab, model_data: Any, show_root: bool) -> None:
    # ``undo_stack`` is owned by ``TabHistoryController`` (Phase 2.2); the
    # tab exposes it via a delegating property.

    tab.model = JsonTreeModel(model_data, tab.view, show_root=show_root, icon_provider=tab._icon_provider)
    tab.model.attach_view(tab.view)
    tab.proxy = TreeFilterProxy(tab)
    tab.proxy.setSourceModel(tab.model)

    tab.view.setModel(tab.proxy)
    tab.model.modelReset.connect(tab._on_model_reset)


def init_validation_state(tab, model_data: Any) -> None:
    doc_path = Path(tab.file_path).expanduser().resolve() if tab.file_path else None
    tab._init_validation_state(model_data, doc_path=doc_path)


def init_delegates_and_connections(tab, update_actions_callback) -> None:
    edit_context = JsonTabEditContext(tab)
    tab._edit_context = edit_context  # kept for tests / debugging

    tab.name_delegate = NameDelegate(tab, theme=tab._theme, edit_context=edit_context)
    tab.type_delegate = JsonTypeDelegate(
        tab, theme=tab._theme, icon_provider=tab._icon_provider, edit_context=edit_context
    )
    tab.value_delegate = ValueDelegate(tab, theme=tab._theme, edit_context=edit_context)

    tab.view.setItemDelegateForColumn(0, tab.name_delegate)
    tab.view.setItemDelegateForColumn(1, tab.type_delegate)
    tab.view.setItemDelegateForColumn(2, tab.value_delegate)

    tab.view.selectionModel().selectionChanged.connect(update_actions_callback)
    tab.view.selectionModel().currentChanged.connect(tab._on_current_changed)
    tab.model.typeChanged.connect(tab._on_type_changed)
    tab.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tab.view.customContextMenuRequested.connect(functools.partial(show_context_menu, tab.view))

    # Track user-initiated column resizes.  The guard flag prevents
    # programmatic resizes (resizeColumnToContents / setColumnWidth from
    # zoom helpers) from being mis-classified as user actions.
    def _on_section_resized(logical: int, _old: int, _new: int) -> None:
        if not tab._programmatic_column_resize:
            tab._user_sized_columns.add(logical)

    tab.view.header().sectionResized.connect(_on_section_resized)


def init_shortcuts(tab) -> None:
    tab._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, tab.view)
    tab._copy_shortcut.activated.connect(lambda: tab._run_tree_action("Copied selection", copy_only=True))

    tab._cut_shortcut = QShortcut(QKeySequence.StandardKey.Cut, tab.view)
    tab._cut_shortcut.activated.connect(lambda: tab._run_tree_action("Cut selection", cut=True))

    tab._paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, tab.view)
    tab._paste_shortcut.activated.connect(lambda: tab._run_tree_action("Pasted JSON", paste=True))

    # Step 10: Ctrl+Shift+V = multi-insert after each paired selected target.
    tab._paste_zip_shortcut = QShortcut(QKeySequence("Ctrl+Shift+V"), tab.view)
    tab._paste_zip_shortcut.activated.connect(lambda: tab._run_tree_action("Inserted at selection", paste_zip=True))

    tab._replace_zip_shortcut = QShortcut(QKeySequence("Ctrl+Alt+V"), tab.view)
    tab._replace_zip_shortcut.activated.connect(
        lambda: tab._run_tree_action("Replaced values at selection", replace_zip=True)
    )

    # Delete is owned by MainWindow's rowRemoveAction (Del). Keeping a second
    # per-tab Delete shortcut causes ambiguous shortcut warnings.

    tab._duplicate_shortcut = QShortcut(QKeySequence("Ctrl+D"), tab.view)
    tab._duplicate_shortcut.activated.connect(lambda: tab._run_tree_action("Duplicated selection", duplicate=True))

    tab._move_up_shortcut = QShortcut(QKeySequence("Alt+Up"), tab.view)
    tab._move_up_shortcut.activated.connect(lambda: tab._run_tree_action("Moved up", move_up=True))

    tab._move_down_shortcut = QShortcut(QKeySequence("Alt+Down"), tab.view)
    tab._move_down_shortcut.activated.connect(lambda: tab._run_tree_action("Moved down", move_down=True))

    tab._move_out_up_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Up"), tab.view)
    tab._move_out_up_shortcut.activated.connect(lambda: tab._run_tree_action("Moved out of parent", move_out_up=True))

    tab._move_out_down_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Down"), tab.view)
    tab._move_out_down_shortcut.activated.connect(
        lambda: tab._run_tree_action("Moved out of parent", move_out_down=True)
    )

    tab._sort_shortcut = QShortcut(QKeySequence("Ctrl+Alt+S"), tab.view)
    tab._sort_shortcut.activated.connect(lambda: tab._run_tree_action("Sorted keys", sort_keys=True))

    tab._find_shortcut = QShortcut(QKeySequence.StandardKey.Find, tab.view)
    tab._find_shortcut.activated.connect(tab.search_edit.setFocus)

    # Zoom shortcuts are owned by MainWindow QAction entries (View menu).
    # Keeping a second per-tab QShortcut copy causes ambiguous shortcut warnings.


def init_search_filter(tab) -> None:
    tab._filter_timer = QTimer(tab)
    tab._filter_timer.setSingleShot(True)
    tab._filter_timer.setInterval(300)
    tab._filter_timer.timeout.connect(tab._apply_filter)
    tab.search_edit.textChanged.connect(lambda _text: tab._filter_timer.start())
