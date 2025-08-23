# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainwindow.ui'
##
## Created by: Qt User Interface Compiler version 6.8.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QHeaderView, QMainWindow,
    QMenu, QMenuBar, QSizePolicy, QStatusBar,
    QTabWidget, QTreeView, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(573, 468)
        self.appExitAction = QAction(MainWindow)
        self.appExitAction.setObjectName(u"appExitAction")
        self.rowInsertAction = QAction(MainWindow)
        self.rowInsertAction.setObjectName(u"rowInsertAction")
        self.rowRemoveAction = QAction(MainWindow)
        self.rowRemoveAction.setObjectName(u"rowRemoveAction")
        self.fileCreateNewAction = QAction(MainWindow)
        self.fileCreateNewAction.setObjectName(u"fileCreateNewAction")
        self.fileOpenAction = QAction(MainWindow)
        self.fileOpenAction.setObjectName(u"fileOpenAction")
        self.fileSaveAction = QAction(MainWindow)
        self.fileSaveAction.setObjectName(u"fileSaveAction")
        self.fileSaveAsAction = QAction(MainWindow)
        self.fileSaveAsAction.setObjectName(u"fileSaveAsAction")
        self.rowInsertAfterAction = QAction(MainWindow)
        self.rowInsertAfterAction.setObjectName(u"rowInsertAfterAction")
        self.centralWidget = QWidget(MainWindow)
        self.centralWidget.setObjectName(u"centralWidget")
        self.vboxLayout = QVBoxLayout(self.centralWidget)
        self.vboxLayout.setSpacing(0)
        self.vboxLayout.setContentsMargins(0, 0, 0, 0)
        self.vboxLayout.setObjectName(u"vboxLayout")
        self.tabWidget = QTabWidget(self.centralWidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.verticalLayout = QVBoxLayout(self.tab)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.view = QTreeView(self.tab)
        self.view.setObjectName(u"view")
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAnimated(False)
        self.view.setAllColumnsShowFocus(True)

        self.verticalLayout.addWidget(self.view)

        self.tabWidget.addTab(self.tab, "")

        self.vboxLayout.addWidget(self.tabWidget)

        MainWindow.setCentralWidget(self.centralWidget)
        self.menuBar = QMenuBar(MainWindow)
        self.menuBar.setObjectName(u"menuBar")
        self.menuBar.setGeometry(QRect(0, 0, 573, 33))
        self.fileMenu = QMenu(self.menuBar)
        self.fileMenu.setObjectName(u"fileMenu")
        self.actionsMenu = QMenu(self.menuBar)
        self.actionsMenu.setObjectName(u"actionsMenu")
        MainWindow.setMenuBar(self.menuBar)
        self.statusBar = QStatusBar(MainWindow)
        self.statusBar.setObjectName(u"statusBar")
        MainWindow.setStatusBar(self.statusBar)

        self.menuBar.addAction(self.fileMenu.menuAction())
        self.menuBar.addAction(self.actionsMenu.menuAction())
        self.fileMenu.addAction(self.fileCreateNewAction)
        self.fileMenu.addAction(self.fileOpenAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.fileSaveAction)
        self.fileMenu.addAction(self.fileSaveAsAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.appExitAction)
        self.actionsMenu.addAction(self.rowInsertAction)
        self.actionsMenu.addAction(self.rowInsertAfterAction)
        self.actionsMenu.addSeparator()
        self.actionsMenu.addAction(self.rowRemoveAction)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Editable Tree Model", None))
        self.appExitAction.setText(QCoreApplication.translate("MainWindow", u"&Exit", None))
#if QT_CONFIG(shortcut)
        self.appExitAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Q", None))
#endif // QT_CONFIG(shortcut)
        self.rowInsertAction.setText(QCoreApplication.translate("MainWindow", u"&Insert Row", None))
#if QT_CONFIG(shortcut)
        self.rowInsertAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+I", None))
#endif // QT_CONFIG(shortcut)
        self.rowRemoveAction.setText(QCoreApplication.translate("MainWindow", u"&Remove Row", None))
#if QT_CONFIG(shortcut)
        self.rowRemoveAction.setShortcut(QCoreApplication.translate("MainWindow", u"Del", None))
#endif // QT_CONFIG(shortcut)
        self.fileCreateNewAction.setText(QCoreApplication.translate("MainWindow", u"Create &New", None))
#if QT_CONFIG(shortcut)
        self.fileCreateNewAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+N", None))
#endif // QT_CONFIG(shortcut)
        self.fileOpenAction.setText(QCoreApplication.translate("MainWindow", u"&Open File", None))
#if QT_CONFIG(shortcut)
        self.fileOpenAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+O", None))
#endif // QT_CONFIG(shortcut)
        self.fileSaveAction.setText(QCoreApplication.translate("MainWindow", u"&Save File", None))
#if QT_CONFIG(shortcut)
        self.fileSaveAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+S", None))
#endif // QT_CONFIG(shortcut)
        self.fileSaveAsAction.setText(QCoreApplication.translate("MainWindow", u"Save File &as ...", None))
#if QT_CONFIG(shortcut)
        self.fileSaveAsAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Shift+S", None))
#endif // QT_CONFIG(shortcut)
        self.rowInsertAfterAction.setText(QCoreApplication.translate("MainWindow", u"Insert Row &after", None))
#if QT_CONFIG(shortcut)
        self.rowInsertAfterAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Shift+I", None))
#endif // QT_CONFIG(shortcut)
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab), QCoreApplication.translate("MainWindow", u"New JSON", None))
        self.fileMenu.setTitle(QCoreApplication.translate("MainWindow", u"&File", None))
        self.actionsMenu.setTitle(QCoreApplication.translate("MainWindow", u"&Actions", None))
    # retranslateUi

