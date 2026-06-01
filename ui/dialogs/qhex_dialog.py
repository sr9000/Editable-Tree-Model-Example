# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'qhex_dialog.ui'
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
    QStatusBar, QVBoxLayout, QWidget)

class Ui_QHexDialog(object):
    def setupUi(self, QHexDialog):
        if not QHexDialog.objectName():
            QHexDialog.setObjectName(u"QHexDialog")
        QHexDialog.resize(600, 440)
        self.verticalLayout = QVBoxLayout(QHexDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.controlsLayout = QHBoxLayout()
        self.controlsLayout.setObjectName(u"controlsLayout")
        self.addressCheckBox = QCheckBox(QHexDialog)
        self.addressCheckBox.setObjectName(u"addressCheckBox")

        self.controlsLayout.addWidget(self.addressCheckBox)

        self.asciiCheckBox = QCheckBox(QHexDialog)
        self.asciiCheckBox.setObjectName(u"asciiCheckBox")

        self.controlsLayout.addWidget(self.asciiCheckBox)

        self.highlightingCheckBox = QCheckBox(QHexDialog)
        self.highlightingCheckBox.setObjectName(u"highlightingCheckBox")

        self.controlsLayout.addWidget(self.highlightingCheckBox)

        self.capsCheckBox = QCheckBox(QHexDialog)
        self.capsCheckBox.setObjectName(u"capsCheckBox")

        self.controlsLayout.addWidget(self.capsCheckBox)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.controlsLayout.addItem(self.horizontalSpacer)


        self.verticalLayout.addLayout(self.controlsLayout)

        self.editorHost = QWidget(QHexDialog)
        self.editorHost.setObjectName(u"editorHost")

        self.verticalLayout.addWidget(self.editorHost)

        self.statusBar = QStatusBar(QHexDialog)
        self.statusBar.setObjectName(u"statusBar")

        self.verticalLayout.addWidget(self.statusBar)

        self.buttonBox = QDialogButtonBox(QHexDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(QHexDialog)

        QMetaObject.connectSlotsByName(QHexDialog)
    # setupUi

    def retranslateUi(self, QHexDialog):
        QHexDialog.setWindowTitle(QCoreApplication.translate("QHexDialog", u"Edit Binary Data", None))
        self.addressCheckBox.setText(QCoreApplication.translate("QHexDialog", u"Address area", None))
        self.asciiCheckBox.setText(QCoreApplication.translate("QHexDialog", u"ASCII area", None))
        self.highlightingCheckBox.setText(QCoreApplication.translate("QHexDialog", u"Modified bytes", None))
        self.capsCheckBox.setText(QCoreApplication.translate("QHexDialog", u"CAPS", None))
    # retranslateUi

