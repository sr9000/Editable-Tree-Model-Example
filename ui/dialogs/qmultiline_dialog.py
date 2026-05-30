# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'qmultiline_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QDialog,
    QDialogButtonBox, QHBoxLayout, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_QMultilineDialog(object):
    def setupUi(self, QMultilineDialog):
        if not QMultilineDialog.objectName():
            QMultilineDialog.setObjectName(u"QMultilineDialog")
        QMultilineDialog.resize(600, 440)
        self.verticalLayout = QVBoxLayout(QMultilineDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.controlsLayout = QHBoxLayout()
        self.controlsLayout.setObjectName(u"controlsLayout")
        self.wrapCheckBox = QCheckBox(QMultilineDialog)
        self.wrapCheckBox.setObjectName(u"wrapCheckBox")

        self.controlsLayout.addWidget(self.wrapCheckBox)

        self.lineNumbersCheckBox = QCheckBox(QMultilineDialog)
        self.lineNumbersCheckBox.setObjectName(u"lineNumbersCheckBox")

        self.controlsLayout.addWidget(self.lineNumbersCheckBox)

        self.monospacedCheckBox = QCheckBox(QMultilineDialog)
        self.monospacedCheckBox.setObjectName(u"monospacedCheckBox")

        self.controlsLayout.addWidget(self.monospacedCheckBox)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.controlsLayout.addItem(self.horizontalSpacer)


        self.verticalLayout.addLayout(self.controlsLayout)

        self.editorHost = QWidget(QMultilineDialog)
        self.editorHost.setObjectName(u"editorHost")

        self.verticalLayout.addWidget(self.editorHost)

        self.buttonBox = QDialogButtonBox(QMultilineDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(QMultilineDialog)

        QMetaObject.connectSlotsByName(QMultilineDialog)
    # setupUi

    def retranslateUi(self, QMultilineDialog):
        QMultilineDialog.setWindowTitle(QCoreApplication.translate("QMultilineDialog", u"Edit Multiline Text", None))
        self.wrapCheckBox.setText(QCoreApplication.translate("QMultilineDialog", u"Word wrap", None))
        self.lineNumbersCheckBox.setText(QCoreApplication.translate("QMultilineDialog", u"Line numbers", None))
        self.monospacedCheckBox.setText(QCoreApplication.translate("QMultilineDialog", u"Monospaced", None))
    # retranslateUi

