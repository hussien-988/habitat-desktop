# -*- coding: utf-8 -*-
"""RTL-aware QComboBox for Arabic right-to-left support.

Uses editable + read-only lineEdit to control text alignment,
which is the recommended workaround for Qt's lack of QSS text-align
support on QComboBox (QTBUG-46245).
"""

from PyQt5.QtWidgets import QComboBox
from PyQt5.QtCore import Qt, QTimer


def _resize_popup_to_items(combo: QComboBox):
    """Force popup view height to match the actual item count.

    Inside frameless+translucent dialogs, the popup container can grow
    while the inner QListView keeps a tiny viewport, leaving empty space
    above and below the items. Setting an explicit fixed height on the
    view fixes this.

    Must be deferred via QTimer to avoid the resize event closing the
    popup immediately after it opens.
    """
    view = combo.view()
    if not view.isVisible():
        return
    count = combo.count()
    if count <= 0:
        return
    row_h = view.sizeHintForRow(0)
    if row_h <= 0:
        return
    visible = min(count, combo.maxVisibleItems())
    target_h = row_h * visible + 8
    if view.height() != target_h:
        view.setFixedHeight(target_h)


class RtlCombo(QComboBox):
    """QComboBox with centered text and full-field click support.
    Uses editable + read-only lineEdit to control text alignment.
    changeEvent ensures alignment survives stylesheet changes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setAlignment(Qt.AlignCenter)
        self.lineEdit().installEventFilter(self)

    def showPopup(self):
        super().showPopup()
        QTimer.singleShot(0, lambda: _resize_popup_to_items(self))

    def eventFilter(self, obj, event):
        if obj == self.lineEdit() and event.type() == event.MouseButtonPress:
            self.showPopup()
            return True
        return super().eventFilter(obj, event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.StyleChange and self.lineEdit():
            self.lineEdit().setAlignment(Qt.AlignCenter)


class FixedPopupCombo(QComboBox):
    """QComboBox that resizes its popup view to fit items exactly.

    Use inside frameless+translucent dialogs to avoid empty space
    above/below the items in the dropdown.
    """

    def showPopup(self):
        super().showPopup()
        QTimer.singleShot(0, lambda: _resize_popup_to_items(self))
