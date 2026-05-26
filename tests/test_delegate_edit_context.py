"""Tests for ``delegates/edit_context.py``."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication

from delegates.edit_context import DefaultEditContext, DelegateEditContext, EditResult


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
