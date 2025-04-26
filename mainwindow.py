# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainwindow.ui'
##
## Created by: Qt User Interface Compiler version 6.8.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QRect
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMenu,
    QMenuBar,
    QStatusBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(573, 468)
        self.exitAction = QAction(MainWindow)
        self.exitAction.setObjectName("exitAction")
        self.insertRowAction = QAction(MainWindow)
        self.insertRowAction.setObjectName("insertRowAction")
        self.removeRowAction = QAction(MainWindow)
        self.removeRowAction.setObjectName("removeRowAction")
        self.insertColumnAction = QAction(MainWindow)
        self.insertColumnAction.setObjectName("insertColumnAction")
        self.removeColumnAction = QAction(MainWindow)
        self.removeColumnAction.setObjectName("removeColumnAction")
        self.insertChildAction = QAction(MainWindow)
        self.insertChildAction.setObjectName("insertChildAction")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.vboxLayout = QVBoxLayout(self.centralwidget)
        self.vboxLayout.setSpacing(0)
        self.vboxLayout.setContentsMargins(0, 0, 0, 0)
        self.vboxLayout.setObjectName("vboxLayout")
        self.view = QTreeView(self.centralwidget)
        self.view.setObjectName("view")
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAnimated(False)
        self.view.setAllColumnsShowFocus(True)

        self.vboxLayout.addWidget(self.view)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName("menubar")
        self.menubar.setGeometry(QRect(0, 0, 573, 33))
        self.fileMenu = QMenu(self.menubar)
        self.fileMenu.setObjectName("fileMenu")
        self.actionsMenu = QMenu(self.menubar)
        self.actionsMenu.setObjectName("actionsMenu")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.fileMenu.menuAction())
        self.menubar.addAction(self.actionsMenu.menuAction())
        self.fileMenu.addAction(self.exitAction)
        self.actionsMenu.addAction(self.insertRowAction)
        self.actionsMenu.addAction(self.insertColumnAction)
        self.actionsMenu.addSeparator()
        self.actionsMenu.addAction(self.removeRowAction)
        self.actionsMenu.addAction(self.removeColumnAction)
        self.actionsMenu.addSeparator()
        self.actionsMenu.addAction(self.insertChildAction)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(
            QCoreApplication.translate("MainWindow", "Editable Tree Model", None)
        )
        self.exitAction.setText(QCoreApplication.translate("MainWindow", "E&xit", None))
        # if QT_CONFIG(shortcut)
        self.exitAction.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+Q", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.insertRowAction.setText(
            QCoreApplication.translate("MainWindow", "Insert Row", None)
        )
        # if QT_CONFIG(shortcut)
        self.insertRowAction.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+I, R", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.removeRowAction.setText(
            QCoreApplication.translate("MainWindow", "Remove Row", None)
        )
        # if QT_CONFIG(shortcut)
        self.removeRowAction.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+R, R", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.insertColumnAction.setText(
            QCoreApplication.translate("MainWindow", "Insert Column", None)
        )
        # if QT_CONFIG(shortcut)
        self.insertColumnAction.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+I, C", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.removeColumnAction.setText(
            QCoreApplication.translate("MainWindow", "Remove Column", None)
        )
        # if QT_CONFIG(shortcut)
        self.removeColumnAction.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+R, C", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.insertChildAction.setText(
            QCoreApplication.translate("MainWindow", "Insert Child", None)
        )
        # if QT_CONFIG(shortcut)
        self.insertChildAction.setShortcut(
            QCoreApplication.translate("MainWindow", "Ctrl+N", None)
        )
        # endif // QT_CONFIG(shortcut)
        self.fileMenu.setTitle(QCoreApplication.translate("MainWindow", "&File", None))
        self.actionsMenu.setTitle(
            QCoreApplication.translate("MainWindow", "&Actions", None)
        )

    # retranslateUi
