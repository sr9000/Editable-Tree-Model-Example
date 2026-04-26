import functools
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QUndoStack
from PySide6.QtWidgets import QAbstractItemView, QLineEdit, QTreeView, QVBoxLayout

from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from tree.model import JsonTreeModel
from tree_actions.clipboard import copy_selection
from tree_actions.context_menu import show_context_menu
from tree_actions.paste import paste_from_clipboard
from tree_actions.structure import (
    cut_selection,
    delete_selection,
    duplicate_selection,
    move_selection_down,
    move_selection_up,
    sort_selection_keys,
)
from tree_filter_proxy import TreeFilterProxy


def init_layout(tab) -> None:
    tab.layout = QVBoxLayout(tab)

    tab.search_edit = QLineEdit(tab)
    tab.search_edit.setPlaceholderText("Filter (Ctrl+F)")

    tab.view = QTreeView(tab)
    tab.view.setUniformRowHeights(True)
    tab.view.setAlternatingRowColors(True)
    tab.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    tab.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    tab.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    tab.view.setAnimated(False)
    tab.view.setAllColumnsShowFocus(True)
    initial_pt = tab.view.font().pointSize()
    tab._default_font_pt = initial_pt if initial_pt > 0 else 10
    tab._font_pt = tab._default_font_pt

    tab.layout.addWidget(tab.search_edit)
    tab.layout.addWidget(tab.view)


def init_model(tab, model_data: Any, show_root: bool) -> None:
    tab.undo_stack = QUndoStack(tab)

    tab.model = JsonTreeModel(model_data, tab.view, show_root=show_root)
    tab.proxy = TreeFilterProxy(tab)
    tab.proxy.setSourceModel(tab.model)

    tab.view.setModel(tab.proxy)
    tab.model.modelReset.connect(tab._on_model_reset)


def init_delegates_and_connections(tab, update_actions_callback) -> None:
    tab.name_delegate = NameDelegate(tab)
    tab.type_delegate = JsonTypeDelegate(tab)
    tab.value_delegate = ValueDelegate(tab)

    tab.view.setItemDelegateForColumn(0, tab.name_delegate)
    tab.view.setItemDelegateForColumn(1, tab.type_delegate)
    tab.view.setItemDelegateForColumn(2, tab.value_delegate)

    tab.view.selectionModel().selectionChanged.connect(update_actions_callback)
    tab.view.selectionModel().currentChanged.connect(tab._on_current_changed)
    tab.model.typeChanged.connect(tab._on_type_changed)
    tab.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tab.view.customContextMenuRequested.connect(functools.partial(show_context_menu, tab.view))


def init_shortcuts(tab) -> None:
    tab._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, tab.view)
    tab._copy_shortcut.activated.connect(lambda: tab._run_tree_action("Copied selection", copy_only=True))

    tab._cut_shortcut = QShortcut(QKeySequence.StandardKey.Cut, tab.view)
    tab._cut_shortcut.activated.connect(lambda: tab._run_tree_action("Cut selection", cut=True))

    tab._paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, tab.view)
    tab._paste_shortcut.activated.connect(lambda: tab._run_tree_action("Pasted JSON", paste=True))

    tab._delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), tab.view)
    tab._delete_shortcut.activated.connect(lambda: tab._run_tree_action("Deleted selection", delete=True))

    tab._duplicate_shortcut = QShortcut(QKeySequence("Ctrl+D"), tab.view)
    tab._duplicate_shortcut.activated.connect(lambda: tab._run_tree_action("Duplicated selection", duplicate=True))

    tab._move_up_shortcut = QShortcut(QKeySequence("Alt+Up"), tab.view)
    tab._move_up_shortcut.activated.connect(lambda: tab._run_tree_action("Moved up", move_up=True))

    tab._move_down_shortcut = QShortcut(QKeySequence("Alt+Down"), tab.view)
    tab._move_down_shortcut.activated.connect(lambda: tab._run_tree_action("Moved down", move_down=True))

    tab._sort_shortcut = QShortcut(QKeySequence("Ctrl+Alt+S"), tab.view)
    tab._sort_shortcut.activated.connect(lambda: tab._run_tree_action("Sorted keys", sort_keys=True))

    tab._find_shortcut = QShortcut(QKeySequence.StandardKey.Find, tab.view)
    tab._find_shortcut.activated.connect(tab.search_edit.setFocus)

    tab._zoom_in_shortcut = QShortcut(QKeySequence.StandardKey.ZoomIn, tab.view)
    tab._zoom_in_shortcut.activated.connect(tab.zoom_in)
    tab._zoom_out_shortcut = QShortcut(QKeySequence.StandardKey.ZoomOut, tab.view)
    tab._zoom_out_shortcut.activated.connect(tab.zoom_out)
    tab._zoom_reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), tab.view)
    tab._zoom_reset_shortcut.activated.connect(tab.zoom_reset)


def init_search_filter(tab) -> None:
    tab._filter_timer = QTimer(tab)
    tab._filter_timer.setSingleShot(True)
    tab._filter_timer.setInterval(150)
    tab._filter_timer.timeout.connect(tab._apply_filter)
    tab.search_edit.textChanged.connect(lambda _text: tab._filter_timer.start())
