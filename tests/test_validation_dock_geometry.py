from PySide6.QtCore import Qt

from app.validation_dock import ValidationDock


def test_validation_dock_allows_only_left_bottom_right(qtbot):
    dock = ValidationDock()
    qtbot.addWidget(dock)

    assert dock.isAreaAllowed(Qt.DockWidgetArea.LeftDockWidgetArea)
    assert dock.isAreaAllowed(Qt.DockWidgetArea.BottomDockWidgetArea)
    assert dock.isAreaAllowed(Qt.DockWidgetArea.RightDockWidgetArea)
    assert not dock.isAreaAllowed(Qt.DockWidgetArea.TopDockWidgetArea)


def test_validation_dock_can_float(qtbot):
    dock = ValidationDock()
    qtbot.addWidget(dock)

    dock.setFloating(True)
    assert dock.isFloating()
