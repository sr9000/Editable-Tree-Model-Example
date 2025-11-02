from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QTreeView

from jsontream import StreamingJSONEncoderWrapper
from model_actions import action_insert_child, action_insert_column, action_insert_row
from tree_model import JsonTreeModel


def show_context_menu(tree_view: QTreeView, position: QPoint):
    context_menu = QMenu(tree_view)

    index = tree_view.indexAt(position)
    model = tree_view.model()
    data = model.data(index, Qt.ItemDataRole.DisplayRole)

    if data is not None and isinstance(model, JsonTreeModel):
        item = model.get_item(index)

        sub_menu = context_menu.addMenu(str(data))
        copy_action = sub_menu.addAction("Copy")
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(to_json(item)))

        cut_action = sub_menu.addAction("Cut")
        delete_action = sub_menu.addAction("Delete")

    new_row = context_menu.addAction("Insert Row")
    new_row.triggered.connect(lambda: action_insert_row(index, model))

    new_child = context_menu.addAction("Insert Child")
    new_child.triggered.connect(lambda: action_insert_child(tree_view, index, model))

    new_column = context_menu.addAction("Insert Column")
    new_column.triggered.connect(lambda: action_insert_column(index, model))

    # Add actions to the context menu here
    context_menu.exec(tree_view.mapToGlobal(position))


def to_json(item):
    encoder = StreamingJSONEncoderWrapper(separators=(",", ":"), indent=2)
    return "".join(encoder.iterencode(item))
