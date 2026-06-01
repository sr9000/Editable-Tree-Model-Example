"""Tests for ``delegates/edit_context.py``."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication

from delegates.edit_context import (DefaultEditContext, DelegateEditContext,
                                    EditResult)


@pytest.fixture(scope="module")
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_edit_result_truthiness():
    assert bool(EditResult(accepted=True)) is True
    assert bool(EditResult(accepted=False)) is False
    assert EditResult(accepted=True, reopen_value_editor=True).reopen_value_editor is True


def test_default_context_implements_protocol():
    ctx = DefaultEditContext()
    assert isinstance(ctx, DelegateEditContext)


def test_default_context_setdata(_qapp):
    model = QStandardItemModel(1, 1)
    model.setItem(0, 0, QStandardItem("initial"))
    ctx = DefaultEditContext()

    idx = model.index(0, 0)
    result = ctx.commit(idx, "updated", Qt.ItemDataRole.EditRole)

    assert result.accepted is True
    assert result.reopen_value_editor is False
    assert model.data(idx, Qt.ItemDataRole.EditRole) == "updated"


def test_default_context_setdata_invalid_index():
    from PySide6.QtCore import QModelIndex

    ctx = DefaultEditContext()
    result = ctx.commit(QModelIndex(), "x", Qt.ItemDataRole.EditRole)
    assert result.accepted is False


def test_default_context_status_sink_called():
    calls: list[tuple[str, int]] = []
    ctx = DefaultEditContext(status_sink=lambda m, t: calls.append((m, t)))
    ctx.notify_status("hello", 1500)
    assert calls == [("hello", 1500)]


def test_default_context_status_sink_default_is_silent():
    ctx = DefaultEditContext()
    # Must not raise even with no sink configured.
    ctx.notify_status("ignored", 0)


def test_default_context_returns_injected_collaborators():
    mru = object()
    icons = object()
    ctx = DefaultEditContext(affix_mru=mru, icon_provider=icons)
    assert ctx.affix_mru() is mru
    assert ctx.icon_provider() is icons


def test_default_context_confirm_below_limit_auto_accepts():
    ctx = DefaultEditContext()
    # When text length is at or below the limit, no dialog should appear.
    assert ctx.confirm_large_text_edit(None, text_len=0, limit=1000, title="t", kind="k") is True
    assert ctx.confirm_large_binary_edit(None, 0) is True


# ---------------------------------------------------------------------------
# Contract: the three delegates accept ``edit_context`` and route through it.
# ---------------------------------------------------------------------------


class _RecordingContext(DefaultEditContext):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.commits: list[tuple[int, object, int]] = []
        self._next_result = EditResult(accepted=True)

    def set_next_result(self, result: EditResult) -> None:
        self._next_result = result

    def commit(self, index, value, role=Qt.ItemDataRole.EditRole):  # type: ignore[override]
        self.commits.append((index.row(), value, int(role)))
        return self._next_result


def _make_model() -> QStandardItemModel:
    m = QStandardItemModel(1, 3)
    for col in range(3):
        m.setItem(0, col, QStandardItem(f"c{col}"))
    return m


def test_value_delegate_uses_context_commit(_qapp):
    from PySide6.QtWidgets import QLineEdit

    from delegates.value import ValueDelegate

    ctx = _RecordingContext()
    delegate = ValueDelegate(edit_context=ctx)

    model = _make_model()
    idx = model.index(0, 2)

    editor = QLineEdit()
    editor.setText("typed")
    delegate.setModelData(editor, model, idx)

    assert ctx.commits and ctx.commits[0][1] == "typed"


def test_name_delegate_uses_context_commit(_qapp):
    from PySide6.QtWidgets import QLineEdit

    from delegates.name_delegate import NameDelegate

    ctx = _RecordingContext()
    delegate = NameDelegate(edit_context=ctx)

    model = _make_model()
    idx = model.index(0, 0)

    editor = QLineEdit()
    editor.setText("newname")
    delegate.setModelData(editor, model, idx)

    assert ctx.commits == [(0, "newname", int(Qt.ItemDataRole.EditRole))]


def test_type_delegate_reopen_via_edit_result(_qapp):
    from PySide6.QtWidgets import QComboBox

    from delegates.type_delegate import JsonTypeDelegate
    from tree.types import JsonType

    ctx = _RecordingContext()
    ctx.set_next_result(EditResult(accepted=True, reopen_value_editor=True))
    delegate = JsonTypeDelegate(edit_context=ctx)

    model = _make_model()
    idx = model.index(0, 1)

    editor = QComboBox()
    editor.addItem("string", JsonType.STRING)
    editor.setCurrentIndex(0)

    delegate.setModelData(editor, model, idx)

    assert delegate.last_edit_result is not None
    assert delegate.last_edit_result.accepted is True
    assert delegate.last_edit_result.reopen_value_editor is True
