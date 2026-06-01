"""Contract test for ``DockValidationPresenter`` (kill-gods Phase 3.3)."""

from __future__ import annotations

from app.main_window import MainWindow
from app.validation_dock import ValidationDock
from app.validation_presenter import DockValidationPresenter


def test_main_window_exposes_dock_presenter(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert isinstance(win._dock_validation, DockValidationPresenter)
        assert isinstance(win.validation_dock, ValidationDock)
        assert win.schemasMenu is not None
        assert win.viewValidationPanelAction is not None
    finally:
        win.close()
        win.deleteLater()


def test_rebuild_schemas_menu_shim_delegates(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        # Should not raise; rebuilds the menu with the current state.
        win._dock_validation.rebuild_schemas_menu()
        actions = win.schemasMenu.actions()
        assert len(actions) >= 3  # attach, recent submenu, ...
    finally:
        win.close()
        win.deleteLater()
