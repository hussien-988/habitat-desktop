# -*- coding: utf-8 -*-
"""RTL-aware QComboBox for Arabic right-to-left support.

Uses editable + read-only lineEdit to control text alignment,
which is the recommended workaround for Qt's lack of QSS text-align
support on QComboBox (QTBUG-46245).
"""

from PyQt5.QtWidgets import QComboBox
from PyQt5.QtCore import Qt


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

    def eventFilter(self, obj, event):
        if obj == self.lineEdit() and event.type() == event.MouseButtonPress:
            self.showPopup()
            return True
        return super().eventFilter(obj, event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.StyleChange and self.lineEdit():
            self.lineEdit().setAlignment(Qt.AlignCenter)
