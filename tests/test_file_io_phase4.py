import pytest
import simplejson
from PySide6.QtWidgets import QApplication, QMessageBox

from ui import MainWindow


def _close_window_cleanly(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        tab = win.tabWidget.widget(i)
        if hasattr(tab, "undo_stack"):
            tab.undo_stack.setClean()
    win.close()
    win.deleteLater()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_dirty(tab) -> None:
    assert tab.push_insert_rows(
        [
            {
                "parent_path": (),
                "row": 0,
                "value": 1,
                "name": "a",
            }
        ],
        label="insert",
    )


def test_setup_model_loads_json_file(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    path = tmp_path / "in.json"
    path.write_text('{"name": "demo", "n": 1.25}\n', encoding="utf-8")

    win = MainWindow(str(path))
    try:
        assert win.tabWidget.count() == 1
        tab = win.tabWidget.widget(0)
        assert tab.file_path == str(path.resolve())
        assert tab.model.root_item.to_json()["name"] == "demo"
    finally:
        _close_window_cleanly(win)


def test_dirty_flips_on_edit_and_clears_on_save(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    win = MainWindow("")
    try:
        win.create_new_file()
        tab = win.tabWidget.currentWidget()
        assert not tab.is_dirty

        _make_dirty(tab)
        assert tab.is_dirty

        out = tmp_path / "saved.json"
        assert tab.save_as(str(out))
        assert not tab.is_dirty

        parsed = simplejson.loads(out.read_text(encoding="utf-8"))
        assert parsed == {"a": 1}
    finally:
        _close_window_cleanly(win)


def test_close_dirty_tab_cancel_keeps_tab_open(tmp_path, monkeypatch, qapp):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    win = MainWindow("")
    try:
        win.create_new_file()
        tab = win.tabWidget.currentWidget()
        _make_dirty(tab)

        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)
        win.close_tab(0)
        assert win.tabWidget.count() == 1
        assert win.tabWidget.widget(0) is tab
    finally:
        _close_window_cleanly(win)
