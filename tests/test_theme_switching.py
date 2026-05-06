from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSettings, QStandardPaths, Qt

from app.main_window import MainWindow
from settings import APPLICATION_ID
from state.theme_settings import get_follow_system, set_watch_user_dir


def _theme_settings() -> QSettings:
    return QSettings(APPLICATION_ID, "theme")


def _current_source_path(tab) -> tuple[int, ...]:
    current_view = tab.view.currentIndex()
    source = tab._proxy_to_source(current_view)
    return tab._index_path(source)


def test_switching_theme_preserves_undo_expansion_and_selection(qtbot, tmp_path, monkeypatch):
    QStandardPaths.setTestModeEnabled(True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _theme_settings().clear()

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    tab = win._add_tab(data={"a": {"b": [1, 2]}}, file_path=None)
    assert tab is not None

    root = tab.model.index(0, 0, QModelIndex())
    a = tab.model.index(0, 0, root)
    b = tab.model.index(0, 0, a)
    leaf = tab.model.index(1, 0, b)

    tab.view.expand(tab._source_to_view(root))
    tab.view.expand(tab._source_to_view(a))
    tab.view.setCurrentIndex(tab._source_to_view(leaf))

    type_idx = tab.model.index(1, 1, b)
    assert tab.model.setData(type_idx, "string", Qt.ItemDataRole.EditRole)

    count_before = tab.undo_stack.count()
    clean_before = tab.undo_stack.cleanIndex()
    expanded_before = sorted(tab._collect_expanded_paths())
    current_before = _current_source_path(tab)

    target = win._theme_registry.default_for_mode("dark" if win._theme.mode == "light" else "light")
    win._apply_theme(target)

    assert tab.undo_stack.count() == count_before
    assert tab.undo_stack.cleanIndex() == clean_before
    assert sorted(tab._collect_expanded_paths()) == expanded_before
    assert _current_source_path(tab) == current_before


def test_follow_system_setting_persists_across_mainwindow_instances(qtbot, tmp_path, monkeypatch):
    QStandardPaths.setTestModeEnabled(True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    settings = _theme_settings()
    settings.clear()

    first = MainWindow(yaml_filename="")
    qtbot.addWidget(first)

    first._on_follow_system_toggled(False)
    first._on_theme_selected("Default Dark")

    assert get_follow_system() is False

    first.close()
    first.deleteLater()

    second = MainWindow(yaml_filename="")
    qtbot.addWidget(second)

    assert second._theme.name == "Default Dark"
    assert second._theme_follow_action is not None
    assert second._theme_follow_action.isChecked() is False


def test_hot_reload_picks_up_new_user_theme_via_watcher_event(qtbot, tmp_path, monkeypatch):
    QStandardPaths.setTestModeEnabled(True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _theme_settings().clear()
    set_watch_user_dir(True)

    try:
        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)

        user_dir = win._theme_registry.user_dir
        user_dir.mkdir(parents=True, exist_ok=True)
        new_theme = user_dir / "custom-light.yaml"
        new_theme.write_text(
            "\n".join(
                [
                    "name: Custom Light",
                    "mode: light",
                    "palette:",
                    "  accent: '#123456'",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        win._on_theme_fs_event(str(new_theme))
        qtbot.wait(350)

        names = {h.name for h in win._theme_registry.list_themes()}
        assert "Custom Light" in names
    finally:
        set_watch_user_dir(False)


def test_apply_theme_emits_datachanged_across_tabs(qtbot, tmp_path, monkeypatch):
    QStandardPaths.setTestModeEnabled(True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _theme_settings().clear()

    for tab_count in (0, 1, 3):
        win = MainWindow(yaml_filename="")
        qtbot.addWidget(win)

        tabs = []
        for i in range(tab_count):
            tab = win._add_tab(data={f"k{i}": {"x": i}}, file_path=None)
            assert tab is not None
            tabs.append(tab)

        signals: dict[object, list[tuple[int, int, list[Qt.ItemDataRole]]]] = {tab: [] for tab in tabs}
        for tab in tabs:
            tab.model.dataChanged.connect(
                lambda top, bottom, roles, t=tab: signals[t].append((top.column(), bottom.column(), list(roles)))
            )

        target = win._theme_registry.default_for_mode("dark" if win._theme.mode == "light" else "light")
        win._apply_theme(target)

        for tab in tabs:
            assert signals[tab]
            assert any(top_col == 0 and bottom_col == 2 for top_col, bottom_col, _roles in signals[tab])
            assert any(Qt.ItemDataRole.DecorationRole in roles for _top, _bottom, roles in signals[tab])

        win.close()
        win.deleteLater()
