"""Tests for Ctrl+W (close tab) and Ctrl+Shift+T (reopen closed tab)."""

from __future__ import annotations

import json

from PySide6.QtCore import QModelIndex, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import documents.composition.init as tab_init
import settings
from app.main_window import MainWindow
from documents.controllers.view import ViewController
from documents.tab import JsonTab
from tree.model import JsonTreeModel
from units.number_affix import AffixKind, NumberAffix


def _current_tab(win: MainWindow) -> JsonTab | None:
    return win._current_tab()


def _tab_count(win: MainWindow) -> int:
    return win.tabWidget.count()


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        w = win.tabWidget.widget(i)
        if isinstance(w, JsonTab):
            w.undo_stack.setClean()
    win.close()
    win.deleteLater()
    QApplication.processEvents()


# ---------------------------------------------------------------------------
# close_current_tab (Ctrl+W)
# ---------------------------------------------------------------------------


def test_close_tab_action_disabled_with_no_tabs(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.update_actions()
        assert not win.fileCloseTabAction.isEnabled()
    finally:
        _cleanup(win)


def test_close_tab_action_enabled_with_tab(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={})
        win.update_actions()
        assert win.fileCloseTabAction.isEnabled()
    finally:
        _cleanup(win)


def test_close_current_tab_removes_tab(qtbot, monkeypatch):
    # Patch confirm to auto-accept
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={})
        assert _tab_count(win) == 1
        win.close_current_tab()
        assert _tab_count(win) == 0
    finally:
        _cleanup(win)


def test_close_current_tab_noop_when_no_tab(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.close_current_tab()  # Should not raise
        assert _tab_count(win) == 0
    finally:
        _cleanup(win)


def test_close_cancels_if_user_cancels(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Cancel)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        tab = win._add_tab(data={"x": 1})
        assert tab is not None
        # Make dirty
        idx = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
        tab.editing.commands.push_edit_value(idx.siblingAtColumn(2), 99, label="dirty")
        assert tab.io.dirty

        win.close_current_tab()
        assert _tab_count(win) == 1  # Not closed
    finally:
        _cleanup(win)


def test_close_empty_untitled_tab_without_prompt(qtbot, monkeypatch):
    called = {"count": 0}

    def _question(*_a, **_kw):
        called["count"] += 1
        return QMessageBox.StandardButton.Discard

    monkeypatch.setattr(QMessageBox, "question", _question)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={})
        win.close_current_tab()
        assert _tab_count(win) == 0
        assert called["count"] == 0
    finally:
        _cleanup(win)


def test_close_nonempty_untitled_tab_prompts_even_if_clean(qtbot, monkeypatch):
    called = {"count": 0}

    def _question(*_a, **_kw):
        called["count"] += 1
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", _question)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"k": 1})
        win.close_current_tab()
        assert _tab_count(win) == 1
        assert called["count"] == 1
    finally:
        _cleanup(win)


def test_close_nonempty_untitled_tab_prompts_and_cancel_keeps_tab(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Cancel)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        tab = win._add_tab(data={"k": 1})
        assert tab is not None
        idx = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
        tab.editing.commands.push_edit_value(idx.siblingAtColumn(2), 2, label="dirty")
        win.close_current_tab()
        assert _tab_count(win) == 1
    finally:
        _cleanup(win)


def test_close_nonempty_untitled_tab_save_uses_save_as(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Save)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        tab = win._add_tab(data={"k": 1})
        assert tab is not None
        idx = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
        tab.editing.commands.push_edit_value(idx.siblingAtColumn(2), 2, label="dirty")
        calls = {"save_as": []}

        def _fake_save(tab, *, save_as=False):
            calls["save_as"].append(save_as)
            return True

        monkeypatch.setattr(win, "_save_tab", _fake_save)
        win.close_current_tab()
        assert calls["save_as"] == [True]
        assert _tab_count(win) == 0
    finally:
        _cleanup(win)


# ---------------------------------------------------------------------------
# Reopen closed tab (Ctrl+Shift+T)
# ---------------------------------------------------------------------------


def test_reopen_action_disabled_initially(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.update_actions()
        assert not win.fileReopenTabAction.isEnabled()
    finally:
        _cleanup(win)


def test_reopen_action_enabled_after_close(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={})
        win.close_current_tab()
        win.update_actions()
        assert win.fileReopenTabAction.isEnabled()
    finally:
        _cleanup(win)


def test_reopen_restores_clean_tab_data(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"msg": "hello"})
        assert _tab_count(win) == 1
        win.close_current_tab()
        assert _tab_count(win) == 0

        win.reopen_closed_tab()
        assert _tab_count(win) == 1
        tab = _current_tab(win)
        assert tab is not None
        assert tab.model.root_item.to_json() == {"msg": "hello"}
    finally:
        _cleanup(win)


def test_reopen_multiple_tabs_lifo_order(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win._add_tab(data={"first": 1})
        win._add_tab(data={"second": 2})
        assert _tab_count(win) == 2

        # Close second (current) → stack: [first, second]... actually LIFO so second is on top
        win.close_current_tab()  # closes second
        win.close_current_tab()  # closes first
        assert _tab_count(win) == 0

        # Reopen: should get 'first' (last closed = top of LIFO)
        win.reopen_closed_tab()
        tab = _current_tab(win)
        assert tab is not None
        data = tab.model.root_item.to_json()
        assert data == {"first": 1}

        # Reopen again: should get 'second'
        win.reopen_closed_tab()
        tab = _current_tab(win)
        assert tab is not None
        data = tab.model.root_item.to_json()
        assert data == {"second": 2}
    finally:
        _cleanup(win)


def test_reopen_after_discard_does_not_resurrect_dirty_data(qtbot, monkeypatch, tmp_path):
    """When user discards dirty changes on close, reopen should reload from file."""
    doc = tmp_path / "data.json"
    doc.write_text(json.dumps({"original": True}), encoding="utf-8")

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Discard)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = _current_tab(win)

        # Make tab dirty
        first_row = tab.model.index(0, 0, tab.model.index(0, 0, QModelIndex()))
        tab.editing.commands.push_edit_value(first_row.siblingAtColumn(2), "dirty_value", label="dirty")
        assert tab.io.dirty

        win.close_current_tab()  # User chose Discard
        assert _tab_count(win) == 0

        win.reopen_closed_tab()
        # Should reload from disk — original clean data
        tab = _current_tab(win)
        assert tab is not None
        data = tab.model.root_item.to_json()
        assert data == {"original": True}  # NOT the dirty value
    finally:
        _cleanup(win)


def test_deferred_first_presentation_yields_event_loop_turn(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        turn_fired = {"value": False}
        presented = {"value": False}

        QTimer.singleShot(0, lambda: turn_fired.__setitem__("value", True))
        tab = win._tab_lifecycle.add_tab(
            data={"k": 1},
            defer_first_presentation=True,
            on_presentation_complete=lambda _tab: presented.__setitem__("value", True),
        )
        assert tab is not None
        assert not presented["value"]

        qtbot.waitUntil(lambda: presented["value"], timeout=1000)
        assert turn_fired["value"]
    finally:
        _cleanup(win)


def test_large_open_skips_expand_all_and_expands_root_only(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "LOADING_AUTO_EXPAND_MAX_NODES", 1)
    calls_expand_all: list[int] = []
    calls_expand: list[tuple[int, ...]] = []
    monkeypatch.setattr(ViewController, "request_expand_all", lambda self: calls_expand_all.append(1))
    monkeypatch.setattr(ViewController, "request_expand", lambda self, path: calls_expand.append(path))

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {"k": 1}
        prebuilt = JsonTreeModel(payload, show_root=True, estimated_item_count=100)
        tab = win._add_tab(data=payload, prebuilt_model=prebuilt)
        assert tab is not None
        assert calls_expand_all == []
        assert () in calls_expand
    finally:
        _cleanup(win)


def test_small_open_keeps_expand_all_behavior(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "LOADING_AUTO_EXPAND_MAX_NODES", 1000)
    calls_expand_all: list[int] = []
    monkeypatch.setattr(ViewController, "request_expand_all", lambda self: calls_expand_all.append(1))

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {"k": 1}
        prebuilt = JsonTreeModel(payload, show_root=True, estimated_item_count=2)
        tab = win._add_tab(data=payload, prebuilt_model=prebuilt)
        assert tab is not None
        assert calls_expand_all
    finally:
        _cleanup(win)


def test_large_open_uses_bounded_column_sizing(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "LOADING_AUTO_EXPAND_MAX_NODES", 1)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {"k": 1}
        prebuilt = JsonTreeModel(payload, show_root=True, estimated_item_count=100)
        tab = win._add_tab(data=payload, prebuilt_model=prebuilt)
        assert tab is not None

        calls: list[int] = []
        monkeypatch.setattr(tab.view, "resizeColumnToContents", lambda col: calls.append(col))
        tab.appearance.resize_key_columns(force=True)
        assert calls == []
    finally:
        _cleanup(win)


def test_small_open_keeps_content_based_column_sizing(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "LOADING_AUTO_EXPAND_MAX_NODES", 1000)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {"k": 1}
        prebuilt = JsonTreeModel(payload, show_root=True, estimated_item_count=2)
        tab = win._add_tab(data=payload, prebuilt_model=prebuilt)
        assert tab is not None

        calls: list[int] = []
        monkeypatch.setattr(tab.view, "resizeColumnToContents", lambda col: calls.append(col))
        tab.appearance.resize_key_columns(force=True)
        assert 0 in calls and 1 in calls
    finally:
        _cleanup(win)


def test_large_open_defers_affix_mru_bootstrap_but_populates(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "LOADING_AUTO_EXPAND_MAX_NODES", 1)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {
            "price": NumberAffix(kind=AffixKind.CURRENCY, affix="$", space=False, number=7),
        }
        prebuilt = JsonTreeModel(payload, show_root=True, estimated_item_count=100)
        tab = win._add_tab(data=payload, prebuilt_model=prebuilt)
        assert tab is not None

        assert tab.affix_mru.items(AffixKind.CURRENCY) == []
        qtbot.waitUntil(lambda: "$" in tab.affix_mru.items(AffixKind.CURRENCY), timeout=1000)
    finally:
        _cleanup(win)


def test_small_open_bootstraps_affix_mru_inline(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "LOADING_AUTO_EXPAND_MAX_NODES", 1000)
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {
            "price": NumberAffix(kind=AffixKind.CURRENCY, affix="$", space=False, number=7),
        }
        prebuilt = JsonTreeModel(payload, show_root=True, estimated_item_count=2)
        tab = win._add_tab(data=payload, prebuilt_model=prebuilt)
        assert tab is not None
        assert "$" in tab.affix_mru.items(AffixKind.CURRENCY)
    finally:
        _cleanup(win)


def test_regular_tab_creation_initializes_validation_inline(qtbot, monkeypatch):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    calls = {"count": 0}

    original_init = tab_init.init_validation_state

    def _spy_init_validation_state(tab, model_data):
        calls["count"] += 1
        original_init(tab, model_data)

    monkeypatch.setattr(tab_init, "init_validation_state", _spy_init_validation_state)
    try:
        tab = win._add_tab(data={"k": 1})
        assert tab is not None
        assert calls["count"] == 1
    finally:
        _cleanup(win)


def test_loading_owned_add_tab_defers_bootstrap_validation_init(qtbot, monkeypatch):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    calls = {"count": 0}

    original_init = tab_init.init_validation_state

    def _spy_init_validation_state(tab, model_data):
        calls["count"] += 1
        original_init(tab, model_data)

    monkeypatch.setattr(tab_init, "init_validation_state", _spy_init_validation_state)
    try:
        payload = {"k": 1}
        prebuilt = JsonTreeModel(payload, show_root=True, estimated_item_count=100)
        tab = win._add_tab(data=payload, prebuilt_model=prebuilt, defer_validation_init=True)
        assert tab is not None
        assert calls["count"] == 0
    finally:
        _cleanup(win)
