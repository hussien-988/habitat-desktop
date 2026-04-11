# -*- coding: utf-8 -*-
"""
Logout Dialog — ديالوغ تأكيد تسجيل الخروج / إغلاق التطبيق
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QApplication
)
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import (
    QColor, QFont, QPainter, QPainterPath,
    QLinearGradient, QRadialGradient, QPen
)

from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr, get_layout_direction


_BLUE_DARK  = "#122C49"
_BLUE_MID   = "#3890DF"
_BLUE_LIGHT = "#00B2E3"
_BLUE_PALE  = "#E8F4FD"


class _IconBadge(QLabel):
    """
    Custom-painted icon badge.
    Exit mode  : refined power ring (arc + stem, precise weights).
    Logout mode: door-ajar with exit arrow (architectural, professional).
    All drawn via QPainter paths — no external assets, no clipping.
    """

    def __init__(self, is_exit: bool, parent=None):
        super().__init__(parent)
        self._is_exit = is_exit
        sz = ScreenScale.h(56)
        self.setFixedSize(sz, sz)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        r = min(w, h) / 2.0

        # Outer radial glow
        glow = QRadialGradient(cx, cy, r)
        glow.setColorAt(0.55, QColor(56, 144, 223, 50))
        glow.setColorAt(1.0,  QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(0, 0, w, h))

        # Inner gradient circle: dark navy → primary blue
        inset = r * 0.18
        cr = QRectF(inset, inset, w - inset * 2, h - inset * 2)
        grad = QLinearGradient(cr.topLeft(), cr.bottomRight())
        grad.setColorAt(0.0, QColor(_BLUE_DARK))
        grad.setColorAt(1.0, QColor(_BLUE_MID))
        painter.setBrush(grad)
        ring_pen = QPen(QColor(255, 255, 255, 55))
        ring_pen.setWidthF(1.2)
        painter.setPen(ring_pen)
        painter.drawEllipse(cr)

        # Fill again cleanly on top of border
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawEllipse(cr)

        icon_color = QColor(255, 255, 255, 225)
        ir = (r - inset) * 0.52

        if self._is_exit:
            self._draw_power(painter, cx, cy, ir, icon_color)
        else:
            self._draw_logout(painter, cx, cy, ir, icon_color)

        painter.end()

    def _draw_power(self, painter, cx, cy, ir, color):
        """Open arc + vertical stem — the 'standby' symbol drawn precisely."""
        lw = ir * 0.21

        arc_r = ir * 0.72
        arc_rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
        arc_pen = QPen(color)
        arc_pen.setWidthF(lw)
        arc_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen)
        painter.setBrush(Qt.NoBrush)
        # 300° arc, 30° gap at top (12 o'clock), Qt: 0=3 o'clock, CCW positive
        # Gap centred at 90° (12 o'clock): 75° to 105°
        start_angle = int((90 + 35) * 16)
        span_angle  = int(-(360 - 70) * 16)
        painter.drawArc(arc_rect, start_angle, span_angle)

        stem_pen = QPen(color)
        stem_pen.setWidthF(lw)
        stem_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(stem_pen)
        painter.drawLine(
            QPointF(cx, cy - arc_r * 0.98),
            QPointF(cx, cy - arc_r * 0.02)
        )

    def _draw_logout(self, painter, cx, cy, ir, color):
        """Door frame (3 sides) + exit arrow through the opening."""
        lw = ir * 0.19
        door_w = ir * 0.95
        door_h = ir * 1.25
        door_x = cx - door_w * 0.60
        door_y = cy - door_h / 2.0

        # Three-sided door frame (open on right)
        frame_pen = QPen(color)
        frame_pen.setWidthF(lw)
        frame_pen.setCapStyle(Qt.RoundCap)
        frame_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(frame_pen)
        painter.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(door_x + door_w, door_y)
        path.lineTo(door_x, door_y)
        path.lineTo(door_x, door_y + door_h)
        path.lineTo(door_x + door_w, door_y + door_h)
        painter.drawPath(path)

        # Arrow: shaft + chevron head pointing right
        arrow_y = cy
        shaft_x1 = door_x + door_w * 0.30
        shaft_x2 = cx + ir * 0.58
        head_size = ir * 0.30

        arrow_pen = QPen(color)
        arrow_pen.setWidthF(lw)
        arrow_pen.setCapStyle(Qt.RoundCap)
        arrow_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(arrow_pen)
        painter.drawLine(QPointF(shaft_x1, arrow_y), QPointF(shaft_x2, arrow_y))
        head = QPainterPath()
        head.moveTo(shaft_x2 - head_size, arrow_y - head_size)
        head.lineTo(shaft_x2, arrow_y)
        head.lineTo(shaft_x2 - head_size, arrow_y + head_size)
        painter.drawPath(head)


class _GradientCard(QFrame):
    """Card with a blue gradient stripe painted along the top edge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logoutCard")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        stripe = QLinearGradient(0, 0, self.width(), 0)
        stripe.setColorAt(0.00, QColor(18, 44, 73, 0))
        stripe.setColorAt(0.15, QColor(_BLUE_LIGHT))
        stripe.setColorAt(0.50, QColor(_BLUE_MID))
        stripe.setColorAt(0.85, QColor(_BLUE_LIGHT))
        stripe.setColorAt(1.00, QColor(18, 44, 73, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(stripe)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, self.width(), 3), 16, 16)
        painter.setClipPath(clip)
        painter.drawRect(0, 0, self.width(), 3)
        painter.end()


class LogoutDialog(QDialog):
    """Dialog for confirming logout or application exit — fully responsive."""

    def __init__(self, parent=None, is_exit: bool = False):
        super().__init__(parent)
        self._is_exit = is_exit

        self.setModal(True)
        _scr = QApplication.primaryScreen().availableGeometry()

        w = min(420, max(300, int(_scr.width() * 0.30)))
        h = min(270, max(210, int(_scr.height() * 0.28)))
        self.resize(w, h)
        self.setMinimumSize(280, 200)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("QDialog { background-color: transparent; }")

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())

        outer = QVBoxLayout(self)
        m = ScreenScale.h(10)
        outer.setContentsMargins(m, m, m, m)
        outer.setSpacing(0)

        card = _GradientCard()
        card.setStyleSheet("""
            QFrame#logoutCard {
                background-color: #FFFFFF;
                border-radius: 16px;
                border: 1px solid #D4E8F6;
            }
            QFrame#logoutCard QLabel {
                background-color: transparent;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(ScreenScale.h(28))
        shadow.setXOffset(0)
        shadow.setYOffset(ScreenScale.h(8))
        shadow.setColor(QColor(18, 44, 73, 55))
        card.setGraphicsEffect(shadow)

        pad_h = ScreenScale.w(22)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(pad_h, ScreenScale.h(20), pad_h, ScreenScale.h(18))
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignCenter)

        layout.addSpacing(ScreenScale.h(8))

        # Icon
        icon = _IconBadge(self._is_exit)
        icon_row = QHBoxLayout()
        icon_row.addStretch()
        icon_row.addWidget(icon)
        icon_row.addStretch()
        layout.addLayout(icon_row)
        layout.addSpacing(ScreenScale.h(10))

        # Title
        title_text = tr("dialog.logout.exit_app") if self._is_exit else tr("dialog.logout.logout")
        title = QLabel(title_text)
        title.setFont(create_font(size=13, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {_BLUE_DARK};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(ScreenScale.h(4))

        # Subtitle
        subtitle_text = tr("dialog.logout.confirm_exit") if self._is_exit else tr("dialog.logout.confirm_logout")
        subtitle = QLabel(subtitle_text)
        subtitle.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        subtitle.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(ScreenScale.h(14))

        # Thin divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("QFrame { background-color: #E8F2FA; border: none; }")
        layout.addWidget(divider)
        layout.addSpacing(ScreenScale.h(14))

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(ScreenScale.w(10))

        back_btn = self._make_cancel_button(tr("action.back"))
        back_btn.clicked.connect(self.reject)

        action_text = tr("button.close") if self._is_exit else tr("dialog.logout.logout_btn")
        action_btn = self._make_action_button(action_text)
        action_btn.clicked.connect(self.accept)

        btn_row.addWidget(back_btn, 1)
        btn_row.addWidget(action_btn, 1)
        layout.addLayout(btn_row)

        outer.addWidget(card)

    def _make_action_button(self, text: str) -> QPushButton:
        """Primary button — dark-to-light blue gradient (left → right)."""
        btn = QPushButton(text)
        btn.setFixedHeight(ScreenScale.h(36))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {_BLUE_DARK},
                    stop:0.55 {_BLUE_MID},
                    stop:1 {_BLUE_LIGHT});
                color: white;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1A3D60,
                    stop:0.55 #2A7BC9,
                    stop:1 #0099C7);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0D1F33,
                    stop:1 #1F68B3);
            }}
        """)
        return btn

    def _make_cancel_button(self, text: str) -> QPushButton:
        """Cancel button — pale blue tint with blue text."""
        btn = QPushButton(text)
        btn.setFixedHeight(ScreenScale.h(36))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_BLUE_PALE};
                color: {_BLUE_MID};
                border: 1px solid #C2DCF2;
                border-radius: 8px;
            }}
            QPushButton:hover  {{ background-color: #D2E9F8; border-color: {_BLUE_MID}; }}
            QPushButton:pressed{{ background-color: #BBDAF4; }}
        """)
        return btn

    @staticmethod
    def confirm_logout(parent=None) -> bool:
        """Show logout confirmation dialog. Returns True if user confirmed."""
        dialog = LogoutDialog(parent=parent, is_exit=False)
        return dialog.exec_() == QDialog.Accepted

    @staticmethod
    def confirm_exit(parent=None) -> bool:
        """Show exit confirmation dialog. Returns True if user confirmed."""
        dialog = LogoutDialog(parent=parent, is_exit=True)
        return dialog.exec_() == QDialog.Accepted
