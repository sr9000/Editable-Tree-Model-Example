# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'attach_schema_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (
    QCoreApplication,
    QDate,
    QDateTime,
    QLocale,
    QMetaObject,
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTime,
    QUrl,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QCursor,
    QFont,
    QFontDatabase,
    QGradient,
    QIcon,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPalette,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class Ui_AttachSchemaDialog(object):
    def setupUi(self, AttachSchemaDialog):
        if not AttachSchemaDialog.objectName():
            AttachSchemaDialog.setObjectName("AttachSchemaDialog")
        AttachSchemaDialog.resize(540, 110)
        self.verticalLayout = QVBoxLayout(AttachSchemaDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.recentRowWidget = QWidget(AttachSchemaDialog)
        self.recentRowWidget.setObjectName("recentRowWidget")
        self.recentRowLayout = QHBoxLayout(self.recentRowWidget)
        self.recentRowLayout.setObjectName("recentRowLayout")
        self.recentRowLayout.setContentsMargins(0, 0, 0, 0)
        self.recentLabel = QLabel(self.recentRowWidget)
        self.recentLabel.setObjectName("recentLabel")

        self.recentRowLayout.addWidget(self.recentLabel)

        self.recentComboBox = QComboBox(self.recentRowWidget)
        self.recentComboBox.setObjectName("recentComboBox")

        self.recentRowLayout.addWidget(self.recentComboBox)

        self.verticalLayout.addWidget(self.recentRowWidget)

        self.pathLabel = QLabel(AttachSchemaDialog)
        self.pathLabel.setObjectName("pathLabel")

        self.verticalLayout.addWidget(self.pathLabel)

        self.pathRowLayout = QHBoxLayout()
        self.pathRowLayout.setObjectName("pathRowLayout")
        self.pathLineEdit = QLineEdit(AttachSchemaDialog)
        self.pathLineEdit.setObjectName("pathLineEdit")

        self.pathRowLayout.addWidget(self.pathLineEdit)

        self.browseButton = QPushButton(AttachSchemaDialog)
        self.browseButton.setObjectName("browseButton")

        self.pathRowLayout.addWidget(self.browseButton)

        self.verticalLayout.addLayout(self.pathRowLayout)

        self.buttonBox = QDialogButtonBox(AttachSchemaDialog)
        self.buttonBox.setObjectName("buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(AttachSchemaDialog)

        QMetaObject.connectSlotsByName(AttachSchemaDialog)

    # setupUi

    def retranslateUi(self, AttachSchemaDialog):
        AttachSchemaDialog.setWindowTitle(QCoreApplication.translate("AttachSchemaDialog", "Attach JSON Schema", None))
        self.recentLabel.setText(QCoreApplication.translate("AttachSchemaDialog", "Recent schemas:", None))
        self.pathLabel.setText(
            QCoreApplication.translate("AttachSchemaDialog", "Schema file path or URL (http/https):", None)
        )
        self.pathLineEdit.setPlaceholderText(
            QCoreApplication.translate("AttachSchemaDialog", "https://...  or  /path/to/schema.json", None)
        )
        self.browseButton.setText(QCoreApplication.translate("AttachSchemaDialog", "Browse...", None))

    # retranslateUi
