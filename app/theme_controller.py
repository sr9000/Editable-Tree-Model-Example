from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QFileSystemWatcher, QObject, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QMenu, QWidget

try:
    from PySide6.QtCore import Shiboken as _qt_shiboken
except (ImportError, AttributeError):
    try:
        import shiboken6 as _qt_shiboken
    except ImportError:
        _qt_shiboken = None

_is_valid = _qt_shiboken.isValid if _qt_shiboken is not None else None

from app.runtime_compat import (
    accent_color_role,
    color_scheme_setter,
    has_color_scheme_changed_signal,
    install_color_scheme_memory,
)
from state.theme_settings import (
    get_follow_system,
    get_watch_user_dir,
    resolve_active_theme,
    set_follow_system,
    set_manual_theme_name,
    set_preferred_theme_name,
    set_watch_user_dir,
)
from themes import ThemeRegistry
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec


class _ColorSchemeProxy(QObject):
    """Thin QObject shim that owns the colorSchemeChanged connection.

    Because its Qt parent is the main window, Qt automatically destroys this
    object (and disconnects all its connections) when the window is destroyed —
    no manual ``disconnect()`` call is ever needed.
    """

    def __init__(self, parent: QObject, controller: "ThemeController") -> None:
        super().__init__(parent)
        self._controller = controller

    @Slot()
    def on_changed(self, *args) -> None:
        self._controller.on_system_color_scheme_changed(*args)


class ThemeController:
    def __init__(
        self,
        parent: QWidget,
        on_theme_changed: Callable[[ThemeSpec, IconProvider], None],
    ) -> None:
        self._parent = parent
        self._on_theme_changed = on_theme_changed
        self._theme_registry = ThemeRegistry()

        self._theme_menu: QMenu | None = None
        self._theme_light_menu: QMenu | None = None
        self._theme_dark_menu: QMenu | None = None
        self._theme_follow_action: QAction | None = None
        self._theme_watch_action: QAction | None = None
        self._theme_light_group: QActionGroup | None = None
        self._theme_dark_group: QActionGroup | None = None
        self._theme_actions: dict[str, QAction] = {}

        self._theme_fs_watcher = QFileSystemWatcher(parent)
        self._theme_reload_timer = QTimer(parent)
        self._theme_reload_timer.setSingleShot(True)
        self._theme_reload_timer.setInterval(250)
        self._theme_reload_timer.timeout.connect(self.reload_themes)
        self._theme_fs_watcher.directoryChanged.connect(self.on_theme_fs_event)
        self._theme_fs_watcher.fileChanged.connect(self.on_theme_fs_event)

        self._suppress_scheme_signal: bool = False
        self._scheme_proxy: _ColorSchemeProxy | None = None

        app = QGuiApplication.instance()
        if isinstance(app, QGuiApplication):
            self._theme = resolve_active_theme(self._theme_registry, app)
            style_hints = app.styleHints()
            if has_color_scheme_changed_signal(style_hints):
                self._scheme_proxy = _ColorSchemeProxy(parent, self)
                style_hints.colorSchemeChanged.connect(self._scheme_proxy.on_changed)
        else:
            self._theme = self._theme_registry.default_for_mode("light")
        self._icon_provider = self._theme_registry.build_icon_provider(self._theme)
        self._apply_app_palette(self._theme)
        self._sync_app_color_scheme(self._theme)

        if get_watch_user_dir():
            self.refresh_theme_watcher_paths()

    @property
    def registry(self) -> ThemeRegistry:
        return self._theme_registry

    @property
    def theme(self) -> ThemeSpec:
        return self._theme

    @property
    def icon_provider(self) -> IconProvider:
        return self._icon_provider

    @property
    def follow_action(self) -> QAction | None:
        return self._theme_follow_action

    def setup_theme_menu(self, view_menu: QMenu) -> None:
        menu = QMenu("Theme", self._parent)
        self._theme_menu = menu
        follow_action = QAction("Follow system", self._parent)
        follow_action.setCheckable(True)
        follow_action.triggered.connect(self.on_follow_system_toggled)
        self._theme_follow_action = follow_action
        menu.addAction(follow_action)

        watch_action = QAction("Watch user theme folder", self._parent)
        watch_action.setCheckable(True)
        watch_action.triggered.connect(self.on_watch_user_dir_toggled)
        self._theme_watch_action = watch_action
        menu.addAction(watch_action)
        menu.addSeparator()

        self._theme_light_menu = menu.addMenu("Light themes")
        self._theme_dark_menu = menu.addMenu("Dark themes")
        self._theme_light_group = QActionGroup(self._parent)
        self._theme_light_group.setExclusive(True)
        self._theme_dark_group = QActionGroup(self._parent)
        self._theme_dark_group.setExclusive(True)

        menu.addSeparator()
        reload_action = QAction("Reload themes", self._parent)
        reload_action.triggered.connect(self.reload_themes)
        menu.addAction(reload_action)

        open_folder_action = QAction("Open themes folder...", self._parent)
        open_folder_action.triggered.connect(self.open_themes_folder)
        menu.addAction(open_folder_action)

        export_action = QAction("Export built-in themes\u2026", self._parent)
        export_action.triggered.connect(self.export_builtin_themes)
        menu.addAction(export_action)

        view_menu.addMenu(menu)
        self.rebuild_theme_menu_entries()
        self.refresh_theme_menu_checks()

    def apply_theme(self, theme: ThemeSpec) -> None:
        self._theme = theme
        self._icon_provider = self._theme_registry.build_icon_provider(theme)
        self._apply_app_palette(theme)
        self._sync_app_color_scheme(theme)
        self._on_theme_changed(theme, self._icon_provider)
        self.refresh_theme_menu_checks()

    def _apply_app_palette(self, theme: ThemeSpec) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        pal = QPalette(app.palette())
        palette = theme.palette
        pal.setColor(QPalette.ColorRole.Base, palette.base_bg)
        pal.setColor(QPalette.ColorRole.AlternateBase, palette.alternate_bg)
        pal.setColor(QPalette.ColorRole.Text, palette.base_fg)
        pal.setColor(QPalette.ColorRole.WindowText, palette.base_fg)
        pal.setColor(QPalette.ColorRole.Highlight, palette.selection_bg)
        pal.setColor(QPalette.ColorRole.HighlightedText, palette.selection_fg)
        accent_role = accent_color_role()
        if accent_role is not None:
            pal.setColor(accent_role, palette.accent)
        app.setPalette(pal)

    def _sync_app_color_scheme(self, theme: ThemeSpec) -> None:
        app = QGuiApplication.instance()
        if not isinstance(app, QGuiApplication):
            return
        style_hints = app.styleHints()
        setter = color_scheme_setter(style_hints)
        if setter is None:
            return  # older Qt — nothing to do, leave system default
        target = Qt.ColorScheme.Dark if theme.mode == "dark" else Qt.ColorScheme.Light
        if style_hints.colorScheme() != target:
            self._suppress_scheme_signal = True
            try:
                setter(target)
                if style_hints.colorScheme() != target:
                    install_color_scheme_memory(style_hints, target)
            finally:
                self._suppress_scheme_signal = False

    def rebuild_theme_menu_entries(self) -> None:
        if self._theme_light_menu is None or self._theme_dark_menu is None:
            return
        if self._theme_light_group is not None:
            for action in list(self._theme_light_group.actions()):
                self._theme_light_group.removeAction(action)
                action.deleteLater()
        if self._theme_dark_group is not None:
            for action in list(self._theme_dark_group.actions()):
                self._theme_dark_group.removeAction(action)
                action.deleteLater()
        self._theme_light_menu.clear()
        self._theme_dark_menu.clear()
        self._theme_actions.clear()

        for handle in self._theme_registry.list_themes():
            action = QAction(handle.name, self._parent)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, n=handle.name: self.on_theme_selected(n))
            self._theme_actions[handle.name] = action
            if handle.mode == "light":
                assert self._theme_light_group is not None
                self._theme_light_group.addAction(action)
                self._theme_light_menu.addAction(action)
            else:
                assert self._theme_dark_group is not None
                self._theme_dark_group.addAction(action)
                self._theme_dark_menu.addAction(action)

    def refresh_theme_menu_checks(self) -> None:
        follow = get_follow_system()
        if self._theme_follow_action is not None:
            self._theme_follow_action.setChecked(follow)
        if self._theme_watch_action is not None:
            self._theme_watch_action.setChecked(get_watch_user_dir())
        for name, action in self._theme_actions.items():
            action.setChecked(name == self._theme.name)

    def on_theme_selected(self, name: str) -> None:
        try:
            selected = self._theme_registry.get(name)
        except KeyError:
            return

        if get_follow_system():
            set_preferred_theme_name(selected.mode, selected.name)
        else:
            set_manual_theme_name(selected.name)

        self.apply_theme(selected)

    def on_follow_system_toggled(self, checked: bool) -> None:
        set_follow_system(checked)
        if checked:
            app = QGuiApplication.instance()
            if isinstance(app, QGuiApplication):
                self.apply_theme(resolve_active_theme(self._theme_registry, app))
            return

        set_manual_theme_name(self._theme.name)
        self.refresh_theme_menu_checks()

    def on_watch_user_dir_toggled(self, checked: bool) -> None:
        set_watch_user_dir(checked)
        if checked:
            self.refresh_theme_watcher_paths()
        else:
            self.clear_theme_watcher_paths()
        self.refresh_theme_menu_checks()

    def open_themes_folder(self) -> None:
        user_dir = self._theme_registry.user_dir
        user_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_dir)))

    def export_builtin_themes(self) -> None:
        """Copy bundled built-in themes (YAMLs + icon sets) into the user folder."""
        from PySide6.QtWidgets import QMessageBox

        from themes.export import export_builtins

        user_dir = self._theme_registry.user_dir
        try:
            copied, skipped = export_builtins(user_dir)
        except (OSError, FileNotFoundError) as exc:
            QMessageBox.warning(
                self._parent,
                "Export failed",
                f"Could not export built-in themes to:\n{user_dir}\n\n{exc}",
            )
            return

        if copied:
            text = f"Exported {copied} file(s) to:\n{user_dir}"
        else:
            text = f"All built-in themes are already present in:\n{user_dir}\n" "Nothing was overwritten."
        if skipped:
            text += f"\n\n{skipped} existing file(s) were left untouched."

        box = QMessageBox(self._parent)
        box.setWindowTitle("Export built-in themes")
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        open_btn = box.addButton("Open folder", QMessageBox.ButtonRole.ActionRole)
        box.exec()
        if box.clickedButton() is open_btn:
            self.open_themes_folder()
        # Picks up the new YAMLs that just landed in the user folder.
        self.reload_themes()

    def clear_theme_watcher_paths(self) -> None:
        current = self._theme_fs_watcher.directories() + self._theme_fs_watcher.files()
        if current:
            self._theme_fs_watcher.removePaths(current)

    def refresh_theme_watcher_paths(self) -> None:
        user_dir = self._theme_registry.user_dir
        user_dir.mkdir(parents=True, exist_ok=True)
        desired = {str(user_dir.resolve())}
        desired.update(str(path.resolve()) for path in user_dir.glob("*.yaml"))
        current = set(self._theme_fs_watcher.directories()) | set(self._theme_fs_watcher.files())

        to_remove = [path for path in current if path not in desired]
        if to_remove:
            self._theme_fs_watcher.removePaths(to_remove)
        to_add = [path for path in desired if path not in current]
        if to_add:
            self._theme_fs_watcher.addPaths(to_add)

    def on_theme_fs_event(self, _path: str) -> None:
        if not get_watch_user_dir():
            return
        self._theme_reload_timer.start()

    def reload_themes(self) -> None:
        self._theme_registry.reload()
        self.rebuild_theme_menu_entries()

        active_name = self._theme.name
        try:
            selected = self._theme_registry.get(active_name)
        except KeyError:
            app = QGuiApplication.instance()
            if isinstance(app, QGuiApplication):
                selected = resolve_active_theme(self._theme_registry, app)
            else:
                selected = self._theme_registry.default_for_mode("light")
        self.apply_theme(selected)

        if get_watch_user_dir():
            self.refresh_theme_watcher_paths()

    def on_system_color_scheme_changed(self, *_args) -> None:
        if self._suppress_scheme_signal:
            return
        if _is_valid is not None and not _is_valid(self._parent):
            return  # parent widget already deleted — ignore stale signal
        if not get_follow_system():
            return
        app = QGuiApplication.instance()
        if not isinstance(app, QGuiApplication):
            return
        self.apply_theme(resolve_active_theme(self._theme_registry, app))

    def shutdown(self) -> None:
        """Detach the color-scheme proxy so this controller stops responding after window close.

        Disconnects the signal immediately (synchronously) so that any deferred
        ``deleteLater()`` processing of the old window cannot trigger callbacks on
        a ``signals`` dict that has already been replaced in the next iteration.
        ``proxy.on_changed`` is a proper ``@Slot()`` on a ``QObject`` subclass, so
        ``disconnect()`` is clean and raises no warnings.
        """
        if self._scheme_proxy is None:
            return
        app = QGuiApplication.instance()
        if isinstance(app, QGuiApplication):
            style_hints = app.styleHints()
            if has_color_scheme_changed_signal(style_hints):
                try:
                    style_hints.colorSchemeChanged.disconnect(self._scheme_proxy.on_changed)
                except (RuntimeError, TypeError):
                    pass  # already disconnected or proxy partially torn down
        self._scheme_proxy.deleteLater()
        self._scheme_proxy = None
