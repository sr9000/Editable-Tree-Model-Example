from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QSizePolicy, QToolButton, QWidget

from qbigint_spinbox import QBigIntSpinBox
from qmpq_spinbox import QMpqSpinBox
from settings import NUMBER_AFFIX_MAX_LEN
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix, format_number_affix, parse_number_affix

_AFFIX_TYPES = {
    JsonType.INTEGER_CURRENCY,
    JsonType.INTEGER_UNITS,
    JsonType.FLOAT_CURRENCY,
    JsonType.FLOAT_UNITS,
}


def is_affix_json_type(json_type: JsonType) -> bool:
    return json_type in _AFFIX_TYPES


def kind_for_json_type(json_type: JsonType) -> AffixKind:
    return AffixKind.CURRENCY if json_type in (JsonType.INTEGER_CURRENCY, JsonType.FLOAT_CURRENCY) else AffixKind.UNITS


def is_integer_json_type(json_type: JsonType) -> bool:
    return json_type in (JsonType.INTEGER_CURRENCY, JsonType.INTEGER_UNITS)


class AffixCompositeEditor(QWidget):
    def __init__(
        self,
        parent: QWidget,
        *,
        json_type: JsonType,
        affix_icon: QIcon | None,
        mru_items: Iterable[str],
    ) -> None:
        super().__init__(parent)
        self._json_type = json_type
        self.kind = kind_for_json_type(json_type)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.affix_combo = QComboBox(self)
        self.affix_combo.setEditable(True)
        self.affix_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.affix_combo.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.affix_combo.setMinimumContentsLength(1)
        if affix_icon is not None and not affix_icon.isNull() and self.affix_combo.lineEdit() is not None:
            self.affix_combo.lineEdit().addAction(
                affix_icon, self.affix_combo.lineEdit().ActionPosition.LeadingPosition
            )

        self.space_button = QToolButton(self)
        self.space_button.setCheckable(True)
        self.space_button.setAutoRaise(True)
        self.space_button.setToolTip("Space between affix and number")
        self.space_button.setFixedSize(16, 16)

        if is_integer_json_type(json_type):
            self.number_editor = QBigIntSpinBox(self)
        else:
            self.number_editor = QMpqSpinBox(self)
        self.number_editor.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        for affix in mru_items:
            if affix:
                self.affix_combo.addItem(affix)

        if self.kind is AffixKind.CURRENCY:
            layout.addWidget(self.affix_combo)
            layout.addWidget(self.space_button)
            layout.addWidget(self.number_editor)
        else:
            layout.addWidget(self.number_editor)
            layout.addWidget(self.space_button)
            layout.addWidget(self.affix_combo)

    def set_invalid(self, invalid: bool) -> None:
        self.setProperty("invalid", bool(invalid))
        if invalid:
            self.setStyleSheet("QComboBox, QAbstractSpinBox { border: 1px solid #cc3333; }")
        else:
            self.setStyleSheet("")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_value(self, value: NumberAffix) -> None:
        text = value.affix
        idx = self.affix_combo.findText(text)
        if idx >= 0:
            self.affix_combo.setCurrentIndex(idx)
        else:
            self.affix_combo.insertItem(0, text)
            self.affix_combo.setCurrentIndex(0)
        if self.affix_combo.lineEdit() is not None:
            self.affix_combo.lineEdit().setText(text)
        self.space_button.setChecked(bool(value.space))
        self.number_editor.setValue(value.number)
        self.set_invalid(False)

    def build_value(self) -> NumberAffix:
        affix = self.affix_combo.currentText()
        return NumberAffix(
            kind=self.kind,
            affix=affix,
            space=self.space_button.isChecked(),
            number=self.number_editor.value(),
        )


def normalize_affix_value(value, json_type: JsonType) -> NumberAffix | None:
    if isinstance(value, NumberAffix):
        return value
    if isinstance(value, str):
        parsed = parse_number_affix(value, max_affix_len=NUMBER_AFFIX_MAX_LEN)
        if parsed is not None:
            return parsed
    return None


def validate_affix_value(value: NumberAffix) -> NumberAffix | None:
    try:
        text = format_number_affix(value)
    except ValueError:
        return None
    return parse_number_affix(text, max_affix_len=NUMBER_AFFIX_MAX_LEN)
