# --- ui.h ---
# #ifndef MAINWINDOW_H
# #define MAINWINDOW_H
#
# #include "mainwindow.h"
#
# #include <QMainWindow>
#
# class MainWindow : public QMainWindow, private Ui::MainWindow
# {
#     Q_OBJECT
#
# public:
#     MainWindow(QWidget *parent = nullptr);
#
# public slots:
#     void updateActions();
#
# private slots:
#     void insertChild();
#     bool insertColumn();
#     void insertRow();
#     bool removeColumn();
#     void removeRow();
# };
#
# --- ui.cpp ---
#
# #include "ui.h"
# #include "treemodel.h"
#
# #include <QDebug>
# #include <QFile>
#
# using namespace Qt::StringLiterals;
#
# MainWindow::MainWindow(QWidget *parent)
#     : QMainWindow(parent)
# {
#     setupUi(this);
#
#     const QStringList headers({tr("Title"), tr("Description")});
#
#     QFile file(":/default.txt"_L1);
#     file.open(QIODevice::ReadOnly | QIODevice::Text);
#     auto *model = new TreeModel(headers, QString::fromUtf8(file.readAll()), this);
#     file.close();
#
#     view->setModel(model);
#     for (int column = 0; column < model->columnCount(); ++column)
#         view->resizeColumnToContents(column);
#     view->expandAll();
#
#     connect(exitAction, &QAction::triggered, qApp, &QCoreApplication::quit);
#
#     connect(view->selectionModel(), &QItemSelectionModel::selectionChanged,
#             this, &MainWindow::updateActions);
#
#     connect(actionsMenu, &QMenu::aboutToShow, this, &MainWindow::updateActions);
#     connect(insertRowAction, &QAction::triggered, this, &MainWindow::insertRow);
#     connect(insertColumnAction, &QAction::triggered, this, &MainWindow::insertColumn);
#     connect(removeRowAction, &QAction::triggered, this, &MainWindow::removeRow);
#     connect(removeColumnAction, &QAction::triggered, this, &MainWindow::removeColumn);
#     connect(insertChildAction, &QAction::triggered, this, &MainWindow::insertChild);
#
#     updateActions();
# }
#
# void MainWindow::insertChild()
# {
#     const QModelIndex index = view->selectionModel()->currentIndex();
#     QAbstractItemModel *model = view->model();
#
#     if (model->columnCount(index) == 0) {
#         if (!model->insertColumn(0, index))
#             return;
#     }
#
#     if (!model->insertRow(0, index))
#         return;
#
#     for (int column = 0; column < model->columnCount(index); ++column) {
#         const QModelIndex child = model->index(0, column, index);
#         model->setData(child, QVariant(tr("[No data]")), Qt::EditRole);
#         if (!model->headerData(column, Qt::Horizontal).isValid())
#             model->setHeaderData(column, Qt::Horizontal, QVariant(tr("[No header]")), Qt::EditRole);
#     }
#
#     view->selectionModel()->setCurrentIndex(model->index(0, 0, index),
#                                             QItemSelectionModel::ClearAndSelect);
#     updateActions();
# }
#
# bool MainWindow::insertColumn()
# {
#     QAbstractItemModel *model = view->model();
#     int column = view->selectionModel()->currentIndex().column();
#
#     // Insert a column in the parent item.
#     bool changed = model->insertColumn(column + 1);
#     if (changed)
#         model->setHeaderData(column + 1, Qt::Horizontal, QVariant("[No header]"), Qt::EditRole);
#
#     updateActions();
#
#     return changed;
# }
#
# void MainWindow::insertRow()
# {
#     const QModelIndex index = view->selectionModel()->currentIndex();
#     QAbstractItemModel *model = view->model();
#
#     if (!model->insertRow(index.row()+1, index.parent()))
#         return;
#
#     updateActions();
#
#     for (int column = 0; column < model->columnCount(index.parent()); ++column) {
#         const QModelIndex child = model->index(index.row() + 1, column, index.parent());
#         model->setData(child, QVariant(tr("[No data]")), Qt::EditRole);
#     }
# }
#
# bool MainWindow::removeColumn()
# {
#     QAbstractItemModel *model = view->model();
#     const int column = view->selectionModel()->currentIndex().column();
#
#     // Insert columns in each child of the parent item.
#     const bool changed = model->removeColumn(column);
#     if (changed)
#         updateActions();
#
#     return changed;
# }
#
# void MainWindow::removeRow()
# {
#     const QModelIndex index = view->selectionModel()->currentIndex();
#     QAbstractItemModel *model = view->model();
#     if (model->removeRow(index.row(), index.parent()))
#         updateActions();
# }
#
# void MainWindow::updateActions()
# {
#     const bool hasSelection = !view->selectionModel()->selection().isEmpty();
#     removeRowAction->setEnabled(hasSelection);
#     removeColumnAction->setEnabled(hasSelection);
#
#     const bool hasCurrent = view->selectionModel()->currentIndex().isValid();
#     insertRowAction->setEnabled(hasCurrent);
#     insertColumnAction->setEnabled(hasCurrent);
#
#     if (hasCurrent) {
#         view->closePersistentEditor(view->selectionModel()->currentIndex());
#
#         const int row = view->selectionModel()->currentIndex().row();
#         const int column = view->selectionModel()->currentIndex().column();
#         if (view->selectionModel()->currentIndex().parent().isValid())
#             statusBar()->showMessage(tr("Position: (%1,%2)").arg(row).arg(column));
#         else
#             statusBar()->showMessage(tr("Position: (%1,%2) in top level").arg(row).arg(column));
#     }
# }

import yaml
from PySide6.QtCore import QCoreApplication, Qt, QItemSelectionModel
from PySide6.QtWidgets import (
    QMainWindow,
)

from mainwindow import Ui_MainWindow
from tree_model import TreeModel


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, yaml_filename: str, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setupModel(yaml_filename)
        self.setupConnections()

    def setupModel(self, yaml_filename: str):
        with open(yaml_filename) as file:
            data = yaml.safe_load(file)

        self.model = TreeModel(data, self, ["Title", "Description"])
        self.view.setModel(self.model)

        for column in range(self.model.columnCount()):
            self.view.resizeColumnToContents(column)

        self.view.expandAll()

    def setupConnections(self):
        self.exitAction.triggered.connect(QCoreApplication.quit)
        self.view.selectionModel().selectionChanged.connect(self.updateActions)

        self.actionsMenu.aboutToShow.connect(self.updateActions)
        self.insertRowAction.triggered.connect(self.insertRow)
        self.insertColumnAction.triggered.connect(self.insertColumn)
        self.removeRowAction.triggered.connect(self.removeRow)
        self.removeColumnAction.triggered.connect(self.removeColumn)
        self.insertChildAction.triggered.connect(self.insertChild)

        self.updateActions()

    def insertChild(self):
        index = self.view.selectionModel().currentIndex()
        model = self.view.model()

        if model.columnCount(index) == 0:
            if not model.insertColumn(0, index):
                return

        if not model.insertRow(0, index):
            return

        for column in range(model.columnCount(index)):
            child = model.index(0, column, index)
            model.setData(child, "[No data]", Qt.ItemDataRole.EditRole)
            if model.headerData(column, Qt.Orientation.Horizontal) is None:
                model.setHeaderData(
                    column,
                    Qt.Orientation.Horizontal,
                    "[No header]",
                    Qt.ItemDataRole.EditRole,
                )

        self.view.selectionModel().setCurrentIndex(
            model.index(0, 0, index), QItemSelectionModel.SelectionFlag.ClearAndSelect
        )
        self.view.expand(model.index(0, 0, index))
        self.updateActions()

    def insertColumn(self):
        model = self.view.model()
        column = self.view.selectionModel().currentIndex().column()
        changed = model.insertColumn(column + 1)

        if changed:
            model.setHeaderData(
                column + 1,
                Qt.Orientation.Horizontal,
                "[No header]",
                Qt.ItemDataRole.EditRole,
            )

        self.updateActions()

        return changed

    def insertRow(self):
        index = self.view.selectionModel().currentIndex()
        model = self.view.model()

        if not model.insertRow(index.row() + 1, index.parent()):
            return

        self.updateActions()

        for column in range(model.columnCount(index.parent())):
            child = model.index(index.row() + 1, column, index.parent())
            model.setData(child, "[No data]", Qt.ItemDataRole.EditRole)

    def removeColumn(self):
        model = self.view.model()
        column = self.view.selectionModel().currentIndex().column()
        changed = model.removeColumn(column)

        if changed:
            self.updateActions()

        return changed

    def removeRow(self):
        index = self.view.selectionModel().currentIndex()
        model = self.view.model()

        if model.removeRow(index.row(), index.parent()):
            self.updateActions()

    def updateActions(self):
        hasSelection = not self.view.selectionModel().selection().isEmpty()
        self.removeRowAction.setEnabled(hasSelection)
        self.removeColumnAction.setEnabled(hasSelection)

        hasCurrent = self.view.selectionModel().currentIndex().isValid()
        self.insertRowAction.setEnabled(hasCurrent)
        self.insertColumnAction.setEnabled(hasCurrent)

        if hasCurrent:
            self.view.closePersistentEditor(self.view.selectionModel().currentIndex())
            row = self.view.selectionModel().currentIndex().row()
            column = self.view.selectionModel().currentIndex().column()

            if self.view.selectionModel().currentIndex().parent().isValid():
                self.statusBar().showMessage(f"Position: ({row},{column})")
            else:
                self.statusBar().showMessage(f"Position: ({row},{column}) in top level")
