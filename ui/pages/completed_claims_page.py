# -*- coding: utf-8 -*-
"""
Claims Page v3 — Dark navy header with constellation, navbar-style tabs,
animated shimmer cards, and cohesive blue palette.
"""

import logging
import math
import random
import time
from typing import List, Dict, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QLineEdit, QPushButton,
    QSizePolicy, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QStackedWidget,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtProperty, QTimer, QRectF, QPoint, QSize,
    QPropertyAnimation, QEasingCurve,
)
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient, QPen,
    QPainterPath, QCursor,
)

from ui.design_system import Colors, PageDimensions, Spacing
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.components.icon import Icon
from ui.components.nav_style_tab import NavStyleTab
from ui.components.stat_pill import StatPill
from ui.components.accent_line import AccentLine
from ui.components.dark_header_zone import DarkHeaderZone
from services.translation_manager import tr, get_layout_direction, get_language
from services.display_mappings import get_source_display, get_claim_type_display
from services.api_worker import ApiWorker
from ui.components.toast import Toast

logger = logging.getLogger(__name__)

CASE_STATUS_OPEN = 1
CASE_STATUS_CLOSED = 2

_STATUS_STYLES = {
    "open":         {"bg": "#FFF7ED", "fg": "#C2410C", "border": "#FDBA74"},
    "draft":        {"bg": "#FFF7ED", "fg": "#C2410C", "border": "#FDBA74"},
    "submitted":    {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
    "under_review": {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
    "screening":    {"bg": "#EFF6FF", "fg": "#1E40AF", "border": "#93C5FD"},
    "awaiting_docs": {"bg": "#FFFBEB", "fg": "#92400E", "border": "#FCD34D"},
    "conflict":     {"bg": "#FEF2F2", "fg": "#991B1B", "border": "#FCA5A5"},
    "approved":     {"bg": "#EBF5FF", "fg": "#0369A1", "border": "#7DD3FC"},
    "closed":       {"bg": "#EBF5FF", "fg": "#0369A1", "border": "#7DD3FC"},
    "rejected":     {"bg": "#FEF2F2", "fg": "#991B1B", "border": "#FCA5A5"},
}


# ---------------------------------------------------------------------------
#  _ClaimCard — Card with blue tint, animated shimmer, press-down, chevron
# ---------------------------------------------------------------------------

class _ClaimCard(QFrame):
    """Claim card with blue-tinted background, animated shimmer sweep,
    prominent hover effects, and directional chevron."""

    clicked = pyqtSignal(str)

    _CARD_BG = "#F7FAFF"
    _CARD_BG_HOVER = "#F0F5FF"

    def _get_lift(self):
        return self._lift_value

    def _set_lift(self, v):
        self._lift_value = v
        lv = int(v)
        self.setContentsMargins(0, max(0, -lv), 0, max(0, lv))
        self.update()

    lift = pyqtProperty(float, _get_lift, _set_lift)

    def __init__(self, claim_data: Dict, parent=None):
        super().__init__(parent)
        self._claim_uuid = claim_data.get("claim_uuid", "")
        self._status = claim_data.get("status", "open")
        self._hovered = False
        self._pressed = False
        self._badge = None
        self._entrance_anim = None
        self._entrance_effect = None
        self._shimmer_offset = random.uniform(0, math.tau)
        self._lift_value = 0.0
        self._lift_anim = None
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(120)
        self.setMouseTracking(True)
        self._build_ui(claim_data)

    def _build_ui(self, d: Dict):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(f"""
            _ClaimCard {{
                background: {self._CARD_BG};
                border-radius: 12px;
                border: 1px solid #E2EAF2;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 22))
        self.setGraphicsEffect(shadow)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 16, 0)
        outer.setSpacing(0)

        # Left status strip
        style = _STATUS_STYLES.get(self._status, _STATUS_STYLES["open"])
        strip = QFrame()
        strip.setFixedWidth(6)
        strip.setStyleSheet(
            f"background-color: {style['fg']}; "
            "border-top-left-radius: 12px; border-bottom-left-radius: 12px;"
        )
        outer.addWidget(strip)

        # Content
        content = QVBoxLayout()
        content.setContentsMargins(16, 12, 0, 12)
        content.setSpacing(6)

        # Row 1: claim number + status badge
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        claim_id_label = QLabel(d.get("claim_id", "N/A"))
        id_font = create_font(size=10, weight=FontManager.WEIGHT_MEDIUM)
        id_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.5)
        claim_id_label.setFont(id_font)
        claim_id_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        row1.addWidget(claim_id_label)
        row1.addStretch()

        status_text = self._get_status_text(self._status)
        badge = QLabel(status_text)
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(24)
        badge.setStyleSheet(
            f"QLabel {{ background-color: {style['bg']}; color: {style['fg']}; "
            f"border: 1px solid {style['border']}; border-radius: 12px; "
            f"padding: 0 12px; }}"
        )
        self._badge = badge
        row1.addWidget(badge)
        content.addLayout(row1)

        # Row 2: claimant name
        name_label = QLabel(d.get("claimant_name", "-"))
        name_label.setFont(create_font(size=13, weight=QFont.Bold))
        name_label.setStyleSheet(
            f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;"
        )
        name_label.setMaximumWidth(600)
        content.addWidget(name_label)

        # Row 3: details
        details_parts = []
        address = d.get("address", "")
        if address:
            details_parts.append(address)
        building_code = d.get("building_code", "")
        if building_code:
            details_parts.append(f"{tr('page.claims.card_building')}: {building_code}")
        claim_type = d.get("claim_type", "")
        if claim_type:
            display = self._get_type_display(claim_type)
            if display:
                details_parts.append(display)
        date_str = d.get("date", "")
        if date_str:
            details_parts.append(date_str)
        source_label = d.get("source_label", "")
        if source_label:
            details_parts.append(source_label)

        details_text = " \u2009\u00b7\u2009 ".join(details_parts)
        details = QLabel(details_text)
        details.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        details.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        content.addWidget(details)

        outer.addLayout(content, 1)

    def _get_status_text(self, status: str) -> str:
        key_map = {
            "open": "page.claims.tab_open",
            "closed": "page.claims.tab_closed",
        }
        return tr(key_map.get(status, "page.claims.tab_open"))

    def _get_type_display(self, claim_type) -> str:
        try:
            return get_claim_type_display(claim_type)
        except Exception:
            return str(claim_type) if claim_type else ""

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time()

        # Animated blue shimmer sweep across the card
        sweep_pos = (math.sin(t * 0.7 + self._shimmer_offset) + 1) / 2
        sweep_x = int(sweep_pos * w)
        shimmer_grad = QLinearGradient(sweep_x - 120, 0, sweep_x + 120, 0)
        shimmer_grad.setColorAt(0, QColor(56, 144, 223, 0))
        shimmer_grad.setColorAt(0.5, QColor(120, 190, 255, 12))
        shimmer_grad.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 11, 11)
        painter.setClipPath(clip)
        painter.fillRect(QRectF(0, 0, w, h), shimmer_grad)

        # Top edge shimmer on hover
        if self._hovered:
            top_grad = QLinearGradient(0, 0, w, 0)
            top_grad.setColorAt(0, QColor(56, 144, 223, 0))
            top_grad.setColorAt(0.15, QColor(56, 144, 223, 35))
            top_grad.setColorAt(0.5, QColor(120, 190, 255, 55))
            top_grad.setColorAt(0.85, QColor(56, 144, 223, 35))
            top_grad.setColorAt(1, QColor(56, 144, 223, 0))
            painter.fillRect(QRectF(0, 0, w, 3.5), top_grad)

        painter.setClipping(False)

        # Chevron arrow
        is_rtl = self.layoutDirection() == Qt.RightToLeft
        chevron_x = 14 if is_rtl else w - 22
        chevron_alpha = 130 if self._hovered else 45
        painter.setPen(QPen(QColor(56, 144, 223, chevron_alpha), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cy = h / 2
        if is_rtl:
            painter.drawLine(int(chevron_x + 6), int(cy - 6), int(chevron_x), int(cy))
            painter.drawLine(int(chevron_x), int(cy), int(chevron_x + 6), int(cy + 6))
        else:
            painter.drawLine(int(chevron_x), int(cy - 6), int(chevron_x + 6), int(cy))
            painter.drawLine(int(chevron_x + 6), int(cy), int(chevron_x), int(cy + 6))

        painter.end()

    def _animate_lift(self, target):
        if self._lift_anim and self._lift_anim.state() == QPropertyAnimation.Running:
            self._lift_anim.stop()
        self._lift_anim = QPropertyAnimation(self, b"lift")
        self._lift_anim.setDuration(180)
        self._lift_anim.setStartValue(self._lift_value)
        self._lift_anim.setEndValue(target)
        self._lift_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._lift_anim.start()

    def enterEvent(self, event):
        self._hovered = True
        self.setStyleSheet(f"""
            _ClaimCard {{
                background: {self._CARD_BG_HOVER};
                border-radius: 12px;
                border: 1px solid rgba(56, 144, 223, 0.3);
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(32)
            eff.setOffset(0, 8)
            eff.setColor(QColor(56, 144, 223, 35))
        if self._badge:
            style = _STATUS_STYLES.get(self._status, _STATUS_STYLES["open"])
            glow = QGraphicsDropShadowEffect(self._badge)
            glow.setBlurRadius(8)
            glow.setOffset(0, 0)
            glow.setColor(QColor(style['fg']))
            self._badge.setGraphicsEffect(glow)
        self._animate_lift(5.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.setStyleSheet(f"""
            _ClaimCard {{
                background: {self._CARD_BG};
                border-radius: 12px;
                border: 1px solid #E2EAF2;
            }}
        """)
        eff = self.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setBlurRadius(20)
            eff.setOffset(0, 4)
            eff.setColor(QColor(0, 0, 0, 22))
        if self._badge:
            self._badge.setGraphicsEffect(None)
        self._animate_lift(0.0)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            eff = self.graphicsEffect()
            if isinstance(eff, QGraphicsDropShadowEffect):
                eff.setBlurRadius(8)
                eff.setOffset(0, 1)
                eff.setColor(QColor(0, 0, 0, 18))
            if self._claim_uuid:
                self.clicked.emit(self._claim_uuid)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pressed:
            self._pressed = False
            if self._hovered:
                eff = self.graphicsEffect()
                if isinstance(eff, QGraphicsDropShadowEffect):
                    eff.setBlurRadius(32)
                    eff.setOffset(0, 8)
                    eff.setColor(QColor(56, 144, 223, 35))
            else:
                eff = self.graphicsEffect()
                if isinstance(eff, QGraphicsDropShadowEffect):
                    eff.setBlurRadius(20)
                    eff.setOffset(0, 4)
                    eff.setColor(QColor(0, 0, 0, 22))
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
#  _EmptyStateAnimated — Dark navy cartographic empty state
# ---------------------------------------------------------------------------

class _EmptyStateAnimated(QWidget):
    """Dark-themed empty state with constellation particles and
    cartographic motifs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._title_text = tr("page.claims.empty_open")
        self._desc_text = tr("page.claims.empty_description")

        self._anim_start = time.time()

        self._shimmer_pos = 0.0
        self._shimmer_anim = QPropertyAnimation(self, b"shimmerPos")
        self._shimmer_anim.setDuration(2500)
        self._shimmer_anim.setStartValue(0.0)
        self._shimmer_anim.setEndValue(1.0)
        self._shimmer_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._shimmer_anim.setLoopCount(-1)
        self._shimmer_anim.start()

        random.seed(77)
        self._particles = []
        for _ in range(12):
            self._particles.append({
                "x": random.uniform(0.05, 0.95),
                "y": random.uniform(0.05, 0.95),
                "phase": random.uniform(0, math.tau),
                "speed": random.uniform(0.3, 0.8),
            })

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    @pyqtProperty(float)
    def shimmerPos(self):
        return self._shimmer_pos

    @shimmerPos.setter
    def shimmerPos(self, val):
        self._shimmer_pos = val
        self.update()

    def set_title(self, text: str):
        self._title_text = text
        self.update()

    def set_description(self, text: str):
        self._desc_text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = time.time() - self._anim_start

        # Dark navy gradient
        bg_grad = QLinearGradient(0, 0, w, h)
        bg_grad.setColorAt(0.0, QColor("#0E2035"))
        bg_grad.setColorAt(0.5, QColor("#132D50"))
        bg_grad.setColorAt(1.0, QColor("#1A3860"))
        painter.fillRect(0, 0, w, h, bg_grad)

        # Grid
        painter.setPen(QPen(QColor(56, 144, 223, 12), 0.5))
        for x in range(0, w, 60):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, 60):
            painter.drawLine(0, y, w, y)

        # Particles
        positions = []
        for p in self._particles:
            px = int((p["x"] + 0.012 * math.sin(t * p["speed"] + p["phase"])) * w)
            py = int((p["y"] + 0.010 * math.cos(t * p["speed"] * 0.7 + p["phase"])) * h)
            px = max(4, min(w - 4, px))
            py = max(4, min(h - 4, py))
            positions.append((px, py))
            alpha = 35 + int(18 * math.sin(t * 1.5 + p["phase"]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(139, 172, 200, alpha))
            painter.drawEllipse(QPoint(px, py), 2, 2)

        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dx = positions[i][0] - positions[j][0]
                dy = positions[i][1] - positions[j][1]
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 150:
                    alpha = int(12 * (1 - dist / 150))
                    painter.setPen(QPen(QColor(139, 172, 200, alpha), 1))
                    painter.drawLine(
                        positions[i][0], positions[i][1],
                        positions[j][0], positions[j][1]
                    )

        cx, cy = w // 2, int(h * 0.40)
        fw, fh = 110, 80

        # Breathing glow
        glow_alpha = 20 + int(12 * math.sin(t * 0.8))
        glow = QRadialGradient(cx, cy, 100)
        glow.setColorAt(0, QColor(56, 144, 223, glow_alpha))
        glow.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(cx - 100, cy - 100, 200, 200)

        # Concentric circles
        for i, radius in enumerate([40, 65, 90]):
            alpha = int(15 + 8 * math.sin(t * 0.4 + i * 1.2))
            painter.setPen(QPen(QColor(56, 144, 223, alpha), 0.8))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

        # Crosshairs
        cross_alpha = int(12 + 6 * math.sin(t * 0.3))
        painter.setPen(QPen(QColor(56, 144, 223, cross_alpha), 0.5))
        painter.drawLine(cx - 100, cy, cx - 55, cy)
        painter.drawLine(cx + 55, cy, cx + 100, cy)
        painter.drawLine(cx, cy - 85, cx, cy - 50)
        painter.drawLine(cx, cy + 50, cx, cy + 85)

        # Folder body
        folder = QPainterPath()
        folder.moveTo(cx - fw // 2, cy - fh // 2 + 16)
        folder.lineTo(cx - fw // 2, cy + fh // 2)
        folder.lineTo(cx + fw // 2, cy + fh // 2)
        folder.lineTo(cx + fw // 2, cy - fh // 2 + 16)
        folder.closeSubpath()
        painter.setPen(QPen(QColor(56, 144, 223, 40), 1.5))
        painter.setBrush(QColor(15, 31, 61, 180))
        painter.drawPath(folder)

        # Folder tab
        tab_path = QPainterPath()
        tab_path.moveTo(cx - fw // 2, cy - fh // 2 + 16)
        tab_path.lineTo(cx - fw // 2, cy - fh // 2 + 4)
        tab_path.lineTo(cx - fw // 2 + 4, cy - fh // 2)
        tab_path.lineTo(cx - 12, cy - fh // 2)
        tab_path.lineTo(cx - 8, cy - fh // 2 + 8)
        tab_path.lineTo(cx + 8, cy - fh // 2 + 8)
        tab_path.lineTo(cx + 12, cy - fh // 2 + 16)
        tab_path.closeSubpath()
        painter.setPen(QPen(QColor(56, 144, 223, 40), 1.5))
        painter.setBrush(QColor(20, 40, 70, 200))
        painter.drawPath(tab_path)

        # Documents
        doc_x, doc_y = cx - 18, cy - fh // 2 + 24
        for i in range(2):
            dx = doc_x + i * 14
            dy = doc_y + i * 5
            painter.setPen(QPen(QColor(56, 144, 223, 30), 1))
            painter.setBrush(QColor(25, 50, 85))
            painter.drawRoundedRect(QRectF(dx, dy, 30, 38), 3, 3)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(56, 144, 223, 25))
            for line_y in range(3):
                lw = 20 if line_y < 2 else 13
                painter.drawRect(QRectF(dx + 5, dy + 9 + line_y * 8, lw, 2))

        # Ground shadow
        painter.setPen(QPen(QColor(56, 144, 223, 20), 1))
        painter.drawLine(cx - fw // 2 + 8, cy + fh // 2 + 3,
                         cx + fw // 2 - 8, cy + fh // 2 + 3)

        # Shimmer sweep
        shimmer_x = int((self._shimmer_pos * 2 - 0.5) * fw + cx - fw // 2)
        sg = QLinearGradient(shimmer_x - 30, 0, shimmer_x + 30, 0)
        sg.setColorAt(0, QColor(56, 144, 223, 0))
        sg.setColorAt(0.5, QColor(91, 168, 240, 50))
        sg.setColorAt(1, QColor(56, 144, 223, 0))
        cp = QPainterPath()
        cp.addRect(QRectF(cx - fw // 2, cy - fh // 2, fw, fh))
        painter.setClipPath(cp)
        painter.setPen(Qt.NoPen)
        painter.setBrush(sg)
        painter.drawRect(shimmer_x - 30, cy - fh // 2, 60, fh)
        painter.setClipping(False)

        # Title
        painter.setFont(create_font(size=FontManager.SIZE_TITLE, weight=QFont.DemiBold))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRectF(0, cy + fh // 2 + 28, w, 30), Qt.AlignCenter, self._title_text)

        # Description
        painter.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        painter.setPen(QColor(139, 172, 200, 200))
        painter.drawText(QRectF(w * 0.2, cy + fh // 2 + 62, w * 0.6, 40),
                         Qt.AlignCenter | Qt.TextWordWrap, self._desc_text)

        painter.end()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start()
        if self._shimmer_anim.state() != QPropertyAnimation.Running:
            self._shimmer_anim.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update()


# ---------------------------------------------------------------------------
#  CompletedClaimsPage — Main page widget
# ---------------------------------------------------------------------------

class CompletedClaimsPage(QWidget):
    """Claims listing page with dark header zone, shimmer cards,
    and comprehensive loading states."""

    claim_selected = pyqtSignal(str)
    add_claim_clicked = pyqtSignal()

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.claims_data: List[Dict] = []
        self._active_tab = "open"
        self._buildings_cache: Dict[str, object] = {}
        self._last_refresh_ms = 0
        self._open_count = 0
        self._closed_count = 0
        self._card_widgets: List[_ClaimCard] = []
        self._loading = False
        self._navigating = False
        self._worker = None
        self._current_page = 1
        self._total_count = 0
        self._page_size = 20

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._on_search_triggered)

        # Shared timer for card shimmer animation
        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.setInterval(80)
        self._shimmer_timer.timeout.connect(self._update_card_shimmer)

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Dark header zone
        self._header = DarkHeaderZone(self)
        self._header.set_title(tr("page.claims.subtitle"))

        self._stat_open = StatPill(tr("page.claims.tab_open"))
        self._header.add_stat_pill(self._stat_open)

        self._stat_closed = StatPill(tr("page.claims.tab_closed"))
        self._header.add_stat_pill(self._stat_closed)

        tab_font = create_font(size=12, weight=QFont.DemiBold)

        self._tab_open = NavStyleTab(tr("page.claims.tab_open"))
        self._tab_open.setFixedSize(130, 38)
        self._tab_open.set_font(tab_font)
        self._tab_open.set_active(True)
        self._tab_open.clicked.connect(lambda: self._on_tab("open"))
        self._header.add_tab(self._tab_open)

        self._tab_closed = NavStyleTab(tr("page.claims.tab_closed"))
        self._tab_closed.setFixedSize(130, 38)
        self._tab_closed.set_font(tab_font)
        self._tab_closed.set_active(False)
        self._tab_closed.clicked.connect(lambda: self._on_tab("closed"))
        self._header.add_tab(self._tab_closed)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("page.claims.search_placeholder"))
        self._search.setFixedSize(280, 34)
        self._search.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        self._search.setStyleSheet("""
            QLineEdit {
                background: rgba(10, 22, 40, 140);
                color: white;
                border: 1px solid rgba(56, 144, 223, 35);
                border-radius: 8px;
                padding: 0 12px 0 34px;
            }
            QLineEdit:focus {
                border: 1.5px solid rgba(56, 144, 223, 140);
                background: rgba(10, 22, 40, 180);
            }
            QLineEdit::placeholder {
                color: rgba(139, 172, 200, 130);
            }
        """)
        search_icon = Icon.load_pixmap("search", 16)
        if search_icon and not search_icon.isNull():
            icon_label = QLabel(self._search)
            icon_label.setPixmap(search_icon)
            icon_label.setFixedSize(16, 16)
            icon_label.move(10, 9)
            icon_label.setStyleSheet("background: transparent; border: none;")
        self._search.returnPressed.connect(self._on_search_triggered)
        self._header.set_search_field(self._search)

        main.addWidget(self._header)

        # Accent line
        self._accent_line = AccentLine()
        main.addWidget(self._accent_line)

        # Light content area
        self._content_wrapper = QWidget()
        self._content_wrapper.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
        content_layout = QVBoxLayout(self._content_wrapper)
        content_layout.setContentsMargins(
            PageDimensions.content_padding_h(), 14,
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        content_layout.setSpacing(0)

        # Card stream area
        self._stack = QStackedWidget()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )

        self._scroll_content = QWidget()
        self._scroll_content.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._scroll_content)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._cards_layout.addStretch()

        self._scroll.setWidget(self._scroll_content)
        self._stack.addWidget(self._scroll)

        self._empty_state = _EmptyStateAnimated()
        self._stack.addWidget(self._empty_state)

        content_layout.addWidget(self._stack, 1)

        self._pagination = self._create_pagination()
        content_layout.addWidget(self._pagination)

        main.addWidget(self._content_wrapper, 1)

        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _create_pagination(self):
        bar = QFrame()
        bar.setFixedHeight(40)
        bar.setStyleSheet("QFrame { background: transparent; border: none; }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 6, 4, 0)
        layout.addStretch()

        _NAV_BTN = """
            QPushButton {
                background: rgba(56, 144, 223, 0.08);
                border: 1px solid rgba(56, 144, 223, 0.2);
                border-radius: 6px; color: #3890DF;
                padding: 0 10px; font-weight: 600;
            }
            QPushButton:hover { background: rgba(56, 144, 223, 0.18); }
            QPushButton:disabled { color: #B0BEC5; background: transparent; border-color: #E0E0E0; }
        """
        self._prev_btn = QPushButton("\u276E")
        self._prev_btn.setFixedSize(32, 28)
        self._prev_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._prev_btn.setStyleSheet(_NAV_BTN)
        self._prev_btn.clicked.connect(self._on_prev_page)
        layout.addWidget(self._prev_btn)

        self._page_info = QLabel("")
        self._page_info.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
        self._page_info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        self._page_info.setAlignment(Qt.AlignCenter)
        self._page_info.setMinimumWidth(80)
        layout.addWidget(self._page_info)

        self._next_btn = QPushButton("\u276F")
        self._next_btn.setFixedSize(32, 28)
        self._next_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._next_btn.setStyleSheet(_NAV_BTN)
        self._next_btn.clicked.connect(self._on_next_page)
        layout.addWidget(self._next_btn)

        return bar

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_claims()

    def _on_next_page(self):
        total_pages = max(1, -(-self._total_count // self._page_size))
        if self._current_page < total_pages:
            self._current_page += 1
            self._load_claims()

    def _update_card_shimmer(self):
        for card in self._card_widgets:
            try:
                card.update()
            except RuntimeError:
                pass

    # -- Tab labels with counts --

    def _update_tab_labels(self):
        open_text = tr("page.claims.tab_open")
        closed_text = tr("page.claims.tab_closed")
        if self._open_count > 0:
            open_text = f"{open_text} ({self._open_count})"
        if self._closed_count > 0:
            closed_text = f"{closed_text} ({self._closed_count})"
        self._tab_open.set_text(open_text)
        self._tab_closed.set_text(closed_text)
        self._stat_open.set_count(self._open_count)
        self._stat_closed.set_count(self._closed_count)

    # -- Events --

    def _on_search_triggered(self):
        self._current_page = 1
        self._load_claims()

    def _on_search_changed(self):
        self._current_page = 1
        self._search_timer.start(500)

    def _on_tab(self, which: str):
        if self._loading or which == self._active_tab:
            return
        self._active_tab = which
        self._current_page = 1
        self._tab_open.set_active(which == "open")
        self._tab_closed.set_active(which == "closed")
        self._accent_line.pulse()
        self._load_claims()

    # -- Data loading --

    def refresh(self, data=None):
        self._navigating = False
        self._last_refresh_ms = int(time.time() * 1000)
        self._load_claims()

    def _load_claims(self):
        if self._loading:
            return
        self._loading = True
        self._spinner.show_loading(tr("page.claims.loading"))

        case_status = CASE_STATUS_OPEN if self._active_tab == "open" else CASE_STATUS_CLOSED
        claim_number = self._search.text().strip()

        self._worker = ApiWorker(
            self._fetch_claims_data, case_status, claim_number
        )
        self._worker.finished.connect(self._on_claims_loaded)
        self._worker.error.connect(self._on_claims_error)
        self._worker.start()

    def _fetch_claims_data(self, case_status, claim_number):
        from services.api_client import get_api_client
        from controllers.building_controller import BuildingController

        api = get_api_client()
        total_count = 0

        if claim_number:
            try:
                result = api.get_claim_by_number(claim_number)
                if result:
                    summaries = [{
                        "claimNumber": result.get("claimNumber", claim_number),
                        "claimId": result.get("id") or result.get("claimId", ""),
                        "primaryClaimantName": result.get("primaryClaimantName", ""),
                        "fullNameArabic": result.get("fullNameArabic", ""),
                        "claimSource": result.get("claimSource", 0),
                        "caseStatus": result.get("caseStatus", 0),
                        "buildingCode": result.get("buildingCode", ""),
                        "claimType": result.get("claimType", ""),
                        "createdAtUtc": result.get("createdAtUtc", ""),
                        "surveyDate": result.get("surveyDate", ""),
                    }]
                    total_count = 1
                else:
                    summaries = []
            except Exception as e:
                logger.warning(f"Search by claim number failed: {e}")
                summaries = []
        else:
            try:
                raw = api._request("GET", "/v2/claims/summaries", params={
                    "caseStatus": case_status,
                    "page": self._current_page,
                    "pageSize": self._page_size,
                })
                if isinstance(raw, dict):
                    summaries = raw.get("items", [])
                    total_count = raw.get("totalCount", len(summaries))
                else:
                    summaries = raw if isinstance(raw, list) else []
                    total_count = len(summaries)
            except Exception as e:
                logger.warning(f"Paginated claims fetch failed: {e}")
                summaries = api.get_claims_summaries(claim_status=case_status)
                total_count = len(summaries)

        open_count = 0
        closed_count = 0
        try:
            raw_open = api._request("GET", "/v2/claims/summaries", params={
                "caseStatus": CASE_STATUS_OPEN, "page": 1, "pageSize": 1,
            })
            open_count = raw_open.get("totalCount", 0) if isinstance(raw_open, dict) else 0
        except Exception:
            pass
        try:
            raw_closed = api._request("GET", "/v2/claims/summaries", params={
                "caseStatus": CASE_STATUS_CLOSED, "page": 1, "pageSize": 1,
            })
            closed_count = raw_closed.get("totalCount", 0) if isinstance(raw_closed, dict) else 0
        except Exception:
            pass

        bc = BuildingController(self.db)
        building_codes = {s.get("buildingCode", "") for s in summaries if s.get("buildingCode")}
        new_buildings = {}
        for code in building_codes:
            if not code or code in self._buildings_cache:
                continue
            try:
                result = api.search_buildings(building_id=code, page_size=1)
                buildings = result.get("buildings", [])
                if buildings:
                    new_buildings[code] = bc._api_dto_to_building(buildings[0])
            except Exception as e:
                logger.debug(f"Building lookup failed for {code}: {e}")

        return {
            "summaries": summaries,
            "new_buildings": new_buildings,
            "case_status": case_status,
            "open_count": open_count,
            "closed_count": closed_count,
            "total_count": total_count,
        }

    def _on_claims_loaded(self, result):
        try:
            self._buildings_cache.update(result.get("new_buildings", {}))
            self._open_count = result.get("open_count", 0)
            self._closed_count = result.get("closed_count", 0)
            self._total_count = result.get("total_count", 0)

            summaries = result.get("summaries", [])
            self.claims_data = [self._map_summary(s) for s in summaries]

            logger.info(f"Loaded {len(self.claims_data)} claims (status={result.get('case_status')})")
            self._populate_cards()
            self._update_tab_labels()
            self._update_pagination()
        except Exception as e:
            logger.error(f"Error processing claims: {e}")
            self.claims_data = []
            self._populate_cards()
        finally:
            self._loading = False
            self._spinner.hide_loading()

    def _update_pagination(self):
        total = self._total_count
        ps = self._page_size
        total_pages = max(1, -(-total // ps))
        page = self._current_page
        start = (page - 1) * ps + 1
        end = min(page * ps, total)
        if total > 0:
            self._page_info.setText(f"{start}-{end}  /  {total}")
        else:
            self._page_info.setText("")
        self._prev_btn.setEnabled(page > 1)
        self._next_btn.setEnabled(page < total_pages)

    def _on_claims_error(self, error_msg):
        self._loading = False
        self._spinner.hide_loading()
        Toast.show_toast(self, tr("page.claims.load_error"), Toast.ERROR)
        logger.warning(f"Error loading claims: {error_msg}")
        self.claims_data = []
        self._populate_cards()

    def _map_summary(self, s: Dict) -> Dict:
        try:
            source = s.get("claimSource", 0)
            claimant = (
                s.get("primaryClaimantName")
                or s.get("fullNameArabic")
                or tr("page.claims.unknown_claimant")
            )
            date_str = s.get("createdAtUtc") or s.get("surveyDate") or ""
            building_code = s.get("buildingCode", "")
            status_int = s.get("caseStatus", 0)
            status_str = "open" if status_int == CASE_STATUS_OPEN else "closed"
            claim_type = s.get("claimType", "")

            address = ""
            if building_code and building_code in self._buildings_cache:
                b = self._buildings_cache[building_code]
                parts = []
                for attr in ("governorate_name", "district_name", "subdistrict_name", "neighbourhood_name"):
                    val = getattr(b, attr, None) or ""
                    if val:
                        parts.append(val)
                if parts:
                    address = " > ".join(parts)

            return {
                "claim_id": s.get("claimNumber", "") or s.get("claimId", "N/A"),
                "claim_uuid": s.get("claimId", "") or s.get("id", ""),
                "claimant_name": claimant,
                "date": date_str[:10] if date_str and not date_str.startswith("0001") else "",
                "status": status_str,
                "claim_type": claim_type,
                "source": source,
                "source_label": get_source_display(source),
                "building_code": building_code,
                "address": address,
            }
        except Exception as e:
            logger.warning(f"Error mapping claim summary: {e}")
            return {
                "claim_id": "N/A", "claim_uuid": "",
                "claimant_name": "-", "date": "", "status": "open",
                "claim_type": "", "source": 0, "source_label": "",
                "building_code": "", "address": "",
            }

    # -- Card population --

    def _populate_cards(self):
        try:
            self._clear_cards()

            if not self.claims_data:
                self._stack.setCurrentIndex(1)
                self._update_empty_text()
                self._update_pagination()
                return

            self._stack.setCurrentIndex(0)

            for claim in self.claims_data:
                card = _ClaimCard(claim)
                card.clicked.connect(self._on_card_clicked)
                self._cards_layout.insertWidget(
                    self._cards_layout.count() - 1, card
                )
                self._card_widgets.append(card)

            self._update_pagination()

            self._animate_card_entrance()

            # Start shimmer timer for card animation
            if not self._shimmer_timer.isActive():
                self._shimmer_timer.start()
        except Exception as e:
            logger.error(f"Error populating cards: {e}")
            self._stack.setCurrentIndex(1)
            self._update_empty_text()

    def _animate_card_entrance(self):
        count = len(self._card_widgets)
        if count > 20 or count == 0:
            return

        for i, card in enumerate(self._card_widgets):
            opacity_eff = QGraphicsOpacityEffect(card)
            opacity_eff.setOpacity(0.0)
            card.setGraphicsEffect(opacity_eff)

            anim = QPropertyAnimation(opacity_eff, b"opacity")
            anim.setDuration(300)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def _restore_shadow(c=card):
                try:
                    s = QGraphicsDropShadowEffect(c)
                    s.setBlurRadius(20)
                    s.setOffset(0, 4)
                    s.setColor(QColor(0, 0, 0, 22))
                    c.setGraphicsEffect(s)
                except RuntimeError:
                    pass

            anim.finished.connect(_restore_shadow)
            QTimer.singleShot(i * 40, anim.start)

            card._entrance_anim = anim
            card._entrance_effect = opacity_eff

    def _clear_cards(self):
        self._shimmer_timer.stop()
        for card in self._card_widgets:
            if hasattr(card, '_entrance_anim') and card._entrance_anim:
                try:
                    card._entrance_anim.stop()
                except RuntimeError:
                    pass
            try:
                card.clicked.disconnect()
            except Exception:
                pass
            card.setParent(None)
            card.deleteLater()
        self._card_widgets.clear()

    def _update_empty_text(self):
        msg = tr("page.claims.empty_open") if self._active_tab == "open" else tr("page.claims.empty_closed")
        self._empty_state.set_title(msg)
        self._empty_state.set_description(tr("page.claims.empty_description"))

    # -- Interaction --

    def _on_card_clicked(self, claim_uuid: str):
        if self._navigating or not claim_uuid:
            return
        self._navigating = True
        self._spinner.show_loading(tr("page.claims.loading"))
        self.claim_selected.emit(claim_uuid)

    # -- Public interface --

    def load_claims(self, claims_data):
        self.claims_data = claims_data
        self._populate_cards()

    def search_claims(self, query: str, mode: str = "name"):
        pass

    def update_language(self, is_arabic: bool):
        direction = get_layout_direction()
        self.setLayoutDirection(direction)

        self._header.get_title_label().setText(tr("page.claims.subtitle"))
        self._search.setPlaceholderText(tr("page.claims.search_placeholder"))
        self._stat_open.set_label(tr("page.claims.tab_open"))
        self._stat_closed.set_label(tr("page.claims.tab_closed"))

        self._update_tab_labels()

        self._scroll.setLayoutDirection(direction)
        self._scroll_content.setLayoutDirection(direction)

        if self.claims_data:
            self._populate_cards()
        else:
            self._update_empty_text()

    def set_tab_title(self, title: str):
        pass

    def configure_for_role(self, role: str):
        pass
