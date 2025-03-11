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
    QTreeView, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(573, 468)
        self.exitAction = QAction(MainWindow)
        self.exitAction.setObjectName(u"exitAction")
        self.insertRowAction = QAction(MainWindow)
        self.insertRowAction.setObjectName(u"insertRowAction")
        self.removeRowAction = QAction(MainWindow)
        self.removeRowAction.setObjectName(u"removeRowAction")
        self.insertColumnAction = QAction(MainWindow)
        self.insertColumnAction.setObjectName(u"insertColumnAction")
        self.removeColumnAction = QAction(MainWindow)
        self.removeColumnAction.setObjectName(u"removeColumnAction")
        self.insertChildAction = QAction(MainWindow)
        self.insertChildAction.setObjectName(u"insertChildAction")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.vboxLayout = QVBoxLayout(self.centralwidget)
        self.vboxLayout.setSpacing(0)
        self.vboxLayout.setContentsMargins(0, 0, 0, 0)
        self.vboxLayout.setObjectName(u"vboxLayout")
        self.view = QTreeView(self.centralwidget)
        self.view.setObjectName(u"view")
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAnimated(False)
        self.view.setAllColumnsShowFocus(True)

        self.vboxLayout.addWidget(self.view)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 573, 33))
        self.fileMenu = QMenu(self.menubar)
        self.fileMenu.setObjectName(u"fileMenu")
        self.actionsMenu = QMenu(self.menubar)
        self.actionsMenu.setObjectName(u"actionsMenu")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
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
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Editable Tree Model", None))
        self.exitAction.setText(QCoreApplication.translate("MainWindow", u"E&xit", None))
#if QT_CONFIG(shortcut)
        self.exitAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Q", None))
#endif // QT_CONFIG(shortcut)
        self.insertRowAction.setText(QCoreApplication.translate("MainWindow", u"Insert Row", None))
#if QT_CONFIG(shortcut)
        self.insertRowAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+I, R", None))
#endif // QT_CONFIG(shortcut)
        self.removeRowAction.setText(QCoreApplication.translate("MainWindow", u"Remove Row", None))
#if QT_CONFIG(shortcut)
        self.removeRowAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+R, R", None))
#endif // QT_CONFIG(shortcut)
        self.insertColumnAction.setText(QCoreApplication.translate("MainWindow", u"Insert Column", None))
#if QT_CONFIG(shortcut)
        self.insertColumnAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+I, C", None))
#endif // QT_CONFIG(shortcut)
        self.removeColumnAction.setText(QCoreApplication.translate("MainWindow", u"Remove Column", None))
#if QT_CONFIG(shortcut)
        self.removeColumnAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+R, C", None))
#endif // QT_CONFIG(shortcut)
        self.insertChildAction.setText(QCoreApplication.translate("MainWindow", u"Insert Child", None))
#if QT_CONFIG(shortcut)
        self.insertChildAction.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+N", None))
#endif // QT_CONFIG(shortcut)
        self.fileMenu.setTitle(QCoreApplication.translate("MainWindow", u"&File", None))
        self.actionsMenu.setTitle(QCoreApplication.translate("MainWindow", u"&Actions", None))
    # retranslateUi

