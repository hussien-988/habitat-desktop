# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen


class ToggleSwitch(QWidget):
    """Slide toggle switch with optional label."""

    toggled = pyqtSignal(bool)

    TRACK_W = 40
    TRACK_H = 22
    KNOB_MARGIN = 2
    KNOB_D = TRACK_H - KNOB_MARGIN * 2  # 18px

    COLOR_ON = QColor("#3890DF")
    COLOR_OFF = QColor("#D1D5DB")
    COLOR_KNOB = QColor("#FFFFFF")

    def __init__(self, label="", checked=True, parent=None):
        super().__init__(parent)
        self._checked = checked
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._track = _TrackWidget(self)
        self._track.setFixedSize(self.TRACK_W, self.TRACK_H)
        self._track.clicked.connect(self._toggle)
        layout.addWidget(self._track)

        if label:
            lbl = QLabel(label)
            lbl.setStyleSheet(
                "color: #637381; font-size: 10pt; background: transparent;"
            )
            layout.addWidget(lbl)

        self._track.update()

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self._track.update()
            self.toggled.emit(self._checked)

    def _toggle(self):
        self._checked = not self._checked
        self._track.update()
        self.toggled.emit(self._checked)


class _TrackWidget(QWidget):
    """Internal widget that draws the toggle track and knob."""

    clicked = pyqtSignal()

    def __init__(self, toggle: ToggleSwitch):
        super().__init__(toggle)
        self._toggle = toggle
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        ts = ToggleSwitch
        checked = self._toggle.isChecked()

        track_color = ts.COLOR_ON if checked else ts.COLOR_OFF
        p.setPen(Qt.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(QRectF(0, 0, ts.TRACK_W, ts.TRACK_H), ts.TRACK_H / 2, ts.TRACK_H / 2)

        knob_x = ts.TRACK_W - ts.KNOB_D - ts.KNOB_MARGIN if checked else ts.KNOB_MARGIN
        knob_y = ts.KNOB_MARGIN
        p.setBrush(ts.COLOR_KNOB)
        p.setPen(QPen(QColor(0, 0, 0, 20), 0.5))
        p.drawEllipse(QRectF(knob_x, knob_y, ts.KNOB_D, ts.KNOB_D))

        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
