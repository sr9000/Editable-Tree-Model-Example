# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'secret_prefixes_dialog.ui'
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
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class Ui_SecretPrefixesDialog(object):
    def setupUi(self, SecretPrefixesDialog):
        if not SecretPrefixesDialog.objectName():
            SecretPrefixesDialog.setObjectName("SecretPrefixesDialog")
        SecretPrefixesDialog.resize(420, 320)
        self.verticalLayout = QVBoxLayout(SecretPrefixesDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.listWidget = QListWidget(SecretPrefixesDialog)
        self.listWidget.setObjectName("listWidget")

        self.verticalLayout.addWidget(self.listWidget)

        self.buttonsRowLayout = QHBoxLayout()
        self.buttonsRowLayout.setObjectName("buttonsRowLayout")
        self.addButton = QPushButton(SecretPrefixesDialog)
        self.addButton.setObjectName("addButton")

        self.buttonsRowLayout.addWidget(self.addButton)

        self.editButton = QPushButton(SecretPrefixesDialog)
        self.editButton.setObjectName("editButton")

        self.buttonsRowLayout.addWidget(self.editButton)

        self.removeButton = QPushButton(SecretPrefixesDialog)
        self.removeButton.setObjectName("removeButton")

        self.buttonsRowLayout.addWidget(self.removeButton)

        self.verticalLayout.addLayout(self.buttonsRowLayout)

        self.buttonBox = QDialogButtonBox(SecretPrefixesDialog)
        self.buttonBox.setObjectName("buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(SecretPrefixesDialog)

        QMetaObject.connectSlotsByName(SecretPrefixesDialog)

    # setupUi

    def retranslateUi(self, SecretPrefixesDialog):
        SecretPrefixesDialog.setWindowTitle(
            QCoreApplication.translate("SecretPrefixesDialog", "Secret word prefixes", None)
        )
        self.addButton.setText(QCoreApplication.translate("SecretPrefixesDialog", "Add", None))
        self.editButton.setText(QCoreApplication.translate("SecretPrefixesDialog", "Edit", None))
        self.removeButton.setText(QCoreApplication.translate("SecretPrefixesDialog", "Remove", None))

    # retranslateUi
