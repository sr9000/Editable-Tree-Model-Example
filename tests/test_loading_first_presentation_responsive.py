from __future__ import annotations

import settings
from app.main_window import MainWindow
from documents.controllers.view import ViewController
from documents.tab import JsonTab
from tree.model import JsonTreeModel


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        maybe_tab = win.tabWidget.widget(i)
        if isinstance(maybe_tab, JsonTab):
            maybe_tab.undo_stack.setClean()
    win.close()
    win.deleteLater()


def test_above_threshold_initial_presentation_does_not_select_root(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "LOADING_AUTO_EXPAND_MAX_NODES", 1)
    calls = {"count": 0}
    original_apply_select = ViewController._apply_select

    def _spy_apply_select(self, payload):
        calls["count"] += 1
        original_apply_select(self, payload)

    monkeypatch.setattr(ViewController, "_apply_select", _spy_apply_select)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {f"k{i}": i for i in range(300)}
        prebuilt = JsonTreeModel(payload, show_root=True, estimated_item_count=100_000)
        tab = win._add_tab(data=payload, prebuilt_model=prebuilt)
        assert tab is not None
        qtbot.wait(50)
        assert calls["count"] == 0
    finally:
        _cleanup(win)


def test_below_threshold_initial_presentation_keeps_selection(qtbot, monkeypatch):
    monkeypatch.setattr(settings, "LOADING_AUTO_EXPAND_MAX_NODES", 100_000)
    calls = {"count": 0}
    original_apply_select = ViewController._apply_select

    def _spy_apply_select(self, payload):
        calls["count"] += 1
        original_apply_select(self, payload)

    monkeypatch.setattr(ViewController, "_apply_select", _spy_apply_select)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {"k": 1}
        prebuilt = JsonTreeModel(payload, show_root=True, estimated_item_count=2)
        tab = win._add_tab(data=payload, prebuilt_model=prebuilt)
        assert tab is not None
        assert calls["count"] >= 1
    finally:
        _cleanup(win)
