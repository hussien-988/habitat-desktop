# -*- coding: utf-8 -*-
"""
Case Details Page — Modern card-grid layout with glowing borders,
watermark scroll area, and cartographic authority styling.
Supports Draft (resume/cancel) and Completed modes.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QGridLayout,
    QSizePolicy,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtProperty,
    QPropertyAnimation, QEasingCurve, QRectF,
)
from PyQt5.QtGui import (
    QColor, QPainter, QLinearGradient, QPen, QFont,
    QPainterPath, QCursor,
)

from ui.wizards.office_survey.survey_context import SurveyContext
from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from ui.components.icon import Icon
from ui.components.logo import LogoWidget
from ui.components.toast import Toast
from services.translation_manager import tr, get_layout_direction, apply_label_alignment
from services.display_mappings import (
    get_building_type_display, get_building_status_display,
    get_unit_type_display, get_unit_status_display,
    get_claim_type_display, get_claim_status_display,
    get_relationship_to_head_display,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
#  _AccentLine
# ---------------------------------------------------------------------------

class _AccentLine(QWidget):
    """Thin gradient line with animated glow pulse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self._glow_opacity = 0.0
        self._glow_anim = QPropertyAnimation(self, b"glowOpacity")
        self._glow_anim.setDuration(600)
        self._glow_anim.setEasingCurve(QEasingCurve.OutQuad)

    @pyqtProperty(float)
    def glowOpacity(self):
        return self._glow_opacity

    @glowOpacity.setter
    def glowOpacity(self, val: float):
        self._glow_opacity = val
        self.update()

    def pulse(self):
        self._glow_anim.stop()
        self._glow_anim.setStartValue(0.7)
        self._glow_anim.setEndValue(0.0)
        self._glow_anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor(56, 144, 223, 0))
        grad.setColorAt(0.2, QColor(56, 144, 223, 80))
        grad.setColorAt(0.5, QColor(120, 190, 255, 140))
        grad.setColorAt(0.8, QColor(56, 144, 223, 80))
        grad.setColorAt(1.0, QColor(56, 144, 223, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawRect(0, 0, w, h)

        if self._glow_opacity > 0.01:
            glow_alpha = int(self._glow_opacity * 180)
            glow_grad = QLinearGradient(0, 0, w, 0)
            glow_grad.setColorAt(0.0, QColor(56, 144, 223, 0))
            glow_grad.setColorAt(0.3, QColor(91, 168, 240, glow_alpha))
            glow_grad.setColorAt(0.5, QColor(120, 190, 255, min(255, int(glow_alpha * 1.3))))
            glow_grad.setColorAt(0.7, QColor(91, 168, 240, glow_alpha))
            glow_grad.setColorAt(1.0, QColor(56, 144, 223, 0))
            painter.setBrush(glow_grad)
            painter.drawRect(0, 0, w, h)

        painter.end()


# ---------------------------------------------------------------------------
#  _GlowingCard
# ---------------------------------------------------------------------------

class _GlowingCard(QFrame):
    """Card with animated orbiting blue border light."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._glow_phase = 0.0
        self._glow_enabled = True

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 25))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(
            f"_GlowingCard {{ background-color: {Colors.SURFACE}; border: none; border-radius: 12px; }}"
        )

        self._phase_anim = QPropertyAnimation(self, b"glowPhase")
        self._phase_anim.setDuration(3000)
        self._phase_anim.setStartValue(0.0)
        self._phase_anim.setEndValue(1.0)
        self._phase_anim.setLoopCount(-1)
        self._phase_anim.setEasingCurve(QEasingCurve.Linear)
        self._phase_anim.start()

    @pyqtProperty(float)
    def glowPhase(self):
        return self._glow_phase

    @glowPhase.setter
    def glowPhase(self, val):
        self._glow_phase = val
        self.update()

    def set_glow_enabled(self, enabled):
        self._glow_enabled = enabled
        if enabled and self._phase_anim.state() != QPropertyAnimation.Running:
            self._phase_anim.start()
        elif not enabled:
            self._phase_anim.stop()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        r = 12

        bg_path = QPainterPath()
        bg_path.addRoundedRect(QRectF(1, 1, w - 2, h - 2), r, r)
        painter.fillPath(bg_path, QColor(Colors.SURFACE))

        if self._glow_enabled:
            perimeter = 2 * (w + h)
            light_pos = self._glow_phase * perimeter
            border_path = QPainterPath()
            border_path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)

            painter.setPen(QPen(QColor(56, 144, 223, 25), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(border_path)

            for offset in range(-3, 4):
                pos = (light_pos + offset * (perimeter * 0.15 / 6)) % perimeter
                alpha = int(60 * (1 - abs(offset) / 3.5))
                px, py = self._pos_on_rect(pos, w, h)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(56, 144, 223, alpha))
                painter.drawEllipse(int(px) - 3, int(py) - 3, 6, 6)

        painter.end()

    def _pos_on_rect(self, pos, w, h):
        if pos < w:
            return pos, 0
        pos -= w
        if pos < h:
            return w, pos
        pos -= h
        if pos < w:
            return w - pos, h
        pos -= w
        return 0, h - pos


# ---------------------------------------------------------------------------
#  _WatermarkScrollArea
# ---------------------------------------------------------------------------

class _WatermarkScrollArea(QScrollArea):
    """Scroll area with pulsing logo watermark."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logo = LogoWidget(height=120, parent=self)
        self._logo_effect = QGraphicsOpacityEffect(self._logo)
        self._logo_effect.setOpacity(0.04)
        self._logo.setGraphicsEffect(self._logo_effect)
        self._logo.setStyleSheet("background: transparent;")

        self._logo_opacity = 0.04
        self._logo_anim = QPropertyAnimation(self, b"logoOpacity")
        self._logo_anim.setDuration(5000)
        self._logo_anim.setStartValue(0.03)
        self._logo_anim.setKeyValueAt(0.5, 0.06)
        self._logo_anim.setEndValue(0.03)
        self._logo_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._logo_anim.setLoopCount(-1)
        self._logo_anim.start()

    @pyqtProperty(float)
    def logoOpacity(self):
        return self._logo_opacity

    @logoOpacity.setter
    def logoOpacity(self, val):
        self._logo_opacity = val
        self._logo_effect.setOpacity(val)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        lw = self._logo.width() if self._logo.pixmap() else 120
        lh = self._logo.height() if self._logo.pixmap() else 120
        self._logo.move(
            (self.width() - lw) // 2,
            (self.height() - lh) // 2,
        )
        self._logo.raise_()


# ---------------------------------------------------------------------------
#  _CaseDetailsHeader
# ---------------------------------------------------------------------------

class _CaseDetailsHeader(QWidget):
    """Light header with survey identification, badges, and action buttons."""

    back_clicked = pyqtSignal()
    resume_clicked = pyqtSignal()
    cancel_clicked = pyqtSignal()
    resume_obstructed_clicked = pyqtSignal()
    revert_to_draft_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Row 1: Back + reference + buttons
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        self._back_btn = QPushButton()
        self._back_btn.setFixedSize(ScreenScale.w(40), ScreenScale.h(40))
        self._back_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._back_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F4FA
                );
                border: 1.5px solid rgba(56, 144, 223, 0.2);
                border-radius: 12px;
                color: #3890DF; font-size: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #EFF6FF, stop:1 #DBEAFE
                );
                border: 1.5px solid rgba(56, 144, 223, 0.4);
            }
            QPushButton:pressed { background: #DBEAFE; }
        """)
        back_pixmap = Icon.load_pixmap("arrow_back", 16)
        if back_pixmap and not back_pixmap.isNull():
            from PyQt5.QtGui import QIcon
            self._back_btn.setIcon(QIcon(back_pixmap))
        else:
            self._back_btn.setText("\u2190")
        self._back_btn.clicked.connect(self.back_clicked.emit)
        row1.addWidget(self._back_btn)

        self._ref_label = QLabel("")
        self._ref_label.setFont(create_font(size=15, weight=QFont.Bold))
        self._ref_label.setStyleSheet("color: #2A6CB5; background: transparent;")
        self._ref_label.setMinimumWidth(ScreenScale.w(200))
        self._ref_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        ref_glow = QGraphicsDropShadowEffect(self._ref_label)
        ref_glow.setBlurRadius(12)
        ref_glow.setOffset(0, 0)
        ref_glow.setColor(QColor(56, 144, 223, 80))
        self._ref_label.setGraphicsEffect(ref_glow)
        row1.addWidget(self._ref_label)

        row1.addStretch()

        # Resume button (draft only)
        self._resume_btn = QPushButton(tr("page.case_details.resume"))
        self._resume_btn.setFixedSize(ScreenScale.w(160), ScreenScale.h(38))
        self._resume_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._resume_btn.setVisible(False)
        self._resume_btn.setFont(create_font(size=11, weight=QFont.DemiBold))
        self._resume_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3890DF, stop:1 #5BA8F0
                );
                color: white; border: none;
                border-radius: 12px; padding: 0 24px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2A7BC9, stop:1 #4A98E0
                );
            }
            QPushButton:pressed {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1E6CB5, stop:1 #3A88D0
                );
            }
        """)
        self._resume_btn.clicked.connect(self.resume_clicked.emit)
        row1.addWidget(self._resume_btn)

        # Cancel button (draft only)
        self._cancel_btn = QPushButton(tr("page.case_details.cancel_survey"))
        self._cancel_btn.setFixedSize(ScreenScale.w(130), ScreenScale.h(38))
        self._cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._cancel_btn.setVisible(False)
        self._cancel_btn.setFont(create_font(size=11, weight=QFont.DemiBold))
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F4FA
                );
                border: 1.5px solid rgba(56, 144, 223, 0.2);
                border-radius: 10px;
                color: #64748B; padding: 0 14px;
            }
            QPushButton:hover {
                background: #FFF1F2;
                border: 1.5px solid rgba(239, 68, 68, 0.3);
                color: #DC2626;
            }
            QPushButton:pressed { background: #FEE2E2; }
        """)
        self._cancel_btn.clicked.connect(self.cancel_clicked.emit)
        row1.addWidget(self._cancel_btn)

        # Resume Obstructed button (obstructed surveys, admin/data_manager only)
        self._resume_obstructed_btn = QPushButton(tr("page.case_details.resume_obstructed"))
        self._resume_obstructed_btn.setFixedSize(ScreenScale.w(160), ScreenScale.h(38))
        self._resume_obstructed_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._resume_obstructed_btn.setVisible(False)
        self._resume_obstructed_btn.setFont(create_font(size=11, weight=QFont.DemiBold))
        self._resume_obstructed_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #D97706, stop:1 #F59E0B
                );
                color: white; border: none;
                border-radius: 12px; padding: 0 24px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #B45309, stop:1 #D97706
                );
            }
            QPushButton:pressed {
                background: #B45309;
            }
        """)
        self._resume_obstructed_btn.clicked.connect(self.resume_obstructed_clicked.emit)
        row1.addWidget(self._resume_obstructed_btn)

        # Revert to Draft button (finalized surveys, admin/data_manager only)
        self._revert_btn = QPushButton(tr("page.case_details.revert_to_draft"))
        self._revert_btn.setFixedSize(ScreenScale.w(160), ScreenScale.h(38))
        self._revert_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._revert_btn.setVisible(False)
        self._revert_btn.setFont(create_font(size=11, weight=QFont.DemiBold))
        self._revert_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F0F4FA
                );
                border: 1.5px solid rgba(217, 119, 6, 0.35);
                border-radius: 10px;
                color: #D97706; padding: 0 14px;
            }
            QPushButton:hover {
                background: #FFFBEB;
                border: 1.5px solid rgba(217, 119, 6, 0.6);
                color: #B45309;
            }
            QPushButton:pressed { background: #FEF3C7; }
        """)
        self._revert_btn.clicked.connect(self.revert_to_draft_clicked.emit)
        row1.addWidget(self._revert_btn)

        outer.addLayout(row1)
        outer.addSpacing(8)

        # Row 2: Badges
        self._badges_widget = QWidget()
        self._badges_widget.setStyleSheet("background: transparent;")
        self._badges_layout = QHBoxLayout(self._badges_widget)
        self._badges_layout.setContentsMargins(48, 0, 0, 0)
        self._badges_layout.setSpacing(8)
        self._badges_layout.addStretch()
        outer.addWidget(self._badges_widget)
        outer.addSpacing(8)

        # Accent line
        self._accent_line = _AccentLine()
        outer.addWidget(self._accent_line)

    def set_info(self, ref_number, badges, is_draft, can_resume_obstructed=False, can_revert=False):
        self._ref_label.setText(ref_number or tr("page.case_details.title"))
        self._ref_label.setLayoutDirection(Qt.LeftToRight)
        self._ref_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
            if get_layout_direction() == Qt.RightToLeft
            else Qt.AlignLeft | Qt.AlignVCenter
        )

        self._resume_btn.setVisible(is_draft)
        self._cancel_btn.setVisible(is_draft)
        self._resume_obstructed_btn.setVisible(can_resume_obstructed)
        self._revert_btn.setVisible(can_revert)

        # Clear old badges
        while self._badges_layout.count():
            item = self._badges_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for text, bg, fg in badges:
            badge = QLabel(text)
            badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedHeight(ScreenScale.h(22))
            badge.setStyleSheet(
                f"QLabel {{ background: {bg}; color: {fg}; "
                f"border-radius: 11px; padding: 0 10px; border: none; }}"
            )
            self._badges_layout.insertWidget(self._badges_layout.count() - 1, badge)

        self._accent_line.pulse()

    def update_texts(self):
        self._resume_btn.setText(tr("page.case_details.resume"))
        self._cancel_btn.setText(tr("page.case_details.cancel_survey"))
        self._resume_obstructed_btn.setText(tr("page.case_details.resume_obstructed"))
        self._revert_btn.setText(tr("page.case_details.revert_to_draft"))
        self._ref_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
            if get_layout_direction() == Qt.RightToLeft
            else Qt.AlignLeft | Qt.AlignVCenter
        )


# ---------------------------------------------------------------------------
#  CaseDetailsPage
# ---------------------------------------------------------------------------

class CaseDetailsPage(QWidget):
    """Case details page with glowing cards, grid layout, watermark scroll."""

    back_requested = pyqtSignal()
    resume_requested = pyqtSignal(str)  # survey_id
    cancel_requested = pyqtSignal(str, str)  # survey_id, reason
    resume_obstructed_requested = pyqtSignal(str)  # survey_id
    revert_requested = pyqtSignal(str, str)  # survey_id, reason

    def __init__(self, parent=None):
        super().__init__(parent)
        self._context = SurveyContext()
        self._user_role = ""
        self._setup_ui()

    def configure_for_role(self, role: str):
        """Set user role for permission-based button visibility."""
        self._user_role = role

    # -- UI Setup --

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet(StyleManager.page_background())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.content_padding_h(),
            PageDimensions.content_padding_v_top(),
            PageDimensions.content_padding_h(),
            PageDimensions.CONTENT_PADDING_V_BOTTOM,
        )
        main_layout.setSpacing(0)

        # Header
        self._header = _CaseDetailsHeader()
        self._header.back_clicked.connect(self.back_requested.emit)
        self._header.resume_clicked.connect(self._on_resume_clicked)
        self._header.cancel_clicked.connect(self._on_cancel_clicked)
        self._header.resume_obstructed_clicked.connect(self._on_resume_obstructed_clicked)
        self._header.revert_to_draft_clicked.connect(self._on_revert_to_draft_clicked)
        main_layout.addWidget(self._header)
        main_layout.addSpacing(16)

        # Watermark scroll area
        self._scroll = _WatermarkScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {Colors.BACKGROUND}; border: none; }}"
            + StyleManager.scrollbar()
        )

        self._scroll_content = QWidget()
        self._scroll_content.setLayoutDirection(get_layout_direction())
        self._scroll_content.setStyleSheet("background: transparent;")
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 40)
        self._scroll_layout.setSpacing(16)

        # Card 1: Survey Info (full width)
        self._survey_card = _GlowingCard()
        self._survey_card_layout = QVBoxLayout(self._survey_card)
        self._survey_card_layout.setContentsMargins(20, 20, 20, 20)
        self._survey_card_layout.setSpacing(12)
        self._survey_content = QVBoxLayout()
        self._survey_content.setSpacing(12)
        self._survey_card_layout.addLayout(self._survey_content)
        self._scroll_layout.addWidget(self._survey_card)

        # Row: Building | Applicant (side-by-side)
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        self._building_card = _GlowingCard()
        self._building_card_layout = QVBoxLayout(self._building_card)
        self._building_card_layout.setContentsMargins(20, 20, 20, 20)
        self._building_card_layout.setSpacing(12)
        self._building_content = QVBoxLayout()
        self._building_content.setSpacing(12)
        self._building_card_layout.addLayout(self._building_content)
        top_row.addWidget(self._building_card, 1)

        self._applicant_card = _GlowingCard()
        self._applicant_card_layout = QVBoxLayout(self._applicant_card)
        self._applicant_card_layout.setContentsMargins(20, 20, 20, 20)
        self._applicant_card_layout.setSpacing(12)
        self._applicant_content = QVBoxLayout()
        self._applicant_content.setSpacing(12)
        self._applicant_card_layout.addLayout(self._applicant_content)
        top_row.addWidget(self._applicant_card, 1)

        self._scroll_layout.addLayout(top_row)

        # Unit card (full width)
        self._unit_card = _GlowingCard()
        self._unit_card_layout = QVBoxLayout(self._unit_card)
        self._unit_card_layout.setContentsMargins(20, 20, 20, 20)
        self._unit_card_layout.setSpacing(12)
        self._unit_content = QVBoxLayout()
        self._unit_content.setSpacing(12)
        self._unit_card_layout.addLayout(self._unit_content)
        self._scroll_layout.addWidget(self._unit_card)

        # Household card (full width)
        self._household_card = _GlowingCard()
        self._household_card_layout = QVBoxLayout(self._household_card)
        self._household_card_layout.setContentsMargins(20, 20, 20, 20)
        self._household_card_layout.setSpacing(12)
        self._household_content = QVBoxLayout()
        self._household_content.setSpacing(12)
        self._household_card_layout.addLayout(self._household_content)
        self._scroll_layout.addWidget(self._household_card)

        # Persons card (full width)
        self._persons_card = _GlowingCard()
        self._persons_card_layout = QVBoxLayout(self._persons_card)
        self._persons_card_layout.setContentsMargins(20, 20, 20, 20)
        self._persons_card_layout.setSpacing(12)
        self._persons_content = QVBoxLayout()
        self._persons_content.setSpacing(10)
        self._persons_card_layout.addLayout(self._persons_content)
        self._scroll_layout.addWidget(self._persons_card)

        self._scroll_layout.addStretch()

        self._scroll.setWidget(self._scroll_content)
        main_layout.addWidget(self._scroll, 1)

    # -- Section header helper --

    def _add_section_header(self, layout, icon_name, title, subtitle):
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            "QLabel { background-color: #ffffff; border: 1px solid #DBEAFE; border-radius: 7px; }"
        )
        icon_pixmap = Icon.load_pixmap(icon_name, size=14)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setFont(create_font(size=FontManager.WIZARD_STEP_TITLE, weight=FontManager.WEIGHT_SEMIBOLD))
        title_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(create_font(size=FontManager.WIZARD_STEP_SUBTITLE, weight=FontManager.WEIGHT_REGULAR))
        sub_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)

        h_layout.addWidget(icon_label)
        h_layout.addLayout(title_box)
        h_layout.addStretch()
        layout.addWidget(header)

    # -- Field helpers --

    def _create_field_pair(self, label_text, value_text):
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        lbl.setAlignment(Qt.AlignCenter)

        val = QLabel(str(value_text) if value_text else "-")
        val.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        val.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        val.setAlignment(Qt.AlignCenter)
        val.setWordWrap(True)

        layout.addWidget(lbl)
        layout.addWidget(val)
        return container

    def _create_badge(self, text, bg_color, text_color):
        badge = QLabel(str(text))
        badge.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(26))
        badge.setStyleSheet(
            f"QLabel {{ background-color: {bg_color}; color: {text_color}; "
            f"border: none; border-radius: 13px; padding: 2px 14px; }}"
        )
        return badge

    def _create_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {Colors.BORDER_DEFAULT}; border: none;")
        return line

    def _create_section_label(self, text):
        """Create a styled label matching ReviewStep's section labels."""
        lbl = QLabel(text)
        lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        return lbl

    def _create_demographic_card(self, items):
        """Create a demographic data card with label/value rows and separators."""
        frame = QFrame()
        frame.setLayoutDirection(get_layout_direction())
        frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2EAF2;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(18)

        ALIGN_ABS_RIGHT = Qt.AlignRight | Qt.AlignAbsolute

        for i, (text, value) in enumerate(items):
            item_block = QVBoxLayout()
            item_block.setSpacing(4)

            txt_lbl = QLabel(text)
            txt_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
            txt_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            txt_lbl.setAlignment(ALIGN_ABS_RIGHT)

            val_lbl = QLabel(str(value))
            val_lbl.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
            val_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            val_lbl.setAlignment(ALIGN_ABS_RIGHT)

            item_block.addWidget(txt_lbl)
            item_block.addWidget(val_lbl)
            card_layout.addLayout(item_block)

            if i < len(items) - 1:
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setFixedHeight(1)
                separator.setStyleSheet("background-color: #f1f5f9; border: none;")
                card_layout.addWidget(separator)

        return frame

    def _create_empty_state(self, message):
        lbl = QLabel(message)
        lbl.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setMinimumHeight(ScreenScale.h(40))
        return lbl

    def _clear_layout(self, layout):
        if not layout:
            return
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # -- Data --

    def refresh(self, survey_data=None):
        """Called by main_window.navigate_to() with SurveyContext or dict."""
        if survey_data is None:
            return

        try:
            if isinstance(survey_data, SurveyContext):
                self._context = survey_data
            elif isinstance(survey_data, dict):
                self._context = SurveyContext.from_dict(survey_data)
            else:
                logger.warning(f"Unexpected survey_data type: {type(survey_data)}")
                return

            self._populate_all()
            logger.info("Case details page refreshed successfully")
        except Exception as e:
            logger.error(f"Error refreshing case details: {e}", exc_info=True)
            from ui.components.toast import Toast
            from services.error_mapper import map_exception
            Toast.show_toast(self, map_exception(e), Toast.ERROR)

    def _populate_all(self):
        self._populate_header()
        self._populate_survey_card()
        self._populate_building_card()
        self._populate_unit_card()
        self._populate_household_card()
        self._populate_persons_card()
        self._populate_applicant_card()

    # -- Header --

    def _populate_header(self):
        ctx = self._context
        ref = ctx.reference_number or ctx.get_data("survey_id") or ""
        status = getattr(ctx, 'status', '') or ctx.get_data("status") or ""
        status_lower = str(status).lower()
        is_draft = status_lower in ("draft", "1", "")
        is_obstructed = status_lower in ("obstructed", "4")
        is_finalized = not is_draft and not is_obstructed

        can_manage = self._user_role in ("admin", "data_manager")
        can_resume_obstructed = is_obstructed and can_manage
        can_revert = is_finalized and can_manage

        badges = []

        self._header.set_info(ref, badges, is_draft, can_resume_obstructed, can_revert)

    # -- Survey Info Card --

    def _populate_survey_card(self):
        self._clear_layout(self._survey_content)
        ctx = self._context

        self._add_section_header(
            self._survey_content, "data",
            tr("page.case_details.section_survey"),
            tr("page.case_details.section_survey_sub")
        )

        grid = QGridLayout()
        grid.setSpacing(16)

        ref = ctx.reference_number or ctx.get_data("survey_id") or "-"
        created = ""
        if ctx.created_at:
            try:
                created = ctx.created_at.strftime("%Y-%m-%d")
            except Exception:
                created = str(ctx.created_at)

        status = getattr(ctx, 'status', '') or ctx.get_data("status") or ""
        status_lower = str(status).lower()
        is_draft = status_lower in ("draft", "1", "")
        is_obstructed = status_lower in ("obstructed", "4")
        if is_obstructed:
            status_display = tr("page.case_details.status_obstructed")
            s_bg, s_fg, s_br = "#FFFBEB", "#B45309", "#FCD34D"
        elif is_draft:
            status_display = tr("page.case_details.status_draft")
            s_bg, s_fg, s_br = "#FEF3C7", "#92400E", "#FBBF24"
        else:
            status_display = tr("page.case_details.status_completed")
            s_bg, s_fg, s_br = "#D1FAE5", "#065F46", "#6EE7B7"

        case_status = getattr(ctx, 'case_status', 1)
        if case_status == 2:
            case_display = tr("page.case_details.case_closed")
            c_bg, c_fg, c_br = "#FEF2F2", "#DC2626", "#FECACA"
        else:
            case_display = tr("page.case_details.case_open")
            c_bg, c_fg, c_br = "#ECFDF5", "#059669", "#A7F3D0"

        grid.addWidget(self._create_field_pair(tr("page.case_details.ref_number"), ref), 0, 0)
        grid.addWidget(self._create_field_pair(tr("wizard.review.survey_date"), created or "-"), 0, 1)
        grid.addWidget(
            self._build_status_pill(tr("wizard.review.case_status"), status_display, s_bg, s_fg, s_br), 0, 2)
        grid.addWidget(
            self._build_status_pill(tr("page.case_details.case_status"), case_display, c_bg, c_fg, c_br), 0, 3)

        self._survey_content.addLayout(grid)

    def _build_status_pill(self, label_text, value_text, bg, fg, border):
        wrap = QFrame()
        wrap.setStyleSheet(
            "QFrame { background-color: #F8FAFF; border: 1px solid #E8EFF6; border-radius: 10px; }"
        )
        wrap.setLayoutDirection(get_layout_direction())

        v = QVBoxLayout(wrap)
        v.setContentsMargins(ScreenScale.w(10), ScreenScale.h(6), ScreenScale.w(10), ScreenScale.h(6))
        v.setSpacing(ScreenScale.h(4))

        lbl = QLabel(label_text)
        lbl.setFont(create_font(size=FontManager.WIZARD_FIELD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
        apply_label_alignment(lbl)
        v.addWidget(lbl)

        pill = QLabel(value_text)
        pill.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        pill.setAlignment(Qt.AlignCenter)
        pill.setFixedHeight(ScreenScale.h(22))
        pill.setStyleSheet(
            f"QLabel {{ background-color: {bg}; color: {fg}; "
            f"border: 1px solid {border}; border-radius: 11px; padding: 0 10px; }}"
        )

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(pill)
        row.addStretch(1)
        v.addLayout(row)
        return wrap

    # -- Building Card --

    def _populate_building_card(self):
        self._clear_layout(self._building_content)
        ctx = self._context

        self._add_section_header(
            self._building_content, "building-03",
            tr("page.case_details.section_building"),
            tr("page.case_details.section_building_sub")
        )

        if not ctx.building:
            self._building_content.addWidget(
                self._create_empty_state(tr("page.case_details.no_building"))
            )
            return

        b = ctx.building
        grid = QGridLayout()
        grid.setSpacing(16)

        is_ar = get_layout_direction() == Qt.RightToLeft

        grid.addWidget(self._create_field_pair(
            tr("wizard.building.code_label"),
            b.building_id_formatted or b.building_id or "-"
        ), 0, 0)

        gov_name = b.governorate_name_ar if is_ar else b.governorate_name
        grid.addWidget(self._create_field_pair(
            tr("page.case_details.governorate"), gov_name or "-"
        ), 0, 1)

        district_name = b.district_name_ar if is_ar else b.district_name
        grid.addWidget(self._create_field_pair(
            tr("page.case_details.district"), district_name or "-"
        ), 1, 0)

        sub_name = b.subdistrict_name_ar if is_ar else b.subdistrict_name
        grid.addWidget(self._create_field_pair(
            tr("page.case_details.subdistrict"), sub_name or "-"
        ), 1, 1)

        grid.addWidget(self._create_field_pair(
            tr("page.case_details.floors"), str(b.number_of_floors) if b.number_of_floors else "-"
        ), 2, 0)

        grid.addWidget(self._create_field_pair(
            tr("wizard.building.type"),
            get_building_type_display(b.building_type) or "-"
        ), 2, 1)

        grid.addWidget(self._create_field_pair(
            tr("wizard.building.status"),
            get_building_status_display(b.building_status) or "-"
        ), 3, 0)

        grid.addWidget(self._create_field_pair(
            tr("wizard.building.units_count"), str(b.number_of_units) if b.number_of_units else "-"
        ), 3, 1)

        self._building_content.addLayout(grid)

    # -- Unit & Claims Card --

    def _populate_unit_card(self):
        self._clear_layout(self._unit_content)
        ctx = self._context

        self._add_section_header(
            self._unit_content, "elements",
            tr("page.case_details.section_unit"),
            tr("page.case_details.section_unit_sub")
        )

        if not ctx.unit:
            self._unit_content.addWidget(
                self._create_empty_state(tr("page.case_details.no_unit"))
            )
            return

        u = ctx.unit
        grid = QGridLayout()
        grid.setSpacing(16)

        unit_num = str(getattr(u, 'unit_number', None) or getattr(u, 'apartment_number', None) or "-")
        grid.addWidget(self._create_field_pair(
            tr("wizard.unit.unit_number"), unit_num
        ), 0, 0)

        grid.addWidget(self._create_field_pair(
            tr("wizard.unit.type"),
            get_unit_type_display(u.unit_type) or "-"
        ), 0, 1)

        grid.addWidget(self._create_field_pair(
            tr("wizard.unit.floor_number"), str(u.floor_number) if u.floor_number is not None else "-"
        ), 1, 0)

        grid.addWidget(self._create_field_pair(
            tr("wizard.unit.status"),
            get_unit_status_display(u.apartment_status) or "-"
        ), 1, 1)

        self._unit_content.addLayout(grid)

        # Claims section
        claims = ctx.claims or []
        if claims:
            self._unit_content.addWidget(self._create_divider())

            claims_header = QLabel(tr("wizard.review.claim_card_title"))
            claims_header.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
            claims_header.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent; border: none;")
            self._unit_content.addWidget(claims_header)

            for i, claim in enumerate(claims):
                self._add_claim_mini_card(claim)
        elif not claims:
            self._unit_content.addWidget(self._create_divider())
            self._unit_content.addWidget(
                self._create_empty_state(tr("page.case_details.no_claims"))
            )

    def _add_claim_mini_card(self, claim):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(12)

        claim_type = claim.get("claim_type") or claim.get("claimType", "")
        claim_status = claim.get("status") or claim.get("claimStatus", "")

        type_text = get_claim_type_display(claim_type) if claim_type else "-"
        type_label = QLabel(type_text)
        type_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_MEDIUM))
        type_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
        card_layout.addWidget(type_label)

        card_layout.addStretch()

        self._unit_content.addWidget(card)

    # -- Household Card --

    def _populate_household_card(self):
        self._clear_layout(self._household_content)
        ctx = self._context

        self._add_section_header(
            self._household_content, "user-group",
            tr("page.case_details.section_household"),
            tr("page.case_details.section_household_sub")
        )

        if not ctx.households:
            self._household_content.addWidget(
                self._create_empty_state(tr("wizard.household.no_data"))
            )
            return

        # Find the household linked to THIS survey (not all from unit)
        survey_hh_id = ctx.get_data("household_id")
        hh = None
        if survey_hh_id and ctx.households:
            for h in ctx.households:
                if h.get('household_id') == survey_hh_id or h.get('id') == survey_hh_id:
                    hh = h
                    break
        if not hh:
            hh = ctx.households[0]

        total_size = hh.get('size', 0)

        # Get main occupant name from first person
        main_occupant_name = "-"
        if ctx.persons:
            p = ctx.persons[0]
            main_occupant_name = f"{p.get('first_name', '')} {p.get('father_name', '')} {p.get('last_name', '')}".strip()
            if not main_occupant_name:
                main_occupant_name = p.get('full_name', p.get('name', '-'))

        # Summary row: occupant info + total count
        summary_container = QWidget()
        summary_container.setLayoutDirection(get_layout_direction())
        summary_container.setStyleSheet("background: transparent; border: none;")
        summary_layout = QHBoxLayout(summary_container)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(0)

        occupant_block = QVBoxLayout()
        occupant_block.setSpacing(4)
        occupant_title = self._create_section_label(tr("wizard.review.main_occupant_info"))
        occupant_val = QLabel(main_occupant_name)
        occupant_val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        occupant_val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        occupant_block.addWidget(occupant_title)
        occupant_block.addWidget(occupant_val)

        count_block = QVBoxLayout()
        count_block.setSpacing(4)
        count_title = self._create_section_label(tr("wizard.household.family_size"))
        count_title.setAlignment(Qt.AlignCenter)
        count_val = QLabel(str(total_size))
        count_val.setFont(create_font(size=FontManager.WIZARD_CARD_VALUE, weight=FontManager.WEIGHT_REGULAR))
        count_val.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
        count_val.setAlignment(Qt.AlignCenter)
        count_block.addWidget(count_title)
        count_block.addWidget(count_val)

        summary_layout.addLayout(occupant_block)
        summary_layout.addStretch()
        summary_layout.addLayout(count_block)
        summary_layout.addStretch()

        self._household_content.addWidget(summary_container)

        # Demographics breakdown (gender + age side-by-side cards)
        gender_items = [
            (tr("wizard.household.males"), hh.get('male_count', 0)),
            (tr("wizard.household.females"), hh.get('female_count', 0)),
        ]

        age_items = [
            (tr("wizard.household.adults"), hh.get('adult_count', 0)),
            (tr("wizard.household.children"), hh.get('child_count', 0)),
            (tr("wizard.household.elderly"), hh.get('elderly_count', 0)),
            (tr("wizard.household.disabled"), hh.get('disabled_count', 0)),
        ]

        cards_container = QWidget()
        cards_container.setLayoutDirection(get_layout_direction())
        cards_container.setStyleSheet("background: transparent; border: none;")
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(20)

        cards_layout.addWidget(self._create_demographic_card(gender_items))
        cards_layout.addWidget(self._create_demographic_card(age_items))

        self._household_content.addWidget(cards_container)

    # -- Persons Card --

    def _populate_persons_card(self):
        self._clear_layout(self._persons_content)
        ctx = self._context

        self._add_section_header(
            self._persons_content, "user",
            tr("page.case_details.section_persons"),
            tr("page.case_details.section_persons_sub")
        )

        persons = ctx.persons or []
        if not persons:
            self._persons_content.addWidget(
                self._create_empty_state(tr("page.case_details.no_persons"))
            )
            return

        for person in persons:
            self._add_person_mini_card(person)

    def _add_person_mini_card(self, person):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(10)

        # Person icon
        icon_label = QLabel()
        icon_label.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(
            "QLabel { background-color: #EFF6FF; border: 1px solid #DBEAFE; border-radius: 16px; }"
        )
        icon_pixmap = Icon.load_pixmap("user", size=14)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        card_layout.addWidget(icon_label)

        # Name and NID
        info_box = QVBoxLayout()
        info_box.setSpacing(2)

        name = f"{person.get('first_name', '')} {person.get('father_name', '')} {person.get('last_name', '')}".strip()
        if not name:
            name = person.get("full_name") or person.get("fullName") or person.get("name", "-")
        name_label = QLabel(str(name))
        name_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_SEMIBOLD))
        name_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
        info_box.addWidget(name_label)

        nid = person.get("national_id") or person.get("nationalId") or ""
        if nid:
            nid_label = QLabel(str(nid))
            nid_label.setFont(create_font(size=FontManager.SIZE_SMALL, weight=FontManager.WEIGHT_REGULAR))
            nid_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;")
            nid_label.setLayoutDirection(Qt.LeftToRight)
            info_box.addWidget(nid_label)

        card_layout.addLayout(info_box)
        card_layout.addStretch()

        # Role text
        role_key = person.get('person_role') or person.get('relationship_type') or person.get("relation_type") or ""
        if role_key:
            role_text = get_relationship_to_head_display(role_key) or str(role_key)
            role_lbl = QLabel(role_text)
            role_lbl.setFont(create_font(size=FontManager.SIZE_SMALL, weight=FontManager.WEIGHT_REGULAR))
            role_lbl.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent; border: none;")
            card_layout.addWidget(role_lbl)

        self._persons_content.addWidget(card)

    # -- Applicant Card --

    def _populate_applicant_card(self):
        self._clear_layout(self._applicant_content)
        ctx = self._context

        self._add_section_header(
            self._applicant_content, "user-account",
            tr("page.case_details.section_applicant"),
            tr("page.case_details.section_applicant_sub")
        )

        applicant = ctx.applicant
        if not applicant:
            self._applicant_content.addWidget(
                self._create_empty_state(tr("page.case_details.no_applicant"))
            )
            return

        grid = QGridLayout()
        grid.setSpacing(16)

        full_name_display = " ".join(filter(None, [
            applicant.get("first_name_ar"),
            applicant.get("father_name_ar"),
            applicant.get("last_name_ar"),
        ])) or applicant.get("full_name") or applicant.get("fullName") or "-"
        grid.addWidget(self._create_field_pair(
            tr("wizard.applicant.full_name"), full_name_display
        ), 0, 0)

        grid.addWidget(self._create_field_pair(
            tr("wizard.applicant.national_id"),
            applicant.get("national_id") or applicant.get("nationalId") or "-"
        ), 0, 1)

        grid.addWidget(self._create_field_pair(
            tr("wizard.applicant.phone"),
            applicant.get("phone") or "-"
        ), 1, 0)

        grid.addWidget(self._create_field_pair(
            tr("wizard.applicant.email"),
            applicant.get("email") or "-"
        ), 1, 1)

        self._applicant_content.addLayout(grid)

        # In-person badge
        in_person = applicant.get("in_person") or applicant.get("inPerson")
        if in_person is not None:
            badge_row = QHBoxLayout()
            badge_row.setContentsMargins(0, 4, 0, 0)
            if in_person:
                badge = self._create_badge(tr("page.case_details.in_person"), "#D1FAE5", "#065F46")
            else:
                badge = self._create_badge(tr("page.case_details.remote"), "#F1F5F9", "#475569")
            badge_row.addWidget(badge)
            badge_row.addStretch()
            self._applicant_content.addLayout(badge_row)

    # -- Actions --

    def _on_resume_clicked(self):
        survey_id = None
        if self._context:
            survey_id = self._context.get_data("survey_id")
            if not survey_id:
                survey_id = getattr(self._context, 'wizard_id', None)
        if survey_id:
            logger.info(f"Resume requested for survey: {survey_id}")
            self.resume_requested.emit(survey_id)
        else:
            logger.warning("No survey_id in context for resume")

    def _on_cancel_clicked(self):
        survey_id = None
        if self._context:
            survey_id = self._context.get_data("survey_id")
            if not survey_id:
                survey_id = getattr(self._context, 'wizard_id', None)
        if not survey_id:
            logger.warning("No survey_id in context for cancel")
            return

        from ui.components.bottom_sheet import BottomSheet
        sheet = BottomSheet.form(
            parent=self,
            title=tr("page.case_details.cancel_survey"),
            fields=[
                ("reason", tr("page.case_details.cancel_reason_placeholder"), "multiline"),
            ],
            submit_text=tr("page.case_details.confirm_cancel"),
            cancel_text=tr("action.dismiss"),
        )
        sheet.confirmed.connect(lambda: self._handle_cancel_confirmed(sheet, survey_id))

    def _handle_cancel_confirmed(self, sheet, survey_id):
        data = sheet.get_form_data()
        reason = (data.get("reason") or "").strip()
        if not reason:
            Toast.show_toast(self, tr("page.case_details.reason_required"), Toast.WARNING)
            return
        logger.info(f"Cancel requested for survey: {survey_id}")
        self.cancel_requested.emit(survey_id, reason)

    def _on_resume_obstructed_clicked(self):
        survey_id = None
        if self._context:
            survey_id = self._context.get_data("survey_id")
            if not survey_id:
                survey_id = getattr(self._context, 'wizard_id', None)
        if survey_id:
            logger.info(f"Resume obstructed requested for survey: {survey_id}")
            self.resume_obstructed_requested.emit(survey_id)
        else:
            logger.warning("No survey_id in context for resume obstructed")

    def _on_revert_to_draft_clicked(self):
        survey_id = None
        if self._context:
            survey_id = self._context.get_data("survey_id")
            if not survey_id:
                survey_id = getattr(self._context, 'wizard_id', None)
        if not survey_id:
            logger.warning("No survey_id in context for revert to draft")
            return

        from ui.components.bottom_sheet import BottomSheet
        sheet = BottomSheet.form(
            parent=self,
            title=tr("page.case_details.revert_to_draft"),
            fields=[
                ("reason", tr("page.case_details.revert_reason_placeholder"), "multiline"),
            ],
            submit_text=tr("page.case_details.confirm_revert"),
            cancel_text=tr("action.dismiss"),
        )
        sheet.confirmed.connect(lambda: self._handle_revert_confirmed(sheet, survey_id))

    def _handle_revert_confirmed(self, sheet, survey_id):
        data = sheet.get_form_data()
        reason = (data.get("reason") or "").strip()
        if not reason:
            Toast.show_toast(self, tr("page.case_details.reason_required"), Toast.WARNING)
            return
        logger.info(f"Revert to draft requested for survey: {survey_id}")
        self.revert_requested.emit(survey_id, reason)

    # -- Language --

    def update_language(self, is_arabic=True):
        self.setLayoutDirection(get_layout_direction())
        self._scroll_content.setLayoutDirection(get_layout_direction())
        self._header.update_texts()
        self._populate_all()
