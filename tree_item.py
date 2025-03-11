"""
class TreeItem
{
public:
    explicit TreeItem(QVariantList data, TreeItem *parent = nullptr);

    TreeItem *child(int number);
    int childCount() const;
    int columnCount() const;
    QVariant data(int column) const;
    bool insertChildren(int position, int count, int columns);
    bool insertColumns(int position, int columns);
    TreeItem *parent();
    bool removeChildren(int position, int count);
    bool removeColumns(int position, int columns);
    int row() const;
    bool setData(int column, const QVariant &value);

private:
    std::vector<std::unique_ptr<TreeItem>> m_childItems;
    QVariantList itemData;
    TreeItem *m_parentItem;
};

TreeItem *TreeItem::parent()
{
    return m_parentItem;
}

TreeItem *TreeItem::child(int number)
{
    return (number >= 0 && number < childCount())
        ? m_childItems.at(number).get() : nullptr;
}

int TreeItem::childCount() const
{
    return int(m_childItems.size());
}

int TreeItem::row() const
{
    if (!m_parentItem)
        return 0;
    const auto it = std::find_if(m_parentItem->m_childItems.cbegin(), m_parentItem->m_childItems.cend(),
                                 [this](const std::unique_ptr<TreeItem> &treeItem) {
        return treeItem.get() == this;
    });

    if (it != m_parentItem->m_childItems.cend())
        return std::distance(m_parentItem->m_childItems.cbegin(), it);
    Q_ASSERT(false); // should not happen
    return -1;
}

int TreeItem::columnCount() const
{
    return int(itemData.count());
}

QVariant TreeItem::data(int column) const
{
    return itemData.value(column);
}

bool TreeItem::setData(int column, const QVariant &value)
{
    if (column < 0 || column >= itemData.size())
        return false;

    itemData[column] = value;
    return true;
}

bool TreeItem::insertChildren(int position, int count, int columns)
{
    if (position < 0 || position > qsizetype(m_childItems.size()))
        return false;

    for (int row = 0; row < count; ++row) {
        QVariantList data(columns);
        m_childItems.insert(m_childItems.cbegin() + position,
                std::make_unique<TreeItem>(data, this));
    }

    return true;
}

bool TreeItem::removeChildren(int position, int count)
{
    if (position < 0 || position + count > qsizetype(m_childItems.size()))
        return false;

    for (int row = 0; row < count; ++row)
        m_childItems.erase(m_childItems.cbegin() + position);

    return true;
}

bool TreeItem::insertColumns(int position, int columns)
{
    if (position < 0 || position > itemData.size())
        return false;

    for (int column = 0; column < columns; ++column)
        itemData.insert(position, QVariant());

    for (auto &child : std::as_const(m_childItems))
        child->insertColumns(position, columns);

    return true;
}
"""

from typing import Any


class TreeItem:
    def __init__(
        self,
        values: list[Any] = None,
        items: list[Any] = None,
        parent_item: "TreeItem" = None,
    ) -> None:
        self.parent_item: "TreeItem" = parent_item
        self.item_data: list = values or []
        self.child_items: list["TreeItem"] = []

        if items is None:
            return

        self.child_items: list["TreeItem"] = [
            TreeItem(it, parent_item=self) for it in items
        ]

    def append_child(self, child: "TreeItem") -> None:
        self.child_items.append(child)

    def parent(self) -> "TreeItem | None":
        return self.parent_item

    def child(self, number: int) -> "TreeItem | None":
        if 0 <= number < len(self.child_items):
            return self.child_items[number]

    def child_count(self) -> int:
        return len(self.child_items)

    def row(self) -> int:
        return (
            0 if self.parent_item is None else self.parent_item.child_items.index(self)
        )

    def column_count(self) -> int:
        return len(self.item_data)

    def data(self, column: int) -> Any:
        if 0 <= column < len(self.item_data):
            return self.item_data[column]

    def set_data(self, column: int, value: Any) -> bool:
        if 0 <= column < len(self.item_data):
            self.item_data[column] = value
            return True
        return False

    def insert_children(self, position: int, count: int, columns: int) -> bool:
        if 0 <= position <= len(self.child_items):
            self.child_items[position:position] = [
                TreeItem([None] * columns, parent_item=self) for _ in range(count)
            ]
            return True
        return False

    def remove_children(self, begin: int, count: int) -> bool:
        end = begin + count
        if 0 <= begin and end <= len(self.child_items):
            del self.child_items[begin:end]
            return True
        return False

    def insert_columns(self, position: int, columns: int) -> bool:
        if 0 <= position <= len(self.item_data):
            self.item_data[position:position] = [None] * columns
            if not all(
                child.insert_columns(position, columns) for child in self.child_items
            ):
                raise IndexError("Failed to insert columns in child items")
            return True
        return False

    def remove_columns(self, begin: int, columns: int) -> bool:
        """declared but not implemented in c++"""
        end = begin + columns
        if 0 <= begin and end <= len(self.item_data):
            del self.item_data[begin:end]
            if not all(
                child.remove_columns(begin, columns) for child in self.child_items
            ):
                raise IndexError("Failed to remove columns in child items")
            return True
        return False
