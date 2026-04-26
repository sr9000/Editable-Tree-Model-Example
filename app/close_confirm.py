from PySide6.QtWidgets import QMessageBox


def confirm_close(window, tab) -> bool:
    if not tab.is_dirty:
        return True
    choice = QMessageBox.question(
        window,
        "Unsaved changes",
        f"Save changes to {tab.display_name().replace(' *', '')}?",
        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Save,
    )
    if choice == QMessageBox.StandardButton.Cancel:
        return False
    if choice == QMessageBox.StandardButton.Save:
        return window._save_tab(tab)
    return True
