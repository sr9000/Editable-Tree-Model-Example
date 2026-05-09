def setup_connections(window):
    window.appExitAction.triggered.connect(window.close)

    window.fileCreateNewAction.triggered.connect(window.create_new_file)
    window.fileOpenAction.triggered.connect(window.open_file_dialog)
    window.fileSaveAction.triggered.connect(window.save_file)
    window.fileSaveAsAction.triggered.connect(window.save_file_as)

    window.actionsMenu.aboutToShow.connect(window.update_actions)
    window.rowInsertAction.triggered.connect(window.insert_row_before)
    window.rowInsertAfterAction.triggered.connect(window.insert_row_after)
    window.rowRemoveAction.triggered.connect(window.remove_row)

    window.viewExpandAllAction.triggered.connect(window.expand_all)
    window.viewCollapseAllAction.triggered.connect(window.collapse_all)
    window.viewZoomInAction.triggered.connect(window.zoom_in)
    window.viewZoomOutAction.triggered.connect(window.zoom_out)
    window.viewResetZoomAction.triggered.connect(window.reset_zoom)
    window.viewMonospaceFieldsAction.toggled.connect(window.toggle_monospace_fields)

    window._setup_theme_menu()

    window.update_actions()

    window.tabWidget.tabCloseRequested.connect(window.close_tab)
    window.tabWidget.currentChanged.connect(window._on_tab_changed)


def update_actions(window):
    tab = window._current_tab()
    has_tab = tab is not None
    has_valid_index = bool(tab and tab.view.selectionModel().currentIndex().isValid())

    window.fileSaveAction.setEnabled(has_tab)
    window.fileSaveAsAction.setEnabled(has_tab)
    window.rowInsertAction.setEnabled(has_valid_index)
    window.rowInsertAfterAction.setEnabled(has_valid_index)
    window.rowRemoveAction.setEnabled(has_valid_index)
    window.viewExpandAllAction.setEnabled(has_tab)
    window.viewCollapseAllAction.setEnabled(has_tab)
    window.viewZoomInAction.setEnabled(has_tab)
    window.viewZoomOutAction.setEnabled(has_tab)
    window.viewResetZoomAction.setEnabled(has_tab)
