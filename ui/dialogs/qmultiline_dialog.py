# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'qmultiline_dialog.ui'
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
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class Ui_QMultilineDialog(object):
    def setupUi(self, QMultilineDialog):
        if not QMultilineDialog.objectName():
            QMultilineDialog.setObjectName("QMultilineDialog")
        QMultilineDialog.resize(600, 440)
        self.verticalLayout = QVBoxLayout(QMultilineDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.controlsLayout = QHBoxLayout()
        self.controlsLayout.setObjectName("controlsLayout")
        self.wrapCheckBox = QCheckBox(QMultilineDialog)
        self.wrapCheckBox.setObjectName("wrapCheckBox")

        self.controlsLayout.addWidget(self.wrapCheckBox)

        self.lineNumbersCheckBox = QCheckBox(QMultilineDialog)
        self.lineNumbersCheckBox.setObjectName("lineNumbersCheckBox")

        self.controlsLayout.addWidget(self.lineNumbersCheckBox)

        self.monospacedCheckBox = QCheckBox(QMultilineDialog)
        self.monospacedCheckBox.setObjectName("monospacedCheckBox")

        self.controlsLayout.addWidget(self.monospacedCheckBox)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.controlsLayout.addItem(self.horizontalSpacer)

        self.verticalLayout.addLayout(self.controlsLayout)

        self.editorHost = QWidget(QMultilineDialog)
        self.editorHost.setObjectName("editorHost")

        self.verticalLayout.addWidget(self.editorHost)

        self.buttonBox = QDialogButtonBox(QMultilineDialog)
        self.buttonBox.setObjectName("buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(QMultilineDialog)

        QMetaObject.connectSlotsByName(QMultilineDialog)

    # setupUi

    def retranslateUi(self, QMultilineDialog):
        QMultilineDialog.setWindowTitle(QCoreApplication.translate("QMultilineDialog", "Edit Multiline Text", None))
        self.wrapCheckBox.setText(QCoreApplication.translate("QMultilineDialog", "Word wrap", None))
        self.lineNumbersCheckBox.setText(QCoreApplication.translate("QMultilineDialog", "Line numbers", None))
        self.monospacedCheckBox.setText(QCoreApplication.translate("QMultilineDialog", "Monospaced", None))

    # retranslateUi
