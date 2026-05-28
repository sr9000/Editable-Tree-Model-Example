from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QModelIndex, QSize, Qt

from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from documents.tab_data import JsonTabData
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
from tree.model import JsonTreeModel
from tree.view import JsonTreeView


class FontProfileLike(Protocol):
    regular_family: str | None
    editor_point_size: int
    monospace_family: str | None
    monospace_fields_enabled: bool


class JsonTabAppearanceController:
    """Own theme, font, icon-size and key-column appearance behavior."""

    def __init__(self, data_store: JsonTabData) -> None:
        self._data_store = data_store
        self._theme: ThemeSpec | None = None
        self._icon_provider: IconProvider | None = None

    @property
    def theme(self) -> ThemeSpec | None:
        return self._theme

    @property
    def icon_provider(self) -> IconProvider | None:
        return self._icon_provider

    def initialize(self, theme: ThemeSpec | None, icon_provider: IconProvider | None) -> None:
        self._theme = theme
        self._icon_provider = icon_provider

    def set_theme(self, theme: ThemeSpec, icon_provider: IconProvider | None = None) -> None:
        self._theme = theme
        self._icon_provider = icon_provider or self._icon_provider
        self._require_name_delegate().set_theme(theme)
        self._require_value_delegate().set_theme(theme)
        type_delegate = self._require_type_delegate()
        type_delegate.set_theme(theme)
        type_delegate.set_icon_provider(self._require_icon_provider())
        self._require_model().set_icon_provider(self._require_icon_provider())

        roles = [
            Qt.ItemDataRole.ForegroundRole,
            Qt.ItemDataRole.BackgroundRole,
            Qt.ItemDataRole.FontRole,
            Qt.ItemDataRole.DecorationRole,
        ]

        def emit_ranges(parent: QModelIndex) -> None:
            model = self._require_model()
            rows = model.rowCount(parent)
            if rows <= 0:
                return

            top_left = model.index(0, 0, parent)
            bottom_right = model.index(rows - 1, model.columnCount(parent) - 1, parent)
            model.dataChanged.emit(top_left, bottom_right, roles)

            for row in range(rows):
                child_parent = model.index(row, 0, parent)
                emit_ranges(child_parent)

        emit_ranges(QModelIndex())

    def set_monospace_fields_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._data_store._monospace_fields_enabled == enabled:
            return
        self._data_store._monospace_fields_enabled = enabled
        self._require_name_delegate().set_monospace_fields_enabled(enabled)
        self._require_value_delegate().set_monospace_fields_enabled(enabled)
        self._require_view().viewport().update()

    def set_regular_font_family(self, family: str) -> None:
        if not family:
            return
        family = str(family)
        if self._data_store._regular_font_family == family:
            return
        self._data_store._regular_font_family = family
        view = self._require_view()
        font = view.font()
        font.setFamily(family)
        if font.pointSizeF() <= 0:
            font.setPointSize(max(6, int(self._data_store._font_pt or 10)))
        view.setFont(font)
        self.sync_icon_size_with_font()

    def set_monospace_font_family(self, family: str) -> None:
        if not family:
            return
        family = str(family)
        if self._data_store._monospace_font_family == family:
            return
        self._data_store._monospace_font_family = family
        self._require_name_delegate().set_monospace_font_family(family)
        self._require_value_delegate().set_monospace_font_family(family)
        self._require_view().viewport().update()

    def set_editor_font_point_size(self, point_size: int) -> None:
        old_pt = self._data_store._font_pt
        self.set_font_pt(point_size)
        self.scale_columns_for_font(old_pt, self._data_store._font_pt)

    def apply_font_profile(self, profile: FontProfileLike) -> None:
        """Apply a complete font profile in dependency order."""
        if profile.regular_family:
            self.set_regular_font_family(profile.regular_family)
        self.set_editor_font_point_size(profile.editor_point_size)
        if profile.monospace_family:
            self.set_monospace_font_family(profile.monospace_family)
        self.set_monospace_fields_enabled(profile.monospace_fields_enabled)

    def resize_key_columns(self, force: bool = False) -> None:
        self._data_store._programmatic_column_resize = True
        try:
            view = self._require_view()
            for col in (0, 1):
                if force or col not in self._data_store._user_sized_columns:
                    view.resizeColumnToContents(col)
        finally:
            self._data_store._programmatic_column_resize = False

    def scale_columns_for_font(self, old_pt: int, new_pt: int) -> None:
        if old_pt <= 0 or new_pt <= 0 or old_pt == new_pt:
            return
        scale = new_pt / old_pt
        self._data_store._programmatic_column_resize = True
        try:
            view = self._require_view()
            for col in (0, 1):
                if col in self._data_store._user_sized_columns:
                    continue
                current = view.columnWidth(col)
                new_w = max(20, min(2000, int(current * scale)))
                view.setColumnWidth(col, new_w)
        finally:
            self._data_store._programmatic_column_resize = False

    def set_font_pt(self, pt: int) -> None:
        clamped = max(6, min(48, int(pt)))
        self._data_store._font_pt = clamped
        view = self._require_view()
        font = view.font()
        font.setPointSize(clamped)
        view.setFont(font)
        self.sync_icon_size_with_font()

    def sync_icon_size_with_font(self) -> None:
        view = self._require_view()
        px = max(12, min(64, int(round(view.fontMetrics().height() * 1.1))))
        view.setIconSize(QSize(px, px))

    def zoom_in(self) -> None:
        old_pt = self._data_store._font_pt
        self.set_font_pt(self._data_store._font_pt + 1)
        self.scale_columns_for_font(old_pt, self._data_store._font_pt)

    def zoom_out(self) -> None:
        old_pt = self._data_store._font_pt
        self.set_font_pt(self._data_store._font_pt - 1)
        self.scale_columns_for_font(old_pt, self._data_store._font_pt)

    def zoom_reset(self) -> None:
        old_pt = self._data_store._font_pt
        self.set_font_pt(self._data_store._default_font_pt)
        self.scale_columns_for_font(old_pt, self._data_store._font_pt)

    def _require_view(self) -> JsonTreeView:
        view = self._data_store.view
        if view is None:
            raise RuntimeError("JsonTab view is not initialized")
        return view

    def _require_model(self) -> JsonTreeModel:
        model = self._data_store.model
        if model is None:
            raise RuntimeError("JsonTab model is not initialized")
        return model

    def _require_name_delegate(self) -> NameDelegate:
        delegate = self._data_store.name_delegate
        if delegate is None:
            raise RuntimeError("JsonTab name delegate is not initialized")
        return delegate

    def _require_type_delegate(self) -> JsonTypeDelegate:
        delegate = self._data_store.type_delegate
        if delegate is None:
            raise RuntimeError("JsonTab type delegate is not initialized")
        return delegate

    def _require_value_delegate(self) -> ValueDelegate:
        delegate = self._data_store.value_delegate
        if delegate is None:
            raise RuntimeError("JsonTab value delegate is not initialized")
        return delegate

    def _require_icon_provider(self) -> IconProvider:
        icon_provider = self._icon_provider
        if icon_provider is None:
            raise RuntimeError("JsonTab icon provider is not initialized")
        return icon_provider


__all__ = ["FontProfileLike", "JsonTabAppearanceController"]
