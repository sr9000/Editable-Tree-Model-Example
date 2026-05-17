"""Smoke tests for MainWindow.

These tests instantiate the real MainWindow and exercise the user-facing
actions to catch integration bugs (such as the QStatusBar shadowing the
QMainWindow.statusBar() method that broke "Create new file").
"""

from time import sleep

import pytest
from PySide6.QtCore import (QByteArray, QMimeData, QModelIndex, QSettings, Qt,
                            QUrl, qInstallMessageHandler)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QStatusBar
from pytestqt.plugin import qtbot

import app.main_window as main_window_module
from app.main_window import MainWindow
from documents.tab import JsonTab
from settings import APPLICATION_ID, WINDOW_DEFAULT_SIZE
from tree.types import JsonType


def _ensure_seed_row(tab: JsonTab) -> QModelIndex:
    if tab.model.show_root:
        root = tab.model.index(0, 0, QModelIndex())
        if tab.model.rowCount(root) == 0:
            assert tab.push_insert_rows(
                [
                    {
                        "parent_path": (),
                        "row": 0,
                        "value": 1,
                        "name": "seed",
                    }
                ],
                label="seed row",
            )
        return tab.model.index(0, 0, root)

    if tab.model.rowCount() == 0:
        assert tab.push_insert_rows(
            [
                {
                    "parent_path": (),
                    "row": 0,
                    "value": 1,
                    "name": "seed",
                }
            ],
            label="seed row",
        )
    return tab.model.index(0, 0)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window(qapp):
    win = MainWindow(yaml_filename="")
    yield win
    for i in range(win.tabWidget.count()):
        tab = win.tabWidget.widget(i)
        if isinstance(tab, JsonTab):
            tab.undo_stack.setClean()
    win.close()
    win.deleteLater()


@pytest.fixture
def qt_messages():
    """Capture Qt log messages during the test."""
    captured: list[str] = []

    def _handler(_msg_type, _context, message):
        captured.append(message)

    previous = qInstallMessageHandler(_handler)
    try:
        yield captured
    finally:
        qInstallMessageHandler(previous)


def test_mainwindow_constructs(main_window):
    """MainWindow can be constructed without errors."""
    assert main_window is not None
    assert main_window.tabWidget is not None
    assert main_window.tabWidget.count() == 0


def test_mainwindow_uses_default_size_without_saved_geometry(qapp):
    settings = QSettings(APPLICATION_ID, "app")
    previous_geometry = settings.value("window/geometry")
    settings.remove("window/geometry")

    try:
        win = MainWindow(yaml_filename="")
        assert (win.width(), win.height()) == WINDOW_DEFAULT_SIZE
        win.close()
        win.deleteLater()
    finally:
        if previous_geometry is None:
            settings.remove("window/geometry")
        else:
            settings.setValue("window/geometry", previous_geometry)


def test_mainwindow_restores_geometry_from_settings(qapp, monkeypatch):
    settings = QSettings(APPLICATION_ID, "app")
    previous_geometry = settings.value("window/geometry")
    expected = QByteArray(b"test-geometry")
    settings.setValue("window/geometry", expected)
    restored: dict[str, QByteArray] = {}

    def _fake_restore_geometry(self, geometry):
        restored["value"] = geometry
        return True

    monkeypatch.setattr(MainWindow, "restoreGeometry", _fake_restore_geometry)

    try:
        win = MainWindow(yaml_filename="")
        assert restored["value"] == expected
        win.close()
        win.deleteLater()
    finally:
        if previous_geometry is None:
            settings.remove("window/geometry")
        else:
            settings.setValue("window/geometry", previous_geometry)


def test_mainwindow_persists_window_mode_on_close(qapp, monkeypatch):
    settings = QSettings(APPLICATION_ID, "app")
    previous_fullscreen = settings.value("window/fullscreen")
    previous_maximized = settings.value("window/maximized")
    settings.remove("window/fullscreen")
    settings.remove("window/maximized")

    try:
        win = MainWindow(yaml_filename="")
        monkeypatch.setattr(win, "isFullScreen", lambda: False)
        monkeypatch.setattr(win, "isMaximized", lambda: True)
        win.close()
        win.deleteLater()

        assert MainWindow._coerce_bool(settings.value("window/fullscreen"), default=True) is False
        assert MainWindow._coerce_bool(settings.value("window/maximized"), default=False) is True
    finally:
        if previous_fullscreen is None:
            settings.remove("window/fullscreen")
        else:
            settings.setValue("window/fullscreen", previous_fullscreen)
        if previous_maximized is None:
            settings.remove("window/maximized")
        else:
            settings.setValue("window/maximized", previous_maximized)


def test_show_with_restored_mode_uses_normal_show_by_default(qapp, monkeypatch):
    win = MainWindow(yaml_filename="")
    calls = {"show": 0, "fullscreen": 0, "maximized": 0}

    monkeypatch.setattr(win, "show", lambda: calls.__setitem__("show", calls["show"] + 1))
    monkeypatch.setattr(win, "showFullScreen", lambda: calls.__setitem__("fullscreen", calls["fullscreen"] + 1))
    monkeypatch.setattr(win, "showMaximized", lambda: calls.__setitem__("maximized", calls["maximized"] + 1))

    win._startup_window_mode = "normal"
    win.show_with_restored_mode()

    assert calls["show"] == 1
    assert calls["fullscreen"] == 0
    assert calls["maximized"] == 0
    win.close()
    win.deleteLater()


def test_mainwindow_status_bar_is_usable(main_window):
    """`self.statusBar` must expose a showMessage callable.

    Regression: Ui_MainWindow assigns ``self.statusBar = QStatusBar(...)``,
    which shadows ``QMainWindow.statusBar()``. Code that called
    ``self.statusBar()`` raised "QStatusBar object is not callable".
    """
    assert isinstance(main_window.statusBar, QStatusBar)
    # showMessage must be callable with (text, timeout)
    main_window.statusBar.showMessage("hello", 1000)
    assert main_window.statusBar.currentMessage() == "hello"


def test_create_new_file_action_opens_tab(main_window):
    """Triggering 'Create new file' must open a JsonTab without errors."""
    assert main_window.tabWidget.count() == 0

    # Trigger via the same code path the menu uses.
    main_window.create_new_file()

    assert main_window.tabWidget.count() == 1
    tab = main_window.tabWidget.widget(0)
    assert isinstance(tab, JsonTab)
    assert tab.model.rowCount() == 1


def test_create_multiple_new_file_tabs(main_window):
    """Multiple invocations should each add a new tab."""
    main_window.create_new_file()
    main_window.create_new_file()
    assert main_window.tabWidget.count() == 2

    main_window.close_tab(0)
    assert main_window.tabWidget.count() == 1


def test_view_monospace_toggle_action_and_shortcut(main_window):
    assert hasattr(main_window, "viewMonospaceFieldsAction")
    action = main_window.viewMonospaceFieldsAction
    assert action.isCheckable()
    assert action.shortcut().toString() == "Ctrl+Shift+M"


def test_view_font_selector_actions_exist(main_window):
    assert hasattr(main_window, "viewSelectRegularFontAction")
    assert hasattr(main_window, "viewSelectMonospaceFontAction")
    assert main_window.viewSelectRegularFontAction.text() == "Select Regular Font..."
    assert main_window.viewSelectMonospaceFontAction.text() == "Select Monospace Font..."


def test_view_monospace_toggle_updates_tab_delegates(main_window):
    main_window.create_new_file()
    tab = main_window.tabWidget.currentWidget()
    assert isinstance(tab, JsonTab)

    main_window.toggle_monospace_fields(True)
    assert tab._monospace_fields_enabled is True
    assert tab.name_delegate._monospace_fields_enabled is True
    assert tab.value_delegate._monospace_fields_enabled is True

    main_window.toggle_monospace_fields(False)
    assert tab._monospace_fields_enabled is False
    assert tab.name_delegate._monospace_fields_enabled is False
    assert tab.value_delegate._monospace_fields_enabled is False


def test_setting_font_families_updates_active_tab(main_window):
    main_window.create_new_file()
    tab = main_window.tabWidget.currentWidget()
    assert isinstance(tab, JsonTab)

    main_window.set_regular_font_family("Serif")
    assert tab.view.font().family() == "Serif"

    main_window.set_monospace_font_family("Monospace")
    assert tab.name_delegate._mono_family == "Monospace"
    assert tab.value_delegate._mono_family == "Monospace"


def test_zoom_updates_global_editor_font_size_for_all_tabs(main_window):
    main_window.create_new_file()
    first = main_window.tabWidget.currentWidget()
    assert isinstance(first, JsonTab)

    main_window.create_new_file()
    second = main_window.tabWidget.currentWidget()
    assert isinstance(second, JsonTab)

    before_first = first.view.font().pointSize()
    before_second = second.view.font().pointSize()

    main_window.zoom_in()

    assert first.view.font().pointSize() == before_first + 1
    assert second.view.font().pointSize() == before_second + 1


def test_select_regular_font_accepts_bool_font_tuple_order(main_window, monkeypatch):
    main_window.create_new_file()
    tab = main_window.tabWidget.currentWidget()
    assert isinstance(tab, JsonTab)

    chosen = QFont(tab.view.font())
    chosen.setFamily("Serif")

    def _fake_get_font(*_args, **_kwargs):
        # Simulate runtime variant that returns (ok, font).
        return True, chosen

    monkeypatch.setattr(main_window_module.QFontDialog, "getFont", _fake_get_font)
    main_window.select_regular_font()
    assert tab.view.font().family() == "Serif"


@pytest.mark.parametrize(
    "json_type",
    [JsonType.NULL, JsonType.ARRAY, JsonType.OBJECT, JsonType.MULTILINE, JsonType.BYTES],
)
def test_type_change_does_not_log_edit_failed(main_window, qt_messages, json_type):
    """Regression: changing a value's type to a non-inline-editor type must not
    cause Qt to log "edit: editing failed".

    Previously ``JsonTab._on_type_changed`` unconditionally called
    ``view.edit(value_index)`` after every type change. For NULL/ARRAY/OBJECT
    the value cell is not editable, and for MULTILINE/BYTES/ZLIB/GZIP the
    delegate uses a modal dialog (createEditor returns None). In both cases
    Qt printed ``edit: editing failed`` to stderr.
    """
    main_window.create_new_file()
    tab = main_window.tabWidget.currentWidget()
    row0 = _ensure_seed_row(tab)
    type_index = tab.model.index(row0.row(), 1, row0.parent())

    qt_messages.clear()
    assert tab.model.setData(type_index, json_type, Qt.ItemDataRole.EditRole)

    failed = [m for m in qt_messages if "edit: editing failed" in m]
    assert not failed, f"Unexpected Qt warnings: {failed}"


def test_cycling_inline_types_does_not_log_edit_failed(main_window, qt_messages, qapp):
    """Regression: cycling a value's type through inline-editor types
    (INTEGER / FLOAT / STRING / BOOLEAN / PERCENT / DATE) must not log
    ``edit: editing failed`` nor raise ``AttributeError`` from
    ``ValueDelegate.setEditorData``.

    Previously ``setEditorData`` / ``setModelData`` dispatched on
    ``item.json_type``; if Qt reused a value editor created for a previous
    type, the dispatch called methods that didn't exist on the old widget
    (``setText`` on a ``QMpqSpinBox`` etc.), producing
    ``edit: editing failed`` warnings and ``AttributeError``s.
    """
    main_window.show()
    qapp.processEvents()
    main_window.create_new_file()
    tab = main_window.tabWidget.currentWidget()
    row0 = _ensure_seed_row(tab)
    type_index = tab.model.index(row0.row(), 1, row0.parent())

    cycle = [
        JsonType.INTEGER,
        JsonType.FLOAT,
        JsonType.STRING,
        JsonType.BOOLEAN,
        JsonType.INTEGER,
        JsonType.PERCENT,
        JsonType.DATE,
        JsonType.STRING,
    ]

    qt_messages.clear()
    for tp in cycle:
        assert tab.model.setData(type_index, tp, Qt.ItemDataRole.EditRole)
        # Let any QTimer.singleShot(0) callbacks run.
        qapp.processEvents()

    failed = [m for m in qt_messages if "edit: editing failed" in m]
    assert not failed, f"Unexpected 'edit: editing failed' warnings: {failed}"


def test_local_paths_from_mime_filters_non_local_and_deduplicates(main_window, tmp_path):
    one = tmp_path / "one.json"
    one.write_text("{}", encoding="utf-8")
    two = tmp_path / "two.yaml"
    two.write_text("a: 1\n", encoding="utf-8")

    mime = QMimeData()
    mime.setUrls(
        [
            QUrl.fromLocalFile(str(one)),
            QUrl("https://example.com/data.json"),
            QUrl.fromLocalFile(str(two)),
            QUrl.fromLocalFile(str(one)),
        ]
    )

    assert main_window._local_paths_from_mime(mime) == [str(one.resolve()), str(two.resolve())]


def test_drop_event_opens_each_local_file(main_window, monkeypatch, tmp_path):
    first = tmp_path / "a.json"
    first.write_text("{}", encoding="utf-8")
    second = tmp_path / "b.json"
    second.write_text("{}", encoding="utf-8")

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(first)), QUrl.fromLocalFile(str(second))])

    opened: list[str] = []

    def _fake_open_path(path: str) -> bool:
        opened.append(path)
        return True

    monkeypatch.setattr(main_window, "_open_path", _fake_open_path)

    class _DropEventStub:
        def __init__(self):
            self.accepted = False
            self.ignored = False

        def mimeData(self):
            return mime

        def acceptProposedAction(self):
            self.accepted = True

        def ignore(self):
            self.ignored = True

    event = _DropEventStub()
    main_window.dropEvent(event)

    assert opened == [str(first.resolve()), str(second.resolve())]
    assert event.accepted is True
    assert event.ignored is False
