from __future__ import annotations

import pytest
from gmpy2 import mpq
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem

from delegates.formatting.bytes_codec import encode_bytes
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate
from documents.tab import JsonTab
from themes import DARK_DEFAULT, LIGHT_DEFAULT, parse_theme_mapping
from tree.model import JsonTreeModel
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix


def _color_hex(color) -> str:
    return color.name().lower()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _index_for_type(json_type: JsonType):
    model = JsonTreeModel({"v": None})
    type_index = model.index(0, 1, QModelIndex())
    value_index = model.index(0, 2, QModelIndex())

    # Pseudo text types (EMPTY_*, WS_*) are purely content-derived and not
    # user-selectable via the type combobox. To put an item into one of those
    # states we seed the value with content that text_pseudotype_for collapses
    # to the desired pseudo while the item is already in its parent shape.
    pseudo_seeds: dict[JsonType, tuple[JsonType, str]] = {
        JsonType.EMPTY_STRING: (JsonType.STRING, ""),
        JsonType.EMPTY_MULTILINE: (JsonType.MULTILINE, ""),
        JsonType.WS_STRING: (JsonType.STRING, "   "),
        JsonType.WS_UNICODE: (JsonType.STRING, " \u00a0 "),
        JsonType.WS_MULTILINE: (JsonType.MULTILINE, "  \n  "),
        JsonType.WS_TEXT: (JsonType.MULTILINE, " \u00a0\n\u3000 "),
    }
    if json_type in pseudo_seeds:
        parent, seed = pseudo_seeds[json_type]
        assert model.setData(type_index, parent, Qt.ItemDataRole.EditRole)
        assert model.setData(value_index, seed, Qt.ItemDataRole.EditRole)
        item = model.get_item(model.index(0, 0, QModelIndex()))
        assert item.json_type is json_type, f"Expected {json_type}, got {item.json_type}"
        return model, value_index

    assert model.setData(type_index, json_type, Qt.ItemDataRole.EditRole)

    sample_values = {
        JsonType.INTEGER: 1,
        JsonType.FLOAT: mpq("3/2"),
        JsonType.PERCENT: mpq("1/2"),
        JsonType.INTEGER_CURRENCY: NumberAffix(AffixKind.CURRENCY, "$", False, 12),
        JsonType.INTEGER_UNITS: NumberAffix(AffixKind.UNITS, "kg", True, 12),
        JsonType.FLOAT_CURRENCY: NumberAffix(AffixKind.CURRENCY, "$", True, mpq("3/2")),
        JsonType.FLOAT_UNITS: NumberAffix(AffixKind.UNITS, "rad", False, mpq("3/2")),
        JsonType.BOOLEAN: True,
        JsonType.STRING: "ascii",
        JsonType.UNICODE: "caf\u00e9",
        JsonType.MULTILINE: "line 1\nline 2",
        JsonType.TEXT: "line 1\n\u03a9",
        JsonType.SECRET_LINE: "plainsecret",
        JsonType.SECRET_TEXT: "line 1\nline 2",
        JsonType.DATE: "2024-06-01",
        JsonType.TIME: "12:34:56",
        JsonType.DATETIME: "2024-06-01 12:34:56",
        JsonType.DATETIMEUTC: "2024-06-01T12:34:56Z",
        JsonType.DATETIMEZONE: "2024-06-01T12:34:56+00:00",
        JsonType.BYTES: "dGVzdA==",
        JsonType.ZLIB: encode_bytes(b"test", JsonType.ZLIB),
        JsonType.GZIP: encode_bytes(b"test", JsonType.GZIP),
        JsonType.NULL: None,
        JsonType.OBJECT: {},
        JsonType.ARRAY: [],
        JsonType.COLOR_RGB: "#3498db",
        JsonType.COLOR_RGBA: "#3498db80",
    }
    assert model.setData(value_index, sample_values[json_type], Qt.ItemDataRole.EditRole)
    return model, value_index


@pytest.mark.parametrize("json_type", list(JsonType))
def test_value_delegate_uses_theme_foreground_per_json_type(json_type, qapp):
    model, value_index = _index_for_type(json_type)
    style = LIGHT_DEFAULT.types[json_type]

    if style.fg is None:
        pytest.skip("Theme style has no foreground color for this type")

    delegate = ValueDelegate(theme=LIGHT_DEFAULT)
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, value_index)

    assert _color_hex(option.palette.color(option.palette.ColorRole.Text)) == _color_hex(style.fg)


def test_value_delegate_selected_does_not_override_foreground(qapp):
    model, value_index = _index_for_type(JsonType.INTEGER)

    light_delegate = ValueDelegate(theme=LIGHT_DEFAULT)
    dark_delegate = ValueDelegate(theme=DARK_DEFAULT)

    light_option = QStyleOptionViewItem()
    light_option.state |= QStyle.StateFlag.State_Selected
    light_delegate.initStyleOption(light_option, value_index)

    dark_option = QStyleOptionViewItem()
    dark_option.state |= QStyle.StateFlag.State_Selected
    dark_delegate.initStyleOption(dark_option, value_index)

    assert _color_hex(light_option.palette.color(light_option.palette.ColorRole.Text)) == _color_hex(
        dark_option.palette.color(dark_option.palette.ColorRole.Text)
    )


def test_value_delegate_applies_theme_bold_italic(qapp):
    themed = parse_theme_mapping(
        {
            "name": "Bold Italic",
            "mode": "light",
            "types": {
                "integer": {"bold": True, "italic": True},
            },
        },
        mode_default=LIGHT_DEFAULT,
    )

    model, value_index = _index_for_type(JsonType.INTEGER)
    delegate = ValueDelegate(theme=themed)
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, value_index)

    assert option.font.bold() is True
    assert option.font.italic() is True


def test_type_delegate_applies_theme_foreground_for_type_column(qapp):
    model = JsonTreeModel({"v": 1})
    type_index = model.index(0, 1, QModelIndex())
    delegate = JsonTypeDelegate(theme=LIGHT_DEFAULT)
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, type_index)

    style = LIGHT_DEFAULT.types[JsonType.INTEGER]
    assert style.fg is not None
    assert _color_hex(option.palette.color(option.palette.ColorRole.Text)) == _color_hex(style.fg)


def test_value_delegate_init_style_option_does_not_overflow_for_bigint(qapp):
    """Regression: initStyleOption must not raise OverflowError for integers
    that exceed Qt's 8-byte signed integer limit (bigints stored verbatim in
    JsonTreeItem bypass the QVariant round-trip that would explode)."""
    BIG = 738_765_433_567_890_087_654_354_678_798_000
    model = JsonTreeModel({"big": BIG})
    type_index = model.index(0, 1, QModelIndex())
    assert model.setData(type_index, JsonType.INTEGER, Qt.ItemDataRole.EditRole)
    value_index = model.index(0, 2, QModelIndex())

    delegate = ValueDelegate(theme=LIGHT_DEFAULT)
    option = QStyleOptionViewItem()
    # Must not raise OverflowError.
    delegate.initStyleOption(option, value_index)

    assert str(BIG) in option.text


def test_json_tab_set_theme_emits_repaint_data_changed(qapp):
    tab = JsonTab(lambda *_args, **_kwargs: None, data={"a": 1, "b": {"c": 2}}, show_root=True, theme=LIGHT_DEFAULT)
    signals = []

    def _on_data_changed(top_left, bottom_right, roles):
        signals.append((top_left, bottom_right, list(roles)))

    tab.model.dataChanged.connect(_on_data_changed)
    try:
        tab.appearance.set_theme(DARK_DEFAULT)
    finally:
        tab.deleteLater()

    assert signals
    assert any(top.column() == 0 and bottom.column() == 2 for top, bottom, _ in signals)
    assert any(
        Qt.ItemDataRole.ForegroundRole in roles
        and Qt.ItemDataRole.BackgroundRole in roles
        and Qt.ItemDataRole.FontRole in roles
        for _, _, roles in signals
    )
