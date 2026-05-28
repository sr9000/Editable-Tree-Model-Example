from __future__ import annotations

import pytest
from PySide6.QtCore import QModelIndex, QSettings, QStandardPaths, Qt
from PySide6.QtGui import QGuiApplication

from app.main_window import MainWindow
from settings import APPLICATION_ID
from state.theme_settings import get_follow_system, set_watch_user_dir


def _theme_settings() -> QSettings:
    return QSettings(APPLICATION_ID, "theme")


@pytest.fixture()
def _restore_color_scheme():
    """Save and restore the Qt color scheme around each test."""
    app = QGuiApplication.instance()
    style_hints = app.styleHints() if isinstance(app, QGuiApplication) else None
    original = style_hints.colorScheme() if style_hints is not None else None
    yield
    if style_hints is not None and original is not None:
        setter = getattr(style_hints, "setColorScheme", None)  # allow: Qt 6.x compat probe in test
        if setter is not None:
            setter(original)


def _current_source_path(tab) -> tuple[int, ...]:
    current_view = tab.data_store.view.currentIndex()
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

    root = tab.data_store.model.index(0, 0, QModelIndex())
    a = tab.data_store.model.index(0, 0, root)
    b = tab.data_store.model.index(0, 0, a)
    leaf = tab.data_store.model.index(1, 0, b)

    tab.data_store.view.expand(tab._source_to_view(root))
    tab.data_store.view.expand(tab._source_to_view(a))
    tab.data_store.view.setCurrentIndex(tab._source_to_view(leaf))

    type_idx = tab.data_store.model.index(1, 1, b)
    assert tab.data_store.model.setData(type_idx, "string", Qt.ItemDataRole.EditRole)

    count_before = tab.data_store.undo_stack.count()
    clean_before = tab.data_store.undo_stack.cleanIndex()
    expanded_before = sorted(tab._collect_expanded_paths())
    current_before = _current_source_path(tab)

    target = win._theme_registry.default_for_mode("dark" if win._theme.mode == "light" else "light")
    win._apply_theme(target)

    assert tab.data_store.undo_stack.count() == count_before
    assert tab.data_store.undo_stack.cleanIndex() == clean_before
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
            tab.data_store.model.dataChanged.connect(
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


def test_color_scheme_follows_selected_theme(qtbot, tmp_path, monkeypatch, _restore_color_scheme):
    QStandardPaths.setTestModeEnabled(True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _theme_settings().clear()

    app = QGuiApplication.instance()
    assert isinstance(app, QGuiApplication)
    style_hints = app.styleHints()
    setter = getattr(style_hints, "setColorScheme", None)  # allow: Qt 6.x compat probe in test
    if setter is None:
        pytest.skip("Qt version does not support setColorScheme")

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    dark_theme = win._theme_registry.default_for_mode("dark")
    win._apply_theme(dark_theme)
    assert style_hints.colorScheme() == Qt.ColorScheme.Dark

    light_theme = win._theme_registry.default_for_mode("light")
    win._apply_theme(light_theme)
    assert style_hints.colorScheme() == Qt.ColorScheme.Light
