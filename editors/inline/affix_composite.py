from __future__ import annotations

from typing import Iterable

from gmpy2 import mpq
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSpinBox, QWidget

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
        self._integral_digits = 0
        self._fractional_digits = -1

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

        self.plus_button = QPushButton("Plain", parent=self)
        self.plus_button.setCheckable(True)
        self.plus_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.plus_button.setToolTip("Preserve explicit leading plus for positive values")
        self.plus_button.toggled.connect(self._on_plus_toggled)

        self.width_button = QPushButton("Short", parent=self)
        self.width_button.setCheckable(True)
        self.width_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.width_button.setToolTip("Preserve leading zeros")
        self.width_button.toggled.connect(self._on_width_toggled)

        self.width_spinbox = QSpinBox(self)
        self.width_spinbox.setRange(1, 999_999)
        self.width_spinbox.setValue(1)
        self.width_spinbox.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.width_spinbox.setToolTip("Number of integral digits to preserve")
        self.width_spinbox.setVisible(False)

        if is_integer:
            self.number_editor = QBigIntSpinBox(self)
            self.precision_button = None
            self.precision_spinbox = None
        else:
            self.number_editor = QMpqSpinBox(self)
            self.precision_button = QPushButton("Strip", parent=self)
            self.precision_button.setCheckable(True)
            self.precision_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
            self.precision_button.setToolTip("Preserve trailing zeros")
            self.precision_button.toggled.connect(self._on_precision_toggled)
            self.precision_spinbox = QSpinBox(self)
            self.precision_spinbox.setRange(0, 999_999)
            self.precision_spinbox.setValue(0)
            self.precision_spinbox.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
            self.precision_spinbox.setToolTip("Number of fractional digits to preserve")
            self.precision_spinbox.setVisible(False)
            self.precision_spinbox.valueChanged.connect(self._on_precision_digits_changed)
        self.number_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.value_label = QLabel("Value: ", self)

        value_font = self.number_editor.font()
        self.affix_label.setFont(value_font)
        self.value_label.setFont(value_font)

        for affix in mru_items:
            if affix:
                self.affix_combo.addItem(affix)

        layout.addWidget(self.space_button)
        layout.addWidget(self.plus_button)
        layout.addWidget(self.width_button)
        layout.addWidget(self.width_spinbox)
        if self.precision_button:
            layout.addWidget(self.precision_button)
            layout.addWidget(self.precision_spinbox)
        layout.addWidget(self.affix_label)
        layout.addWidget(self.affix_combo)
        layout.addWidget(self.value_label)
        layout.addWidget(self.number_editor)

    @staticmethod
    def _space_button_text(spaced: bool) -> str:
        return "Spaced out" if spaced else "Joined-up"

    def _on_space_toggled(self, checked: bool) -> None:
        self.space_button.setText(self._space_button_text(bool(checked)))

    def _on_plus_toggled(self, checked: bool) -> None:
        self.plus_button.setText("Plus" if checked else "Plain")

    def _on_width_toggled(self, checked: bool) -> None:
        self.width_button.setText("Width" if checked else "Short")
        self.width_spinbox.setVisible(bool(checked))
        if checked and self._integral_digits <= 0 and self.width_spinbox.value() == 1:
            self.width_spinbox.setValue(self._infer_integral_digits())

    def _on_precision_toggled(self, checked: bool) -> None:
        self.precision_button.setText("Precision" if checked else "Strip")
        self.precision_spinbox.setVisible(bool(checked))
        if checked and self._fractional_digits < 0 and self.precision_spinbox.value() == 0:
            self.precision_spinbox.setValue(self._infer_fractional_digits())
        self._apply_fractional_step()

    def _on_precision_digits_changed(self, _value: int) -> None:
        self._apply_fractional_step()

    def _infer_integral_digits(self) -> int:
        text = self.number_editor.cleanText()
        digits = text.lstrip("+-").split(".", 1)[0]
        return max(1, len(digits))

    def _infer_fractional_digits(self) -> int:
        text = self.number_editor.cleanText()
        parts = text.split(".", 1)
        if len(parts) == 2:
            return len(parts[1])
        return 0

    def _apply_fractional_step(self) -> None:
        if not isinstance(self.number_editor, QMpqSpinBox):
            return

        digits = self._infer_fractional_digits()
        if self.precision_button and self.precision_button.isChecked() and self.precision_spinbox is not None:
            digits = self.precision_spinbox.value()

        if digits <= 0:
            self.number_editor.setSingleStep(mpq(1))
            return

        self.number_editor.setSingleStep(mpq(1, 10**digits))

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
        self.plus_button.setChecked(bool(value.explicit_plus))

        self.number_editor.setValue(value.number)
        self.set_invalid(False)

        self._integral_digits = value.integral_digits
        self._fractional_digits = value.fractional_digits

        self.width_spinbox.setValue(
            self._integral_digits if self._integral_digits > 0 else self._infer_integral_digits()
        )
        self.width_button.setChecked(self._integral_digits > 0)

        if self.precision_button:
            self.precision_spinbox.setValue(
                self._fractional_digits if self._fractional_digits >= 0 else self._infer_fractional_digits()
            )
            self.precision_button.setChecked(self._fractional_digits >= 0)

        self._apply_fractional_step()

    def build_value(self) -> NumberAffix:
        affix = self.affix_combo.currentText()
        new_integral = self.width_spinbox.value() if self.width_button.isChecked() else 0

        new_fractional = -1
        if self.precision_button and self.precision_button.isChecked() and self.precision_spinbox is not None:
            new_fractional = self.precision_spinbox.value()

        return NumberAffix(
            kind=self.kind,
            affix=affix,
            space=self.space_button.isChecked(),
            number=self.number_editor.value(),
            integral_digits=new_integral,
            fractional_digits=new_fractional,
            explicit_plus=self.plus_button.isChecked() and self.number_editor.value() >= 0,
        )
