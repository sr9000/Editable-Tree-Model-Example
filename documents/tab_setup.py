import functools
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QMessageBox

from delegates.edit_context import DefaultEditContext, EditResult
from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from documents.json_tab_ui import Ui_JsonTab
from tree.model import JsonTreeModel
from tree_actions.context_menu import show_context_menu
from tree_filter_proxy import TreeFilterProxy
from units import counts, format_bytes

if TYPE_CHECKING:
    from documents.tab import JsonTab


class JsonTabEditContext(DefaultEditContext):
    """``DelegateEditContext`` implementation backed by a ``JsonTab``.

    Holds a weakref-style direct reference to the host tab (lifetime is
    coupled to the tab anyway because the delegate is parented to it).
    Routes commits through ``tab.data_store.mutations.commit_set_data`` so the seam
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
        accepted = bool(self._tab.data_store.mutations.commit_set_data(idx, value, role))
        return EditResult(accepted=accepted)

    # ---- collaborators ----
    def notify_status(self, message: str, timeout_ms: int = 0) -> None:  # type: ignore[override]
        try:
            self._tab.show_status(message, timeout_ms)
        except Exception:
            pass

    def icon_provider(self):  # type: ignore[override]
        return self._tab.data_store.icon_provider

    def affix_mru(self):  # type: ignore[override]
        return self._tab.data_store.affix_mru

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
    tab.data_store.ui = Ui_JsonTab()
    tab.data_store.ui.setupUi(tab)
    tab.data_store.search_edit = tab.data_store.ui.searchEdit
    tab.data_store.view = tab.data_store.ui.treeView

    tab.data_store.view.setUniformRowHeights(True)
    tab.data_store.view.setAlternatingRowColors(True)
    tab.data_store.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    tab.data_store.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    tab.data_store.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    tab.data_store.view.setAnimated(False)
    tab.data_store.view.setAllColumnsShowFocus(True)
    tab.data_store.view.setDragEnabled(True)
    tab.data_store.view.setAcceptDrops(True)
    tab.data_store.view.setDropIndicatorShown(True)
    tab.data_store.view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
    tab.data_store.view.setDefaultDropAction(Qt.DropAction.MoveAction)
    tab.data_store.view.installEventFilter(tab)
    tab.data_store.view.viewport().installEventFilter(tab)
    initial_pt = tab.data_store.view.font().pointSize()
    tab.data_store._default_font_pt = initial_pt if initial_pt > 0 else 10
    tab.data_store._font_pt = tab.data_store._default_font_pt

    # Tracks which columns the user has manually resized (drag or persisted state).
    tab.data_store._user_sized_columns = set()  # set[int]
    # Guard: True while code is programmatically resizing columns so the
    # sectionResized handler does not mis-classify that as a user action.
    tab.data_store._programmatic_column_resize = False


def init_model(tab: "JsonTab", model_data: Any, show_root: bool) -> None:
    # ``undo_stack`` is owned by ``TabHistoryController`` (Phase 2.2); the
    # tab exposes it via a delegating property.

    tab.data_store.model = JsonTreeModel(
        model_data, tab.data_store.view, show_root=show_root, icon_provider=tab.data_store.icon_provider
    )
    tab.data_store.model.attach_view(tab.data_store.view)
    tab.data_store.proxy = TreeFilterProxy(tab)
    tab.data_store.proxy.setSourceModel(tab.data_store.model)

    tab.data_store.view.setModel(tab.data_store.proxy)
    tab.data_store.model.modelReset.connect(tab._on_model_reset)


def init_validation_state(tab: "JsonTab", model_data: Any) -> None:
    doc_path = Path(tab.data_store.file_path).expanduser().resolve() if tab.data_store.file_path else None
    tab._init_validation_state(model_data, doc_path=doc_path)


def init_delegates_and_connections(tab: "JsonTab") -> None:
    edit_context = JsonTabEditContext(tab)
    tab._edit_context = edit_context  # kept for tests / debugging

    tab.data_store.name_delegate = NameDelegate(tab, theme=tab.data_store.theme, edit_context=edit_context)
    tab.data_store.type_delegate = JsonTypeDelegate(
        tab, theme=tab.data_store.theme, icon_provider=tab.data_store.icon_provider, edit_context=edit_context
    )
    tab.data_store.value_delegate = ValueDelegate(tab, theme=tab.data_store.theme, edit_context=edit_context)

    tab.data_store.view.setItemDelegateForColumn(0, tab.data_store.name_delegate)
    tab.data_store.view.setItemDelegateForColumn(1, tab.data_store.type_delegate)
    tab.data_store.view.setItemDelegateForColumn(2, tab.data_store.value_delegate)

    def _refresh_actions(*_args) -> None:
        tab.refresh_actions()

    tab.data_store.view.selectionModel().selectionChanged.connect(_refresh_actions)
    tab.data_store.view.selectionModel().currentChanged.connect(tab._on_current_changed)
    tab.data_store.model.typeChanged.connect(tab._on_type_changed)
    tab.data_store.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tab.data_store.view.customContextMenuRequested.connect(functools.partial(show_context_menu, tab.data_store.view))

    # Track user-initiated column resizes.  The guard flag prevents
    # programmatic resizes (resizeColumnToContents / setColumnWidth from
    # zoom helpers) from being mis-classified as user actions.
    def _on_section_resized(logical: int, _old: int, _new: int) -> None:
        if not tab.data_store._programmatic_column_resize:
            tab.data_store._user_sized_columns.add(logical)

    tab.data_store.view.header().sectionResized.connect(_on_section_resized)


def init_shortcuts(tab: "JsonTab") -> None:
    tab._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, tab.data_store.view)
    tab._copy_shortcut.activated.connect(lambda: tab._run_tree_action("Copied selection", copy_only=True))

    tab._cut_shortcut = QShortcut(QKeySequence.StandardKey.Cut, tab.data_store.view)
    tab._cut_shortcut.activated.connect(lambda: tab._run_tree_action("Cut selection", cut=True))

    tab._paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, tab.data_store.view)
    tab._paste_shortcut.activated.connect(lambda: tab._run_tree_action("Pasted JSON", paste=True))

    # Step 10: Ctrl+Shift+V = multi-insert after each paired selected target.
    tab._paste_zip_shortcut = QShortcut(QKeySequence("Ctrl+Shift+V"), tab.data_store.view)
    tab._paste_zip_shortcut.activated.connect(lambda: tab._run_tree_action("Inserted at selection", paste_zip=True))

    tab._replace_zip_shortcut = QShortcut(QKeySequence("Ctrl+Alt+V"), tab.data_store.view)
    tab._replace_zip_shortcut.activated.connect(
        lambda: tab._run_tree_action("Replaced values at selection", replace_zip=True)
    )

    # Delete is owned by MainWindow's rowRemoveAction (Del). Keeping a second
    # per-tab Delete shortcut causes ambiguous shortcut warnings.

    tab._duplicate_shortcut = QShortcut(QKeySequence("Ctrl+D"), tab.data_store.view)
    tab._duplicate_shortcut.activated.connect(lambda: tab._run_tree_action("Duplicated selection", duplicate=True))

    tab._move_up_shortcut = QShortcut(QKeySequence("Alt+Up"), tab.data_store.view)
    tab._move_up_shortcut.activated.connect(lambda: tab._run_tree_action("Moved up", move_up=True))

    tab._move_down_shortcut = QShortcut(QKeySequence("Alt+Down"), tab.data_store.view)
    tab._move_down_shortcut.activated.connect(lambda: tab._run_tree_action("Moved down", move_down=True))

    tab._move_out_up_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Up"), tab.data_store.view)
    tab._move_out_up_shortcut.activated.connect(lambda: tab._run_tree_action("Moved out of parent", move_out_up=True))

    tab._move_out_down_shortcut = QShortcut(QKeySequence("Ctrl+Alt+Down"), tab.data_store.view)
    tab._move_out_down_shortcut.activated.connect(
        lambda: tab._run_tree_action("Moved out of parent", move_out_down=True)
    )

    tab._sort_shortcut = QShortcut(QKeySequence("Ctrl+Alt+S"), tab.data_store.view)
    tab._sort_shortcut.activated.connect(lambda: tab._run_tree_action("Sorted keys", sort_keys=True))

    tab._find_shortcut = QShortcut(QKeySequence.StandardKey.Find, tab.data_store.view)
    tab._find_shortcut.activated.connect(tab.data_store.search_edit.setFocus)

    # Zoom shortcuts are owned by MainWindow QAction entries (View menu).
    # Keeping a second per-tab QShortcut copy causes ambiguous shortcut warnings.


def init_search_filter(tab: "JsonTab") -> None:
    tab._filter_timer = QTimer(tab)
    tab._filter_timer.setSingleShot(True)
    tab._filter_timer.setInterval(300)
    tab._filter_timer.timeout.connect(tab._apply_filter)
    tab.data_store.search_edit.textChanged.connect(lambda _text: tab._filter_timer.start())
