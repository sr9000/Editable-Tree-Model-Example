from __future__ import annotations

from typing import Iterable

from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

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

        self.width_button = QPushButton("Width", parent=self)
        self.width_button.setCheckable(True)
        self.width_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.width_button.setToolTip("Preserve leading zeros")
        self.width_button.toggled.connect(self._on_width_toggled)

        if is_integer:
            self.number_editor = QBigIntSpinBox(self)
            self.precision_button = None
        else:
            self.number_editor = QMpqSpinBox(self)
            self.precision_button = QPushButton("Precision", parent=self)
            self.precision_button.setCheckable(True)
            self.precision_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
            self.precision_button.setToolTip("Preserve trailing zeros")
            self.precision_button.toggled.connect(self._on_precision_toggled)
        self.number_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.value_label = QLabel("Value: ", self)

        value_font = self.number_editor.font()
        self.affix_label.setFont(value_font)
        self.value_label.setFont(value_font)

        for affix in mru_items:
            if affix:
                self.affix_combo.addItem(affix)

        layout.addWidget(self.space_button)
        layout.addWidget(self.width_button)
        if self.precision_button:
            layout.addWidget(self.precision_button)
        layout.addWidget(self.affix_label)
        layout.addWidget(self.affix_combo)
        layout.addWidget(self.value_label)
        layout.addWidget(self.number_editor)

    @staticmethod
    def _space_button_text(spaced: bool) -> str:
        return "Spaced out" if spaced else "Joined-up"

    def _on_space_toggled(self, checked: bool) -> None:
        self.space_button.setText(self._space_button_text(bool(checked)))

    def _on_width_toggled(self, checked: bool) -> None:
        self.width_button.setText("Width" if checked else "Short")

    def _on_precision_toggled(self, checked: bool) -> None:
        self.precision_button.setText("Precision" if checked else "Strip")

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

        if isinstance(self.number_editor, QMpqSpinBox):
            if value.fractional_digits >= 0:
                self.number_editor.setSingleStep(mpq(1, 10**value.fractional_digits))

        self.number_editor.setValue(value.number)
        self.set_invalid(False)

        # Store for unmodified round-trip
        self._integral_digits = value.integral_digits
        self._fractional_digits = value.fractional_digits
        self.width_button.setChecked(self._integral_digits > 0)
        self._on_width_toggled(self._integral_digits > 0)
        if self.precision_button:
            self.precision_button.setChecked(self._fractional_digits >= 0)
            self._on_precision_toggled(self._fractional_digits >= 0)

    def build_value(self) -> NumberAffix:
        affix = self.affix_combo.currentText()
        new_integral = self._integral_digits if self.width_button.isChecked() else 0

        new_fractional = -1
        if self.precision_button and self.precision_button.isChecked():
            new_fractional = self._fractional_digits
            if new_fractional < 0:
                new_fractional = 1

        return NumberAffix(
            kind=self.kind,
            affix=affix,
            space=self.space_button.isChecked(),
            number=self.number_editor.value(),
            integral_digits=new_integral,
            fractional_digits=new_fractional,
        )
