import functools
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QUndoStack
from PySide6.QtWidgets import QAbstractItemView, QLineEdit, QVBoxLayout

from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from tree.model import JsonTreeModel
from tree.view import JsonTreeView
from tree_actions.context_menu import show_context_menu
from tree_filter_proxy import TreeFilterProxy


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
    tab.undo_stack = QUndoStack(tab)

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
    tab.name_delegate = NameDelegate(tab, theme=tab._theme)
    tab.type_delegate = JsonTypeDelegate(tab, theme=tab._theme, icon_provider=tab._icon_provider)
    tab.value_delegate = ValueDelegate(tab, theme=tab._theme)

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
    tab._filter_timer.setInterval(150)
    tab._filter_timer.timeout.connect(tab._apply_filter)
    tab.search_edit.textChanged.connect(lambda _text: tab._filter_timer.start())
