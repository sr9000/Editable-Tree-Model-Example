from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QTreeView, QMenu


def show_context_menu(tree_view: QTreeView, position: QPoint):
    context_menu = QMenu(tree_view)

    index = tree_view.indexAt(position)
    data = tree_view.model().data(index, Qt.ItemDataRole.DisplayRole)

    if data is not None:
        sub_menu = context_menu.addMenu(str(data))
        copy_action = sub_menu.addAction("Copy")
        cut_action = sub_menu.addAction("Cut")
        delete_action = sub_menu.addAction("Delete")

    new_row = context_menu.addAction("Insert Row")
    new_child = context_menu.addAction("Insert Child")
    new_column = context_menu.addAction("Insert Column")

    # Add actions to the context menu here
    context_menu.exec(tree_view.mapToGlobal(position))
