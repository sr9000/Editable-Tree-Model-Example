from __future__ import annotations

from typing import Iterable

from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QWidget)

from editors.inline.bigint_spinbox import QBigIntSpinBox
from editors.inline.mpq_spinbox import QMpqSpinBox
from units.number_affix import AffixKind, NumberAffix


class AffixCompositeEditor(QWidget):
    """Inline editor pairing an affix combo with a numeric spinbox.

    App-agnostic: the host decides the affix ``kind`` and whether the
    number is an integer; this widget knows nothing about ``JsonType``.
    """

    def __init__(self, parent: QWidget, *, kind: AffixKind, is_integer: bool, mru_items: Iterable[str]) -> None:
        super().__init__(parent)
        self.kind = kind

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        affix_label_text = "Currency: " if self.kind is AffixKind.CURRENCY else "Units: "
        self.affix_label = QLabel(affix_label_text, self)
        self.affix_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        self.affix_combo = QComboBox(self)
        self.affix_combo.setEditable(True)
        self.affix_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.affix_combo.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.affix_combo.setMinimumContentsLength(1)

        self.space_button = QPushButton(self._space_button_text(False), parent=self)
        self.space_button.setCheckable(True)
        self.space_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.space_button.setToolTip("Space between affix and number")
        self.space_button.toggled.connect(self._on_space_toggled)
        self._update_space_button_width()

        if is_integer:
            self.number_editor = QBigIntSpinBox(self)
        else:
            self.number_editor = QMpqSpinBox(self)
        self.number_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.value_label = QLabel("Value: ", self)

        value_font = self.number_editor.font()
        self.affix_label.setFont(value_font)
        self.value_label.setFont(value_font)

        for affix in mru_items:
            if affix:
                self.affix_combo.addItem(affix)

        layout.addWidget(self.space_button)
        layout.addWidget(self.affix_label)
        layout.addWidget(self.affix_combo)
        layout.addWidget(self.value_label)
        layout.addWidget(self.number_editor)

    @staticmethod
    def _space_button_text(spaced: bool) -> str:
        return "Spaced out" if spaced else "Joined-up"

    def _on_space_toggled(self, checked: bool) -> None:
        self.space_button.setText(self._space_button_text(bool(checked)))

    def _update_space_button_width(self) -> None:
        metrics = QFontMetrics(self.space_button.font())
        width = (
            max(
                metrics.horizontalAdvance(self._space_button_text(False)),
                metrics.horizontalAdvance(self._space_button_text(True)),
            )
            + 18
        )
        self.space_button.setFixedWidth(width)

    def setFont(self, font: QFont) -> None:
        super().setFont(font)
        self._update_space_button_width()

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
