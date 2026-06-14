# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainwindow.ui'
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
    QAction,
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
    QApplication,
    QMainWindow,
    QMenu,
    QMenuBar,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(573, 468)
        self.appExitAction = QAction(MainWindow)
        self.appExitAction.setObjectName("appExitAction")
        self.rowInsertAction = QAction(MainWindow)
        self.rowInsertAction.setObjectName("rowInsertAction")
        self.rowRemoveAction = QAction(MainWindow)
        self.rowRemoveAction.setObjectName("rowRemoveAction")
        self.fileCreateNewAction = QAction(MainWindow)
        self.fileCreateNewAction.setObjectName("fileCreateNewAction")
        self.fileOpenAction = QAction(MainWindow)
        self.fileOpenAction.setObjectName("fileOpenAction")
        self.fileSaveAction = QAction(MainWindow)
        self.fileSaveAction.setObjectName("fileSaveAction")
        self.fileSaveAsAction = QAction(MainWindow)
        self.fileSaveAsAction.setObjectName("fileSaveAsAction")
        self.rowInsertAfterAction = QAction(MainWindow)
        self.rowInsertAfterAction.setObjectName("rowInsertAfterAction")
        self.viewExpandAllAction = QAction(MainWindow)
        self.viewExpandAllAction.setObjectName("viewExpandAllAction")
        self.viewCollapseAllAction = QAction(MainWindow)
        self.viewCollapseAllAction.setObjectName("viewCollapseAllAction")
        self.viewZoomInAction = QAction(MainWindow)
        self.viewZoomInAction.setObjectName("viewZoomInAction")
        self.viewZoomOutAction = QAction(MainWindow)
        self.viewZoomOutAction.setObjectName("viewZoomOutAction")
        self.viewResetZoomAction = QAction(MainWindow)
        self.viewResetZoomAction.setObjectName("viewResetZoomAction")
        self.fileCopyPathAction = QAction(MainWindow)
        self.fileCopyPathAction.setObjectName("fileCopyPathAction")
        self.centralWidget = QWidget(MainWindow)
        self.centralWidget.setObjectName("centralWidget")
        self.vboxLayout = QVBoxLayout(self.centralWidget)
        self.vboxLayout.setSpacing(0)
        self.vboxLayout.setContentsMargins(0, 0, 0, 0)
        self.vboxLayout.setObjectName("vboxLayout")
        self.tabWidget = QTabWidget(self.centralWidget)
        self.tabWidget.setObjectName("tabWidget")
        self.tabWidget.setDocumentMode(True)
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.setMovable(True)

        self.vboxLayout.addWidget(self.tabWidget)

        MainWindow.setCentralWidget(self.centralWidget)
        self.menuBar = QMenuBar(MainWindow)
        self.menuBar.setObjectName("menuBar")
        self.menuBar.setGeometry(QRect(0, 0, 573, 33))
        self.fileMenu = QMenu(self.menuBar)
        self.fileMenu.setObjectName("fileMenu")
        self.actionsMenu = QMenu(self.menuBar)
        self.actionsMenu.setObjectName("actionsMenu")
        self.viewMenu = QMenu(self.menuBar)
        self.viewMenu.setObjectName("viewMenu")
        MainWindow.setMenuBar(self.menuBar)
        self.statusBar = QStatusBar(MainWindow)
        self.statusBar.setObjectName("statusBar")
        MainWindow.setStatusBar(self.statusBar)

        self.menuBar.addAction(self.fileMenu.menuAction())
        self.menuBar.addAction(self.actionsMenu.menuAction())
        self.menuBar.addAction(self.viewMenu.menuAction())
        self.fileMenu.addAction(self.fileCreateNewAction)
        self.fileMenu.addAction(self.fileOpenAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.fileSaveAction)
        self.fileMenu.addAction(self.fileSaveAsAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.fileCopyPathAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.appExitAction)
        self.actionsMenu.addAction(self.rowInsertAction)
        self.actionsMenu.addAction(self.rowInsertAfterAction)
        self.actionsMenu.addSeparator()
        self.actionsMenu.addAction(self.rowRemoveAction)
        self.viewMenu.addAction(self.viewExpandAllAction)
        self.viewMenu.addAction(self.viewCollapseAllAction)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.viewZoomInAction)
        self.viewMenu.addAction(self.viewZoomOutAction)
        self.viewMenu.addAction(self.viewResetZoomAction)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(-1)

        QMetaObject.connectSlotsByName(MainWindow)

    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", "Editable Tree Model", None))
        self.appExitAction.setText(QCoreApplication.translate("MainWindow", "&Exit", None))
        # if QT_CONFIG(shortcut)
        self.appExitAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+Q", None))
        # endif // QT_CONFIG(shortcut)
        self.rowInsertAction.setText(QCoreApplication.translate("MainWindow", "&Insert Row", None))
        # if QT_CONFIG(shortcut)
        self.rowInsertAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+I", None))
        # endif // QT_CONFIG(shortcut)
        self.rowRemoveAction.setText(QCoreApplication.translate("MainWindow", "&Remove Row", None))
        # if QT_CONFIG(shortcut)
        self.rowRemoveAction.setShortcut(QCoreApplication.translate("MainWindow", "Del", None))
        # endif // QT_CONFIG(shortcut)
        self.fileCreateNewAction.setText(QCoreApplication.translate("MainWindow", "Create &New", None))
        # if QT_CONFIG(shortcut)
        self.fileCreateNewAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+N", None))
        # endif // QT_CONFIG(shortcut)
        self.fileOpenAction.setText(QCoreApplication.translate("MainWindow", "&Open File", None))
        # if QT_CONFIG(shortcut)
        self.fileOpenAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+O", None))
        # endif // QT_CONFIG(shortcut)
        self.fileSaveAction.setText(QCoreApplication.translate("MainWindow", "&Save File", None))
        # if QT_CONFIG(shortcut)
        self.fileSaveAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+S", None))
        # endif // QT_CONFIG(shortcut)
        self.fileSaveAsAction.setText(QCoreApplication.translate("MainWindow", "Save File &as ...", None))
        # if QT_CONFIG(shortcut)
        self.fileSaveAsAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+Shift+S", None))
        # endif // QT_CONFIG(shortcut)
        self.rowInsertAfterAction.setText(QCoreApplication.translate("MainWindow", "Insert Row &after", None))
        # if QT_CONFIG(shortcut)
        self.rowInsertAfterAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+Shift+I", None))
        # endif // QT_CONFIG(shortcut)
        self.viewExpandAllAction.setText(QCoreApplication.translate("MainWindow", "Expand All", None))
        self.viewCollapseAllAction.setText(QCoreApplication.translate("MainWindow", "Collapse All", None))
        self.viewZoomInAction.setText(QCoreApplication.translate("MainWindow", "Zoom In", None))
        # if QT_CONFIG(shortcut)
        self.viewZoomInAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl++", None))
        # endif // QT_CONFIG(shortcut)
        self.viewZoomOutAction.setText(QCoreApplication.translate("MainWindow", "Zoom Out", None))
        # if QT_CONFIG(shortcut)
        self.viewZoomOutAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+-", None))
        # endif // QT_CONFIG(shortcut)
        self.viewResetZoomAction.setText(QCoreApplication.translate("MainWindow", "Reset Zoom", None))
        # if QT_CONFIG(shortcut)
        self.viewResetZoomAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+0", None))
        # endif // QT_CONFIG(shortcut)
        self.fileCopyPathAction.setText(QCoreApplication.translate("MainWindow", "Copy Full File &Path", None))
        # if QT_CONFIG(tooltip)
        self.fileCopyPathAction.setToolTip(
            QCoreApplication.translate("MainWindow", "Copy absolute path of the current document", None)
        )
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(shortcut)
        self.fileCopyPathAction.setShortcut(QCoreApplication.translate("MainWindow", "Ctrl+Alt+C", None))
        # endif // QT_CONFIG(shortcut)
        self.fileMenu.setTitle(QCoreApplication.translate("MainWindow", "&File", None))
        self.actionsMenu.setTitle(QCoreApplication.translate("MainWindow", "&Actions", None))
        self.viewMenu.setTitle(QCoreApplication.translate("MainWindow", "&View", None))

    # retranslateUi
