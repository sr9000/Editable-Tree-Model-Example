from __future__ import annotations

from app.main_window import MainWindow
from documents.tab import JsonTab


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        maybe_tab = win.tabWidget.widget(i)
        if isinstance(maybe_tab, JsonTab):
            maybe_tab.undo_stack.setClean()
    win.close()
    win.deleteLater()


def test_loading_validation_with_no_schema_does_not_snapshot_tree(qtbot, monkeypatch):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {f"k{i}": i for i in range(500)}
        tab = win._add_tab(data=payload, defer_validation_init=True)
        assert tab is not None

        monkeypatch.setattr(
            tab.model.root_item,
            "to_json",
            lambda: (_ for _ in ()).throw(AssertionError("to_json() must not run for no-schema loading validation")),
        )

        win._load_coordinator.run_schema_discovery_and_validation(tab, parsed_data=payload)
        assert len(tab.validation.issue_index) == 0
    finally:
        _cleanup(win)


def test_clearing_schema_from_empty_state_emits_no_recursive_repaint(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        tab = win._add_tab(data={"a": 1})
        assert tab is not None

        emitted = {"count": 0}
        tab.model.dataChanged.connect(lambda *_args: emitted.__setitem__("count", emitted["count"] + 1))

        tab.validation.clear_schema()
        assert emitted["count"] == 0
    finally:
        _cleanup(win)
