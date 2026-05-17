from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from validation.schema_registry import SchemaSource


class AttachSchemaDialog(QDialog):
    def __init__(self, parent=None, *, start_dir: str = "") -> None:
        super().__init__(parent)
        self._start_dir = start_dir

        self.setWindowTitle(self.tr("Attach JSON Schema"))
        self.resize(540, 110)

        label = QLabel(self.tr("Schema file path or URL (http/https):"), self)
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText("https://...  or  /path/to/schema.json")

        browse = QPushButton(self.tr("Browse..."), self)
        browse.clicked.connect(self._browse)

        row = QHBoxLayout()
        row.addWidget(self._edit, 1)
        row.addWidget(browse)

        buttons = QDialogButtonBox(parent=self)
        buttons.setStandardButtons(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addLayout(row)
        layout.addWidget(buttons)

    @classmethod
    def ask(cls, parent=None, *, start_dir: str = "") -> SchemaSource | None:
        dlg = cls(parent, start_dir=start_dir)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.source()

    @classmethod
    def parse_source(cls, raw: str, *, start_dir: str = "") -> SchemaSource | None:
        text = raw.strip()
        if not text:
            return None
        lowered = text.casefold()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            return SchemaSource.for_url(text)

        start = Path(start_dir).expanduser() if start_dir else None
        base_dir = start.parent if start is not None and start.suffix else start

        candidate = Path(text).expanduser()
        if not candidate.is_absolute() and base_dir is not None:
            candidate = base_dir / candidate
        if not candidate.exists() or not candidate.is_file():
            return None
        return SchemaSource.for_file(candidate)

    def source(self) -> SchemaSource | None:
        return self.parse_source(self._edit.text(), start_dir=self._start_dir)

    def _browse(self) -> None:
        picked, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Schema File"),
            self._start_dir,
            self.tr("JSON Schema (*.json *.yaml *.yml);;All files (*)"),
        )
        if picked:
            self._edit.setText(picked)
