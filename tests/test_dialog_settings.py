from PySide6.QtCore import QSettings

from editors.windowed.hex_dialog import QHEXDIALOG_ID, QHexDialog
from editors.windowed.multiline_dialog import QMULTILINEDIALOG_ID, QMultilineDialog
from settings import APPLICATION_ID


def test_multiline_settings(qtbot):
    """Test QMultilineDialog settings are preserved across instances."""
    # Clear existing settings for a clean slate
    settings = QSettings(APPLICATION_ID, QMULTILINEDIALOG_ID)
    settings.clear()

    # First instance: check defaults, then change and close
    dialog1 = QMultilineDialog()
    qtbot.addWidget(dialog1)

    # Verify default values
    assert dialog1.wrapCheckBox.isChecked() is True
    assert dialog1.lineNumbersCheckBox.isChecked() is True

    # Simulate changing settings
    dialog1.wrapCheckBox.setChecked(False)
    dialog1.lineNumbersCheckBox.setChecked(False)
    dialog1.accept()  # Closes the dialog and should trigger saving settings

    # Second instance: verify settings were loaded
    dialog2 = QMultilineDialog()
    qtbot.addWidget(dialog2)

    assert dialog2.wrapCheckBox.isChecked() is False
    assert dialog2.lineNumbersCheckBox.isChecked() is False
    dialog2.accept()


def test_hex_settings(qtbot):
    """Test QHexDialog settings are preserved across instances."""
    # Clear existing settings for a clean slate
    settings = QSettings(APPLICATION_ID, QHEXDIALOG_ID)
    settings.clear()

    # First instance: check defaults, then change and close
    dialog1 = QHexDialog()
    qtbot.addWidget(dialog1)

    # Verify default values
    assert dialog1.addressCheckBox.isChecked() is True
    assert dialog1.asciiCheckBox.isChecked() is True
    assert dialog1.highlightingCheckBox.isChecked() is True

    # Simulate changing settings
    dialog1.addressCheckBox.setChecked(False)
    dialog1.asciiCheckBox.setChecked(False)
    dialog1.highlightingCheckBox.setChecked(False)
    dialog1.accept()  # Closes the dialog and should trigger saving settings

    # Second instance: verify settings were loaded
    dialog2 = QHexDialog()
    qtbot.addWidget(dialog2)

    assert dialog2.addressCheckBox.isChecked() is False
    assert dialog2.asciiCheckBox.isChecked() is False
    assert dialog2.highlightingCheckBox.isChecked() is False
    dialog2.accept()


def test_global_font_settings_apply_to_multiline_and_hex_dialogs(qtbot):
    app_settings = QSettings(APPLICATION_ID, "app")
    app_settings.setValue("view/regular_font_family", "Serif")
    app_settings.setValue("view/monospace_font_family", "Monospace")
    app_settings.setValue("view/editor_font_point_size", 13)

    multiline = QMultilineDialog()
    qtbot.addWidget(multiline)
    assert multiline.editor.font().pointSize() == 13

    multiline.monospacedCheckBox.setChecked(True)
    assert multiline.editor.font().pointSize() == 13

    hexdlg = QHexDialog()
    qtbot.addWidget(hexdlg)
    assert hexdlg.editor.font().pointSize() == 13
