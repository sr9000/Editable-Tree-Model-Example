from PySide6.QtCore import QModelIndex, QSettings

from app.main_window import MainWindow
from documents.tab import JsonTab
from settings import APPLICATION_ID
from state.view_state import restore, save, state_key


def _view_settings() -> QSettings:
    return QSettings(APPLICATION_ID, "view_state")


def test_state_key_is_stable_for_same_resolved_path(tmp_path):
    base = tmp_path / "folder"
    base.mkdir()
    direct = str(base / "doc.json")
    via_parent = str(base / "." / "doc.json")

    key_a = state_key(direct)
    key_b = state_key(via_parent)

    assert key_a == key_b
    assert key_a.startswith("view_state/")
    assert len(key_a.rsplit("/", 1)[-1]) == 16


def test_view_state_save_restore_roundtrip(tmp_path, monkeypatch, qtbot):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _view_settings().clear()

    file_path = str(tmp_path / "doc.json")
    tab = JsonTab(
        lambda *_: None,
        data={"foo": {"bar": [1, 2]}},
        file_path=file_path,
        show_root=True,
    )
    qtbot.addWidget(tab)

    for column in range(3):
        tab.view.setColumnWidth(column, 140 + (column * 25))

    root = tab.data_store.model.index(0, 0, QModelIndex())
    foo = tab.data_store.model.index(0, 0, root)
    bar = tab.data_store.model.index(0, 0, foo)
    leaf = tab.data_store.model.index(1, 0, bar)

    tab.view.collapseAll()
    tab.view.expand(tab.view_controller.source_to_view(root))
    tab.view.expand(tab.view_controller.source_to_view(foo))
    tab.view.setCurrentIndex(tab.view_controller.source_to_view(leaf))

    tab.appearance.zoom_in()
    tab.appearance.zoom_in()
    saved_font_pt = tab.view.font().pointSize()
    saved_widths = [tab.view.columnWidth(column) for column in range(3)]

    save(tab)

    restored = JsonTab(
        lambda *_: None,
        data={"foo": {"bar": [1, 2]}},
        file_path=file_path,
        show_root=True,
    )
    qtbot.addWidget(restored)

    assert restore(restored)

    for column in range(3):
        assert restored.view.columnWidth(column) == saved_widths[column]

    root2 = restored.data_store.model.index(0, 0, QModelIndex())
    foo2 = restored.data_store.model.index(0, 0, root2)
    bar2 = restored.data_store.model.index(0, 0, foo2)
    leaf2 = restored.data_store.model.index(1, 0, bar2)

    assert restored.view.isExpanded(restored.view_controller.source_to_view(root2))
    assert restored.view.isExpanded(restored.view_controller.source_to_view(foo2))
    assert not restored.view.isExpanded(restored.view_controller.source_to_view(bar2))
    assert restored.view.currentIndex() == restored.view_controller.source_to_view(leaf2)
    assert restored.view.font().pointSize() == saved_font_pt


def test_save_as_discards_old_view_state_group(tmp_path, monkeypatch, qtbot):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    settings = _view_settings()
    settings.clear()

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    win.create_new_file()
    tab = win._current_tab()
    assert tab is not None

    old_path = str(tmp_path / "old.json")
    new_path = str(tmp_path / "new.json")
    tab.data_store.file_path = old_path

    tab.view.setColumnWidth(0, 222)
    save(tab)

    def _fake_save_as() -> bool:
        tab.data_store.file_path = new_path
        return True

    monkeypatch.setattr(tab, "save_as", _fake_save_as)

    assert win._save_tab(tab, save_as=True)

    settings.beginGroup(state_key(old_path))
    old_widths = settings.value("col_widths")
    settings.endGroup()

    settings.beginGroup(state_key(new_path))
    new_widths = settings.value("col_widths")
    settings.endGroup()

    assert old_widths is None
    assert isinstance(new_widths, list)
    assert int(new_widths[0]) == 222

    tab.data_store.undo_stack.setClean()
    win.close()
    win.deleteLater()
