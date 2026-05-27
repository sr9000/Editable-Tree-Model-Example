from __future__ import annotations

from importlib import resources

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QComboBox, QStyleOptionViewItem, QWidget

from delegates.type_delegate import JsonTypeDelegate
from documents.tab import JsonTab
from themes import LIGHT_DEFAULT, ThemeRegistry, load_theme_yaml
from themes.icon_provider import FileIconProvider, StubIconProvider
from tree.model import JsonTreeModel


def _builtin_light_theme():
    traversable = resources.files("themes.builtin").joinpath("light.yaml")
    with resources.as_file(traversable) as path:
        return load_theme_yaml(path, mode_default=LIGHT_DEFAULT)


def _iter_leaf_name_indexes(model: JsonTreeModel, parent: QModelIndex = QModelIndex()):
    for row in range(model.rowCount(parent)):
        idx = model.index(row, 0, parent)
        if not idx.isValid():
            continue
        if model.rowCount(idx) == 0:
            yield idx
            continue
        yield from _iter_leaf_name_indexes(model, idx)


def test_stub_provider_returns_null_icon_in_type_column():
    model = JsonTreeModel({"a": 1}, icon_provider=StubIconProvider())
    idx = model.index(0, 1, QModelIndex())

    icon = model.data(idx, Qt.ItemDataRole.DecorationRole)
    assert icon is not None
    assert icon.isNull() is True


def test_file_provider_returns_non_null_icons_for_leaf_rows():
    theme = _builtin_light_theme()
    model = JsonTreeModel({"a": 1, "b": "x", "nest": {"leaf": True}}, icon_provider=FileIconProvider(theme))

    leaf_rows = list(_iter_leaf_name_indexes(model))
    assert leaf_rows

    for name_idx in leaf_rows:
        type_idx = model.index(name_idx.row(), 1, name_idx.parent())
        icon = model.data(type_idx, Qt.ItemDataRole.DecorationRole)
        assert icon is not None
        assert icon.isNull() is False


def test_json_type_delegate_combobox_entries_have_icons(qtbot):
    theme = _builtin_light_theme()
    delegate = JsonTypeDelegate(theme=theme, icon_provider=FileIconProvider(theme))
    parent = QWidget()

    try:
        editor = delegate.createEditor(parent, QStyleOptionViewItem(), QModelIndex())
        assert isinstance(editor, QComboBox)
        assert editor.count() > 0

        for i in range(editor.count()):
            icon = editor.itemIcon(i)
            assert icon.isNull() is False
    finally:
        parent.deleteLater()


def test_json_tab_set_theme_emits_data_changed_for_type_column_icons(qtbot):
    registry = ThemeRegistry()
    light = registry.default_for_mode("light")
    dark = registry.default_for_mode("dark")
    light_icons = registry.build_icon_provider(light)
    dark_icons = registry.build_icon_provider(dark)

    tab = JsonTab(
        lambda *_args, **_kwargs: None,
        data={"a": 1, "b": {"c": 2}},
        show_root=True,
        theme=light,
        icon_provider=light_icons,
    )
    emissions: list[tuple[int, int, list[Qt.ItemDataRole]]] = []

    def _on_data_changed(top_left, bottom_right, roles):
        emissions.append((top_left.column(), bottom_right.column(), list(roles)))

    tab.data_store.model.dataChanged.connect(_on_data_changed)
    try:
        tab.set_theme(dark, dark_icons)
    finally:
        tab.deleteLater()

    assert emissions
    assert any(top_col <= 1 <= bottom_col for top_col, bottom_col, _roles in emissions)
    assert any(Qt.ItemDataRole.DecorationRole in roles for _top, _bottom, roles in emissions)
