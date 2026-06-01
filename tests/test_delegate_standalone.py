"""Phase 1.3 architectural assertion: a delegate is usable with no JsonTab in
scope, driven only by a ``QStandardItemModel`` and a ``DefaultEditContext``.

If parent crawling is ever reintroduced, these tests will start crashing or
silently routing commits through some accidental ancestor — both are caught
here.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QApplication, QComboBox, QLineEdit,
                               QStyleOptionViewItem, QWidget)

from delegates.edit_context import DefaultEditContext
from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from tree.types import JsonType


@pytest.fixture(scope="module")
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _model() -> QStandardItemModel:
    m = QStandardItemModel(1, 3)
    for col, text in enumerate(["name", "string", "value"]):
        m.setItem(0, col, QStandardItem(text))
    return m


def test_value_delegate_standalone_commit_to_model(_qapp):
    model = _model()
    ctx = DefaultEditContext()
    delegate = ValueDelegate(edit_context=ctx)

    parent = QWidget()
    idx = model.index(0, 2)
    editor = QLineEdit(parent)
    editor.setText("hello")

    delegate.setModelData(editor, model, idx)

    assert model.data(idx, Qt.ItemDataRole.EditRole) == "hello"


def test_name_delegate_standalone_commit_to_model(_qapp):
    model = _model()
    ctx = DefaultEditContext()
    delegate = NameDelegate(edit_context=ctx)

    parent = QWidget()
    idx = model.index(0, 0)
    editor = QLineEdit(parent)
    editor.setText("renamed")

    delegate.setModelData(editor, model, idx)

    assert model.data(idx, Qt.ItemDataRole.EditRole) == "renamed"


def test_type_delegate_standalone_commit_to_model(_qapp):
    model = _model()
    ctx = DefaultEditContext()
    delegate = JsonTypeDelegate(edit_context=ctx)

    parent = QWidget()
    idx = model.index(0, 1)
    editor = QComboBox(parent)
    editor.addItem("integer", JsonType.INTEGER)
    editor.setCurrentIndex(0)

    delegate.setModelData(editor, model, idx)

    assert model.data(idx, Qt.ItemDataRole.EditRole) == JsonType.INTEGER
    assert delegate.last_edit_result is not None
    assert delegate.last_edit_result.accepted is True


def test_value_delegate_without_context_falls_back_to_default(_qapp):
    """No explicit context and no JsonTab in the parent chain — commits must
    still land on the model via the bare ``DefaultEditContext`` fallback."""
    model = _model()
    delegate = ValueDelegate()  # no edit_context kwarg

    parent = QWidget()
    idx = model.index(0, 2)
    editor = QLineEdit(parent)
    editor.setText("fallback-typed")

    delegate.setModelData(editor, model, idx)

    assert model.data(idx, Qt.ItemDataRole.EditRole) == "fallback-typed"
