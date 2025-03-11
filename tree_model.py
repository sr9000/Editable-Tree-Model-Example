"""
class TreeModel : public QAbstractItemModel
{
    Q_OBJECT

public:
    Q_DISABLE_COPY_MOVE(TreeModel)

    TreeModel(const QStringList &headers, const QString &data,
              QObject *parent = nullptr);
    ~TreeModel() override;

    // Read-only tree models only need to provide following public functions.
    QVariant data(const QModelIndex &index, int role) const override;
    QVariant headerData(int section, Qt::Orientation orientation,
                        int role = Qt::DisplayRole) const override;

    QModelIndex index(int row, int column,
                      const QModelIndex &parent = {}) const override;
    QModelIndex parent(const QModelIndex &index) const override;

    int rowCount(const QModelIndex &parent = {}) const override;
    int columnCount(const QModelIndex &parent = {}) const override;

    // The following public functions provide support for editing and resizing.

    Qt::ItemFlags flags(const QModelIndex &index) const override;
    bool setData(const QModelIndex &index, const QVariant &value,
                 int role = Qt::EditRole) override;
    bool setHeaderData(int section, Qt::Orientation orientation,
                       const QVariant &value, int role = Qt::EditRole) override;

    bool insertColumns(int position, int columns,
                       const QModelIndex &parent = {}) override;
    bool removeColumns(int position, int columns,
                       const QModelIndex &parent = {}) override;
    bool insertRows(int position, int rows,
                    const QModelIndex &parent = {}) override;
    bool removeRows(int position, int rows,
                    const QModelIndex &parent = {}) override;

private:
    void setupModelData(const QList<QStringView> &lines);
    TreeItem *getItem(const QModelIndex &index) const;

    std::unique_ptr<TreeItem> rootItem;
};

TreeModel::TreeModel(const QStringList &headers, const QString &data, QObject *parent)
    : QAbstractItemModel(parent)
{
    QVariantList rootData;
    for (const QString &header : headers)
        rootData << header;

    rootItem = std::make_unique<TreeItem>(rootData);
    setupModelData(QStringView{data}.split(u'\n'));
}

TreeModel::~TreeModel() = default;

TreeItem *TreeModel::getItem(const QModelIndex &index) const
{
    if (index.isValid()) {
        if (auto *item = static_cast<TreeItem*>(index.internalPointer()))
            return item;
    }
    return rootItem.get();
}

int TreeModel::rowCount(const QModelIndex &parent) const
{
    if (parent.isValid() && parent.column() > 0)
        return 0;

    const TreeItem *parentItem = getItem(parent);

    return parentItem ? parentItem->childCount() : 0;
}

int TreeModel::columnCount(const QModelIndex &parent) const
{
    Q_UNUSED(parent);
    return rootItem->columnCount();
}

Qt::ItemFlags TreeModel::flags(const QModelIndex &index) const
{
    if (!index.isValid())
        return Qt::NoItemFlags;

    return Qt::ItemIsEditable | QAbstractItemModel::flags(index);
}

QModelIndex TreeModel::index(int row, int column, const QModelIndex &parent) const
{
    if (parent.isValid() && parent.column() != 0)
        return {};

    // In this model, we only return model indexes for child items
    // if the parent index is invalid (corresponding to the root item)
    // or if it has a zero column number.

    // We use the custom getItem() function to obtain a TreeItem instance
    // that corresponds to the model index supplied,
    // and request its child item that corresponds to the specified row.

    TreeItem *parentItem = getItem(parent);
    if (!parentItem)
        return {};

    if (auto *childItem = parentItem->child(row))
        return createIndex(row, column, childItem);
    return {};
}

QModelIndex TreeModel::parent(const QModelIndex &index) const
{
    if (!index.isValid())
        return {};

    TreeItem *childItem = getItem(index);
    TreeItem *parentItem = childItem ? childItem->parent() : nullptr;

    return (parentItem != rootItem.get() && parentItem != nullptr)
        ? createIndex(parentItem->row(), 0, parentItem) : QModelIndex{};
}

// https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel/treemodel.cpp?h=6.8

bool TreeModel::insertColumns(int position, int columns, const QModelIndex &parent)
{
    beginInsertColumns(parent, position, position + columns - 1);
    const bool success = rootItem->insertColumns(position, columns);
    endInsertColumns();

    return success;
}

bool TreeModel::insertRows(int position, int rows, const QModelIndex &parent)
{
    TreeItem *parentItem = getItem(parent);
    if (!parentItem)
        return false;

    beginInsertRows(parent, position, position + rows - 1);
    const bool success = parentItem->insertChildren(position,
                                                    rows,
                                                    rootItem->columnCount());
    endInsertRows();

    return success;
}

bool TreeModel::removeColumns(int position, int columns, const QModelIndex &parent)
{
    beginRemoveColumns(parent, position, position + columns - 1);
    const bool success = rootItem->removeColumns(position, columns);
    endRemoveColumns();

    if (rootItem->columnCount() == 0)
        removeRows(0, rowCount());

    return success;
}

bool TreeModel::removeRows(int position, int rows, const QModelIndex &parent)
{
    TreeItem *parentItem = getItem(parent);
    if (!parentItem)
        return false;

    beginRemoveRows(parent, position, position + rows - 1);
    const bool success = parentItem->removeChildren(position, rows);
    endRemoveRows();

    return success;
}

bool TreeModel::setData(const QModelIndex &index, const QVariant &value, int role)
{
    if (role != Qt::EditRole)
        return false;

    TreeItem *item = getItem(index);
    bool result = item->setData(index.column(), value);

    if (result)
        emit dataChanged(index, index, {Qt::DisplayRole, Qt::EditRole});

    return result;
}

bool TreeModel::setHeaderData(int section, Qt::Orientation orientation,
                              const QVariant &value, int role)
{
    if (role != Qt::EditRole || orientation != Qt::Horizontal)
        return false;

    const bool result = rootItem->setData(section, value);

    if (result)
        emit headerDataChanged(orientation, section, section);

    return result;
}
"""

from contextlib import contextmanager
from typing import Optional, Any, Mapping

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from tree_item import TreeItem


def setup_model_data(items: list[Mapping[str, Any]], root: TreeItem) -> None:
    for it in items:
        root.append_child(
            TreeItem([it["title"], it["description"]], it.get("items", None), root)
        )


class TreeModel(QAbstractItemModel):
    def __init__(
        self,
        items: list[Mapping[str, Any]],
        /,
        parent: Optional[Any] = None,
        values: list[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.root_item = TreeItem(values or [])
        setup_model_data(items, self.root_item)

    def get_item(self, index: QModelIndex) -> TreeItem:
        if index.isValid() and (item := index.internalPointer()):
            return item
        return self.root_item

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() and parent.column() != 0:
            return 0  # No children for column != 0
        return self.get_item(parent).child_count()

    def columnCount(self, _: QModelIndex = QModelIndex()) -> int:
        return self.root_item.column_count()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if index.isValid():
            return Qt.ItemFlag.ItemIsEditable | QAbstractItemModel.flags(self, index)
        return Qt.ItemFlag.NoItemFlags

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()
        if childItem := self.get_item(parent).child(row):
            return self.createIndex(row, column, childItem)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        parent_item = self.get_item(index).parent()

        if parent_item not in (self.root_item, None):
            return self.createIndex(parent_item.row(), 0, parent_item)
        return QModelIndex()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return self.get_item(index).data(index.column())

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.root_item.data(section)

    @contextmanager
    def columns_insertion(self, parent: QModelIndex, position: int, columns: int):
        self.beginInsertColumns(parent, position, position + columns - 1)
        try:
            yield
        finally:
            self.endInsertColumns()

    def insertColumns(
        self, position: int, columns: int, parent: QModelIndex = QModelIndex()
    ) -> bool:
        with self.columns_insertion(parent, position, columns):
            return self.root_item.insert_columns(position, columns)

    @contextmanager
    def rows_insertion(self, parent: QModelIndex, position: int, rows: int):
        self.beginInsertRows(parent, position, position + rows - 1)
        try:
            yield
        finally:
            self.endInsertRows()

    def insertRows(
        self, position: int, rows: int, parent: QModelIndex = QModelIndex()
    ) -> bool:
        if parent_item := self.get_item(parent):
            with self.rows_insertion(parent, position, rows):
                return parent_item.insert_children(
                    position, rows, self.root_item.column_count()
                )
        return False

    @contextmanager
    def columns_removal(self, parent: QModelIndex, position: int, columns: int):
        self.beginRemoveColumns(parent, position, position + columns - 1)
        try:
            yield
        finally:
            self.endRemoveColumns()
            self.cleanup_columns_removal()

    def cleanup_columns_removal(self):
        """Remove rows if there are no columns left."""
        if self.root_item.column_count() == 0:
            self.removeRows(0, self.rowCount())

    def removeColumns(
        self, position: int, columns: int, parent: QModelIndex = QModelIndex()
    ) -> bool:
        with self.columns_removal(parent, position, columns):
            return self.root_item.remove_columns(position, columns)

    @contextmanager
    def rows_removal(self, parent: QModelIndex, position: int, rows: int):
        self.beginRemoveRows(parent, position, position + rows - 1)
        try:
            yield
        finally:
            self.endRemoveRows()

    def removeRows(
        self, position: int, rows: int, parent: QModelIndex = QModelIndex()
    ) -> bool:
        if parent_item := self.get_item(parent):
            with self.rows_removal(parent, position, rows):
                return parent_item.remove_children(position, rows)
        return False

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role == Qt.ItemDataRole.EditRole:
            if self.get_item(index).set_data(index.column(), value):
                roles = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
                self.dataChanged.emit(index, index, roles)
                return True
        return False

    def setHeaderData(
        self,
        section: int,
        orientation: Qt.Orientation,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if (
            role == Qt.ItemDataRole.EditRole
            and orientation == Qt.Orientation.Horizontal
        ):
            if self.root_item.set_data(section, value):
                self.headerDataChanged.emit(orientation, section, section)
                return True
        return False
