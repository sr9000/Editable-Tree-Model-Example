# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'json_tab.ui'
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
from PySide6.QtWidgets import (QApplication, QHeaderView, QLineEdit, QSizePolicy,
    QVBoxLayout, QWidget)

from tree.view import JsonTreeView

class Ui_JsonTab(object):
    def setupUi(self, JsonTab):
        if not JsonTab.objectName():
            JsonTab.setObjectName(u"JsonTab")
        JsonTab.resize(480, 360)
        self.verticalLayout = QVBoxLayout(JsonTab)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.searchEdit = QLineEdit(JsonTab)
        self.searchEdit.setObjectName(u"searchEdit")

        self.verticalLayout.addWidget(self.searchEdit)

        self.treeView = JsonTreeView(JsonTab)
        self.treeView.setObjectName(u"treeView")

        self.verticalLayout.addWidget(self.treeView)


        self.retranslateUi(JsonTab)

        QMetaObject.connectSlotsByName(JsonTab)
    # setupUi

    def retranslateUi(self, JsonTab):
        self.searchEdit.setPlaceholderText(QCoreApplication.translate("JsonTab", u"Filter (Ctrl+F)", None))
        pass
    # retranslateUi

