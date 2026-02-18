# ui/components/base_table_model.py

from PyQt5.QtCore import QAbstractTableModel, Qt, QModelIndex


class BaseTableModel(QAbstractTableModel):
    """
    Base reusable table model with:
    - items storage
    - column configuration
    - i18n support
    """

    def __init__(self, items=None, columns=None):
        super().__init__()
        self._items = items or []
        self._columns = columns or []
        self._is_arabic = False

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            _, header_en, header_ar = self._columns[section]
            return header_ar if self._is_arabic else header_en

        return section + 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        if role != Qt.DisplayRole:
            return None

        item = self._items[index.row()]
        key, _, _ = self._columns[index.column()]
        return getattr(item, key, "")

    def set_items(self, items):
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get_item(self, row: int):
        """Return the underlying item at `row` or None if out of range."""
        if row is None:
            return None
        if 0 <= int(row) < len(self._items):
            return self._items[int(row)]
        return None

    def set_language(self, is_arabic: bool):
        self._is_arabic = is_arabic
        self.layoutChanged.emit()
