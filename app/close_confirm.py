from PySide6.QtWidgets import QMessageBox


def _has_meaningful_data(tab) -> bool:
    data = tab.data_store.model.root_item.to_json()
    if isinstance(data, dict):
        return bool(data)
    if isinstance(data, list):
        return bool(data)
    if isinstance(data, str):
        return data != ""
    return data is not None


def confirm_close(window, tab, *, prompt_for_untitled_nonempty: bool = True) -> bool:
    if prompt_for_untitled_nonempty and not tab.file_path and _has_meaningful_data(tab):
        choice = QMessageBox.question(
            window,
            "Unsaved untitled tab",
            "This untitled tab contains data. Save changes before closing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            return window._save_tab(tab, save_as=True)
        return True

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
