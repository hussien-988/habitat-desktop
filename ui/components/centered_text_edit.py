# -*- coding: utf-8 -*-
"""QTextEdit with centered placeholder text via QLabel overlay.

Qt5's QTextEdit draws placeholder text internally and does NOT
reliably respect document().setDefaultTextOption() alignment.
This widget uses a QLabel overlay as the placeholder — guaranteed
to center text on all Qt5 versions.
"""

from PyQt5.QtWidgets import QTextEdit, QLabel
from PyQt5.QtCore import Qt


class CenteredTextEdit(QTextEdit):
    """QTextEdit whose placeholder text is always visually centered."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ph_label = QLabel(self.viewport())
        self._ph_label.setAlignment(Qt.AlignCenter)
        self._ph_label.setWordWrap(True)
        self._ph_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._ph_label.setStyleSheet("color: #9CA3AF; background: transparent;")
        self.textChanged.connect(self._toggle_placeholder)

    def setPlaceholderText(self, text: str):
        """Show text as a centered overlay label (skip QTextEdit's built-in placeholder)."""
        self._ph_label.setText(text)
        self._toggle_placeholder()

    def setPlaceholderStyleSheet(self, qss: str):
        """Allow callers to style the placeholder label."""
        self._ph_label.setStyleSheet(qss)

    def _toggle_placeholder(self):
        self._ph_label.setVisible(not self.toPlainText())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        vp = self.viewport()
        self._ph_label.setGeometry(0, 0, vp.width(), vp.height())
