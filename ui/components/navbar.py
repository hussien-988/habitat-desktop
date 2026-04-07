# -*- coding: utf-8 -*-
"""
Navbar Component - UN-HABITAT TRRCMS
المكون المشترك للشريط العلوي مع التبويبات
"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QWidget, QPushButton,
    QVBoxLayout, QSpacerItem, QSizePolicy, QLineEdit, QGraphicsOpacityEffect
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, pyqtProperty, QPoint, QSize,
    QRect, QRectF, QPropertyAnimation, QEasingCurve, QTimer
)
from PyQt5.QtGui import (
    QFont, QCursor, QIcon, QPainter, QPainterPath, QColor, QPixmap,
    QRadialGradient, QLinearGradient, QPen
)

from ..design_system import Colors, NavbarDimensions, Typography, Spacing, ScreenScale
from ..font_utils import create_font, FontManager
from ..style_manager import StyleManager
from .logo import LogoWidget
from .id_badge import IDBadgeWidget
from .curved_tab import CurvedTab
from services.translation_manager import tr, get_language


# -- Draggable Top Bar Frame --

class DraggableFrame(QFrame):
    """Draggable frame for window movement with geometric grid texture."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Subtle geometric grid
        grid_spacing = 60
        painter.setPen(QPen(QColor(56, 144, 223, 6), 1))
        x = grid_spacing
        while x < w:
            painter.drawLine(x, 0, x, h)
            x += grid_spacing
        y = grid_spacing
        while y < h:
            painter.drawLine(0, y, w, y)
            y += grid_spacing

        # Radial glow at center-bottom
        glow = QRadialGradient(w / 2, h + 8, w * 0.35)
        glow.setColorAt(0, QColor(56, 144, 223, 22))
        glow.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawRect(0, int(h * 0.4), w, int(h * 0.6))

        # Corner bracket accents
        bracket_color = QColor(56, 144, 223, 15)
        painter.setPen(QPen(bracket_color, 1))
        painter.drawLine(10, 10, 10, 28)
        painter.drawLine(10, 10, 28, 10)
        painter.drawLine(w - 10, h - 10, w - 10, h - 28)
        painter.drawLine(w - 10, h - 10, w - 28, h - 10)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.window().frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and (event.buttons() & Qt.LeftButton):
            if not self.window().isMaximized():
                self.window().move(event.globalPos() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        navbar = self.parent()
        if hasattr(navbar, '_toggle_maximize'):
            navbar._toggle_maximize()
        event.accept()


# -- Tabs Bar with Flowing Line --

class _TabsBarFrame(QFrame):
    """Tabs bar: background + flowing blue line that wraps active tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._indicator_rect = QRect(0, 0, 0, 0)

        # Indicator slide animation
        self._anim = QPropertyAnimation(self, b"indicatorRect")
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        # Glow pulse on tab switch
        self._glow_opacity = 0.0
        self._glow_anim = QPropertyAnimation(self, b"glowOpacity")
        self._glow_anim.setDuration(600)
        self._glow_anim.setEasingCurve(QEasingCurve.OutQuad)

    @pyqtProperty(QRect)
    def indicatorRect(self):
        return self._indicator_rect

    @indicatorRect.setter
    def indicatorRect(self, rect):
        self._indicator_rect = rect
        self.update()

    @pyqtProperty(float)
    def glowOpacity(self):
        return self._glow_opacity

    @glowOpacity.setter
    def glowOpacity(self, val):
        self._glow_opacity = val
        self.update()

    def animate_to(self, target_rect: QRect):
        self._anim.stop()
        self._anim.setStartValue(self._indicator_rect)
        self._anim.setEndValue(target_rect)
        self._anim.start()

        self._glow_anim.stop()
        self._glow_anim.setStartValue(0.7)
        self._glow_anim.setEndValue(0.0)
        self._glow_anim.start()

    def set_indicator_immediate(self, rect: QRect):
        self._indicator_rect = rect
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Background gradient
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor(13, 31, 59))
        bg.setColorAt(1, QColor(8, 20, 38))
        painter.fillRect(0, 0, w, h, bg)

        # Ambient radial glow
        glow = QRadialGradient(w / 2, h / 2, w * 0.30)
        glow.setColorAt(0, QColor(56, 144, 223, 14))
        glow.setColorAt(0.5, QColor(56, 144, 223, 5))
        glow.setColorAt(1, QColor(56, 144, 223, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawRect(0, 0, w, h)

        # Flowing blue line that wraps around active tab
        r = self._indicator_rect
        if r.width() > 0 and r.height() > 0:
            self._paint_flowing_line(painter, r, w, h)

        painter.end()

    def _paint_flowing_line(self, painter, r, w, h):
        """Paint blue line spanning full width that U-frames the active tab."""
        line_y = 2.0
        cr = 10.0
        pen_w = 1.5

        tx = float(r.x())
        ty = float(r.y())
        tw = float(r.width())
        th = float(r.height())
        tb = ty + th

        # Clamp curve radius
        cr = min(cr, tw / 4, th / 3)

        # Build the continuous path
        path = QPainterPath()
        path.moveTo(0, line_y)
        path.lineTo(max(0, tx - cr), line_y)
        # Curve down on left side
        path.quadTo(tx, line_y, tx, line_y + cr)
        # Down left side of tab
        path.lineTo(tx, tb - cr)
        # Curve along bottom-left
        path.quadTo(tx, tb, tx + cr, tb)
        # Along the bottom
        path.lineTo(tx + tw - cr, tb)
        # Curve up bottom-right
        path.quadTo(tx + tw, tb, tx + tw, tb - cr)
        # Up right side
        path.lineTo(tx + tw, line_y + cr)
        # Curve back to horizontal
        path.quadTo(tx + tw, line_y, min(float(w), tx + tw + cr), line_y)
        # Continue to right edge
        path.lineTo(float(w), line_y)

        # Gradient pen: fades at edges, bright at center
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0, QColor(56, 144, 223, 0))
        grad.setColorAt(0.05, QColor(56, 144, 223, 100))
        grad.setColorAt(0.25, QColor(56, 144, 223, 180))
        grad.setColorAt(0.5, QColor(120, 190, 255, 240))
        grad.setColorAt(0.75, QColor(56, 144, 223, 180))
        grad.setColorAt(0.95, QColor(56, 144, 223, 100))
        grad.setColorAt(1.0, QColor(56, 144, 223, 0))

        painter.setPen(QPen(grad, pen_w))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # Glow layer (wider, softer)
        glow_alpha = max(15, int(30 * (1.0 + self._glow_opacity)))
        painter.setPen(QPen(QColor(56, 144, 223, glow_alpha), pen_w + 4))
        painter.drawPath(path)

        # Extra glow pulse during tab switch
        if self._glow_opacity > 0.01:
            pulse_alpha = int(self._glow_opacity * 40)
            painter.setPen(QPen(QColor(91, 168, 240, pulse_alpha), pen_w + 8))
            painter.drawPath(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)


# -- Pulsing Logo Wrapper --

class _PulsingLogo(QWidget):
    """Wrapper that applies a gentle opacity pulse to the LogoWidget."""

    def __init__(self, height=28, parent=None):
        super().__init__(parent)
        self._logo = LogoWidget(height=height, parent=self)
        self._opacity = 1.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._logo)

        # Gentle opacity pulse (barely perceptible breathing)
        self._pulse_anim = QPropertyAnimation(self, b"logoOpacity")
        self._pulse_anim.setDuration(5000)
        self._pulse_anim.setStartValue(0.92)
        self._pulse_anim.setKeyValueAt(0.5, 1.0)
        self._pulse_anim.setEndValue(0.92)
        self._pulse_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._pulse_anim.setLoopCount(-1)

        self._effect = QGraphicsOpacityEffect(self._logo)
        self._effect.setOpacity(1.0)
        self._logo.setGraphicsEffect(self._effect)

    @pyqtProperty(float)
    def logoOpacity(self):
        return self._opacity

    @logoOpacity.setter
    def logoOpacity(self, val):
        self._opacity = val
        self._effect.setOpacity(val)

    def start_pulse(self):
        if not self._pulse_anim.state() == QPropertyAnimation.Running:
            self._pulse_anim.start()

    def stop_pulse(self):
        self._pulse_anim.stop()
        self._effect.setOpacity(1.0)

    def logo(self):
        return self._logo


# -- Main Navbar --

class Navbar(QFrame):
    """
    Main Navbar Component with Tabs
    المكون الرئيسي للشريط العلوي مع التبويبات
    """

    tab_changed = pyqtSignal(int)
    search_requested = pyqtSignal(str)
    filter_applied = pyqtSignal(dict)
    logout_requested = pyqtSignal()
    language_change_requested = pyqtSignal()
    sync_requested = pyqtSignal()
    password_change_requested = pyqtSignal()
    import_requested = pyqtSignal()

    def __init__(self, user_id=None, parent=None):
        super().__init__(parent)

        self.user_id = user_id or "12345"
        self.setObjectName("navbar")
        self.current_tab_index = 0
        self.tab_buttons = []
        self.search_mode = "name"

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar (80px)
        self._top_bar = self._create_top_bar()
        main_layout.addWidget(self._top_bar)

        # Tabs bar (68px) -- flowing line replaces accent separator
        tabs_bar = self._create_tabs_bar()
        main_layout.addWidget(tabs_bar)

        # Bottom glow border
        bottom_glow = QFrame()
        bottom_glow.setObjectName("navbar_bottom_glow")
        bottom_glow.setFixedHeight(1)
        bottom_glow.setStyleSheet("""
            QFrame#navbar_bottom_glow {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(56, 144, 223, 0),
                    stop:0.2 rgba(56, 144, 223, 50),
                    stop:0.5 rgba(56, 144, 223, 100),
                    stop:0.8 rgba(56, 144, 223, 50),
                    stop:1.0 rgba(56, 144, 223, 0)
                );
                max-height: 1px;
            }
        """)
        main_layout.addWidget(bottom_glow)

        self.setFixedHeight(NavbarDimensions.container_height())

    # -- Top Bar --

    def _create_top_bar(self):
        top_bar = DraggableFrame()
        top_bar.setObjectName("navbar_top")
        top_bar.setAttribute(Qt.WA_StyledBackground, True)
        top_bar.setFixedHeight(NavbarDimensions.top_bar_height())
        top_bar.setLayoutDirection(Qt.RightToLeft)

        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(
            Spacing.NAVBAR_HORIZONTAL_PADDING, 16,
            Spacing.NAVBAR_HORIZONTAL_PADDING, 14
        )
        layout.setSpacing(16)

        # Window controls (leftmost visually in RTL)
        win_controls = self._create_window_controls()
        layout.addWidget(win_controls)

        # Spacer
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Logo (centered via spacers on both sides)
        self._pulsing_logo = _PulsingLogo(height=28)
        self.logo = self._pulsing_logo.logo()
        layout.addWidget(self._pulsing_logo)

        # Spacer
        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # ID Badge (rightmost visually)
        self.id_badge = IDBadgeWidget(user_id=self.user_id)
        layout.addWidget(self.id_badge)

        # Settings pill (next to ID badge)
        self._settings_pill = self._create_settings_pill()
        layout.addWidget(self._settings_pill)

        return top_bar

    def _create_window_controls(self):
        box = QWidget()
        box.setObjectName("window_controls")
        box.setLayoutDirection(Qt.LeftToRight)

        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        btn_min = QPushButton("\u2013")
        btn_max = QPushButton("\u25A1")
        btn_close = QPushButton("\u2715")

        btn_max.setStyleSheet("QPushButton { font-size: 28px; margin-bottom: 4px; }")

        btn_min.setObjectName("win_btn")
        btn_max.setObjectName("win_btn")
        btn_close.setObjectName("win_close")

        for b in (btn_min, btn_max, btn_close):
            b.setFixedSize(ScreenScale.w(46), ScreenScale.h(32))
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(QCursor(Qt.PointingHandCursor))

        btn_min.clicked.connect(lambda: self.window().showMinimized())
        btn_max.clicked.connect(lambda: self._toggle_maximize())
        btn_close.clicked.connect(lambda: self.window().close())

        lay.addWidget(btn_min)
        lay.addWidget(btn_max)
        lay.addWidget(btn_close)

        return box

    def _toggle_maximize(self):
        win = self.window()
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()

    # -- Tabs Bar --

    def _create_tabs_bar(self):
        self._tabs_bar_frame = _TabsBarFrame()
        self._tabs_bar_frame.setObjectName("tabs_bar")
        self._tabs_bar_frame.setFixedHeight(NavbarDimensions.tabs_bar_height())

        layout = QHBoxLayout(self._tabs_bar_frame)
        layout.setContentsMargins(
            Spacing.NAVBAR_HORIZONTAL_PADDING, 8,
            Spacing.NAVBAR_HORIZONTAL_PADDING, 10
        )
        layout.setSpacing(0)

        # Tabs wrapper (75%)
        tabs_wrapper = QWidget()
        tabs_wrapper.setObjectName("tabs_wrapper")
        tabs_wrapper.setStyleSheet("QWidget#tabs_wrapper { background: transparent; }")
        tabs_wrapper_layout = QHBoxLayout(tabs_wrapper)
        tabs_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        tabs_wrapper_layout.setSpacing(4)

        self._tab_keys = [
            "navbar.tab.completed_claims",
            "navbar.tab.cases",
            "navbar.tab.case_management",
            "navbar.tab.import",
            "navbar.tab.duplicates",
            "navbar.tab.field_assignment",
            "navbar.tab.buildings",
        ]
        tab_titles = [tr(key) for key in self._tab_keys]

        self.tab_buttons = []
        for index, title in enumerate(tab_titles):
            tab_btn = self._create_tab_button(title, index)
            self.tab_buttons.append(tab_btn)
            tabs_wrapper_layout.addWidget(tab_btn, stretch=1)

        layout.addWidget(tabs_wrapper, 1)

        self._set_active_tab(0)
        QTimer.singleShot(0, self._init_tab_indicator)

        return self._tabs_bar_frame

    def _create_tab_button(self, title: str, index: int) -> CurvedTab:
        tab = CurvedTab(title, theme="dark")
        tab.setFixedHeight(NavbarDimensions.tab_height())
        tab.setMinimumWidth(ScreenScale.w(100))
        tab.setCursor(QCursor(Qt.PointingHandCursor))
        tab.set_font(create_font(
            size=NavbarDimensions.TAB_FONT_SIZE,
            weight=NavbarDimensions.TAB_FONT_WEIGHT,
            letter_spacing=0
        ))
        tab.clicked.connect(lambda: self._on_tab_clicked(index))
        return tab

    # -- Settings Pill (collapsible, login page style) --

    def _create_settings_pill(self):
        """Collapsible frosted glass pill: trigger label + expandable content."""
        self._pill_expanded = False
        self._pill_collapsed_w = 120
        self._pill_expanded_w = 530

        pill = QFrame()
        pill.setObjectName("navbar_pill")
        pill.setFixedHeight(ScreenScale.h(36))
        pill.setFixedWidth(self._pill_collapsed_w)
        pill.setStyleSheet("""
            QFrame#navbar_pill {
                background: rgba(10, 22, 40, 180);
                border: 1px solid rgba(56, 144, 223, 40);
                border-radius: 18px;
            }
        """)

        _BTN_STYLE = """
            QPushButton {
                color: rgba(139, 172, 200, 200);
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px 6px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.10);
                color: white;
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.16);
            }
        """
        _btn_font = create_font(size=9, weight=QFont.DemiBold)

        pill_layout = QHBoxLayout(pill)
        pill_layout.setContentsMargins(14, 0, 14, 0)
        pill_layout.setSpacing(0)

        # Trigger label (always visible)
        self._pill_trigger = QPushButton("\u25C8  " + tr("navbar.pill.settings"))
        self._pill_trigger.setObjectName("pill_trigger")
        self._pill_trigger.setStyleSheet("""
            QPushButton#pill_trigger {
                color: rgba(139, 172, 200, 200);
                background: transparent;
                border: none;
                padding: 0;
            }
            QPushButton#pill_trigger:hover {
                color: white;
            }
        """)
        self._pill_trigger.setFont(create_font(size=10, weight=QFont.DemiBold))
        self._pill_trigger.setCursor(QCursor(Qt.PointingHandCursor))
        self._pill_trigger.setFocusPolicy(Qt.NoFocus)
        self._pill_trigger.clicked.connect(self._toggle_pill)
        pill_layout.addWidget(self._pill_trigger)

        # Expandable content (hidden initially)
        self._pill_content = QWidget()
        self._pill_content.setStyleSheet("background: transparent;")
        self._pill_content.setVisible(False)
        content_lay = QHBoxLayout(self._pill_content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(0)

        # Separator
        content_lay.addWidget(self._create_pill_separator())
        content_lay.addSpacing(6)

        # Sync button
        self._pill_sync_btn = QPushButton()
        self._pill_sync_btn.setStyleSheet(_BTN_STYLE)
        self._pill_sync_btn.setFixedHeight(ScreenScale.h(28))
        self._pill_sync_btn.setFont(_btn_font)
        self._pill_sync_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._pill_sync_btn.setFocusPolicy(Qt.NoFocus)
        self._pill_sync_btn.clicked.connect(self._on_sync_requested)
        self._load_pill_icon(self._pill_sync_btn, "fluent", tr("navbar.menu.sync_data"))
        content_lay.addWidget(self._pill_sync_btn)

        content_lay.addSpacing(4)
        content_lay.addWidget(self._create_pill_separator())
        content_lay.addSpacing(4)

        # Password change button
        self._pill_pwd_btn = QPushButton()
        self._pill_pwd_btn.setStyleSheet(_BTN_STYLE)
        self._pill_pwd_btn.setFixedHeight(ScreenScale.h(28))
        self._pill_pwd_btn.setFont(_btn_font)
        self._pill_pwd_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._pill_pwd_btn.setFocusPolicy(Qt.NoFocus)
        self._pill_pwd_btn.clicked.connect(self._on_password_change_requested)
        self._load_pill_icon(self._pill_pwd_btn, "safe", tr("navbar.menu.change_password"))
        content_lay.addWidget(self._pill_pwd_btn)

        content_lay.addSpacing(4)
        content_lay.addWidget(self._create_pill_separator())
        content_lay.addSpacing(4)

        # Language toggle button
        self._pill_lang_btn = QPushButton()
        self._pill_lang_btn.setStyleSheet(_BTN_STYLE)
        self._pill_lang_btn.setFixedHeight(ScreenScale.h(28))
        self._pill_lang_btn.setFont(_btn_font)
        self._pill_lang_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._pill_lang_btn.setFocusPolicy(Qt.NoFocus)
        self._pill_lang_btn.clicked.connect(self._on_language_change_requested)
        self._update_pill_lang_text()
        try:
            from ui.components.icon import Icon
            lang_px = Icon.load_pixmap("language", size=14)
            if lang_px and not lang_px.isNull():
                self._pill_lang_btn.setIcon(QIcon(lang_px))
                self._pill_lang_btn.setIconSize(QSize(14, 14))
        except Exception:
            pass
        content_lay.addWidget(self._pill_lang_btn)

        content_lay.addSpacing(4)
        content_lay.addWidget(self._create_pill_separator())
        content_lay.addSpacing(4)

        # Logout button
        self._pill_logout_btn = QPushButton()
        self._pill_logout_btn.setStyleSheet(_BTN_STYLE)
        self._pill_logout_btn.setFixedHeight(ScreenScale.h(28))
        self._pill_logout_btn.setFont(_btn_font)
        self._pill_logout_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._pill_logout_btn.setFocusPolicy(Qt.NoFocus)
        self._pill_logout_btn.clicked.connect(self._on_logout_requested)
        self._load_pill_icon(self._pill_logout_btn, "logout", tr("navbar.menu.logout"))
        content_lay.addWidget(self._pill_logout_btn)

        pill_layout.addWidget(self._pill_content)

        # Notification badge on sync button
        self._pill_sync_badge = QLabel(self._pill_sync_btn)
        self._pill_sync_badge.setAlignment(Qt.AlignCenter)
        self._pill_sync_badge.setFixedSize(ScreenScale.w(16), ScreenScale.h(16))
        self._pill_sync_badge.setStyleSheet("""
            QLabel {
                background-color: #EF4444;
                color: white;
                border-radius: 8px;
                font-size: 9px;
                font-weight: bold;
            }
        """)
        self._pill_sync_badge.hide()

        return pill

    def _toggle_pill(self):
        """Toggle settings pill between collapsed and expanded."""
        self._pill_expanded = not self._pill_expanded
        pill = self._settings_pill

        if self._pill_expanded:
            # Remove settings text, keep only icon when expanded
            self._pill_trigger.setText("\u25C8")
            self._pill_content.setVisible(True)
            self._pill_anim_min = QPropertyAnimation(pill, b"minimumWidth")
            self._pill_anim_min.setDuration(250)
            self._pill_anim_min.setStartValue(self._pill_collapsed_w)
            self._pill_anim_min.setEndValue(self._pill_expanded_w)
            self._pill_anim_min.setEasingCurve(QEasingCurve.OutCubic)
            self._pill_anim_max = QPropertyAnimation(pill, b"maximumWidth")
            self._pill_anim_max.setDuration(250)
            self._pill_anim_max.setStartValue(self._pill_collapsed_w)
            self._pill_anim_max.setEndValue(self._pill_expanded_w)
            self._pill_anim_max.setEasingCurve(QEasingCurve.OutCubic)
            self._pill_anim_min.start()
            self._pill_anim_max.start()
        else:
            self._pill_anim_min = QPropertyAnimation(pill, b"minimumWidth")
            self._pill_anim_min.setDuration(200)
            self._pill_anim_min.setStartValue(self._pill_expanded_w)
            self._pill_anim_min.setEndValue(self._pill_collapsed_w)
            self._pill_anim_min.setEasingCurve(QEasingCurve.InCubic)
            self._pill_anim_max = QPropertyAnimation(pill, b"maximumWidth")
            self._pill_anim_max.setDuration(200)
            self._pill_anim_max.setStartValue(self._pill_expanded_w)
            self._pill_anim_max.setEndValue(self._pill_collapsed_w)
            self._pill_anim_max.setEasingCurve(QEasingCurve.InCubic)
            self._pill_anim_min.finished.connect(self._on_pill_collapsed)
            self._pill_anim_min.start()
            self._pill_anim_max.start()

    def _on_pill_collapsed(self):
        """Restore trigger text and hide content after collapse animation."""
        self._pill_content.setVisible(False)
        self._pill_trigger.setText("\u25C8  " + tr("navbar.pill.settings"))

    def _create_pill_separator(self):
        sep = QFrame()
        sep.setFixedSize(1, ScreenScale.h(16))
        sep.setStyleSheet("background: rgba(139, 172, 200, 40);")
        return sep

    def _load_pill_icon(self, btn, icon_name, text):
        """Load tinted icon for a pill button and set text."""
        btn.setText(text)
        try:
            from ui.components.icon import Icon
            pixmap = Icon.load_pixmap(icon_name, size=14)
            if pixmap and not pixmap.isNull():
                tinted = QPixmap(pixmap.size())
                tinted.fill(Qt.transparent)
                p = QPainter(tinted)
                p.drawPixmap(0, 0, pixmap)
                p.setCompositionMode(QPainter.CompositionMode_SourceIn)
                p.fillRect(tinted.rect(), QColor(139, 172, 200, 200))
                p.end()
                btn.setIcon(QIcon(tinted))
                btn.setIconSize(QSize(14, 14))
        except Exception:
            pass

    def _update_pill_lang_text(self):
        current = get_language()
        text = "English" if current == "ar" else "\u0639\u0631\u0628\u064A"
        self._pill_lang_btn.setText(text)

    # -- Tab Indicator --

    def _init_tab_indicator(self):
        if not self.tab_buttons:
            return
        idx = self.current_tab_index
        if idx < len(self.tab_buttons) and self.tab_buttons[idx].isVisible():
            self._update_indicator_for_tab(idx, animate=False)

    def _update_indicator_for_tab(self, index: int, animate: bool = True):
        if index >= len(self.tab_buttons):
            return
        tab = self.tab_buttons[index]
        if not tab.isVisible():
            return
        try:
            pos = tab.mapTo(self._tabs_bar_frame, QPoint(0, 0))
            target = QRect(pos.x(), pos.y(), tab.width(), tab.height())
            if animate:
                self._tabs_bar_frame.animate_to(target)
            else:
                self._tabs_bar_frame.set_indicator_immediate(target)
        except Exception:
            pass

    def _set_active_tab(self, index: int):
        self.current_tab_index = index
        for i, tab in enumerate(self.tab_buttons):
            tab.set_active(i == index)
        if hasattr(self, '_tabs_bar_frame'):
            self._update_indicator_for_tab(index)

    def _on_tab_clicked(self, index: int):
        self._set_active_tab(index)
        self.tab_changed.emit(index)

    # -- Styles --

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QFrame#navbar {{
                background-color: {Colors.NAVBAR_GRADIENT_TOP};
                border: none;
            }}
            QFrame#navbar_top {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #061222,
                    stop:0.4 {Colors.NAVBAR_GRADIENT_MID},
                    stop:1.0 {Colors.NAVBAR_GRADIENT_BOT}
                );
                border-radius: 16px;
                border: none;
            }}
            QWidget#window_controls {{
                background: transparent;
            }}
            QPushButton#win_btn, QPushButton#win_close {{
                color: rgba(180, 210, 245, 190);
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: 400;
                border-radius: 6px;
            }}
            QPushButton#win_btn:hover {{
                background: rgba(15, 31, 61, 180);
                border: 1px solid {Colors.FROSTED_BORDER};
                color: white;
            }}
            QPushButton#win_btn:pressed {{
                background: rgba(56, 144, 223, 0.20);
                border: 1px solid {Colors.FROSTED_BORDER_HOVER};
                color: white;
            }}
            QPushButton#win_close:hover {{
                background: rgba(255, 59, 48, 0.80);
                border: 1px solid rgba(255, 59, 48, 0.40);
                color: white;
            }}
            QPushButton#win_close:pressed {{
                background: rgba(255, 59, 48, 0.65);
                color: white;
            }}
        """)

    # -- Role-based Visibility --

    TAB_PERMISSIONS = {
        "admin":            [0, 1, 2, 3, 4, 5, 6],
        "data_manager":     [0, 1, 2, 3, 4, 5, 6],
        "office_clerk":     [1],
        "field_supervisor": [5],
        "field_researcher": [],
        "analyst":          [],
    }

    def configure_for_role(self, role: str):
        allowed = self.TAB_PERMISSIONS.get(role, [0, 1, 2, 3])
        for i, btn in enumerate(self.tab_buttons):
            btn.setVisible(i in allowed)

        for idx in sorted(allowed):
            if idx < len(self.tab_buttons):
                self._set_active_tab(idx)
                self.tab_changed.emit(idx)
                break

        # Pill button visibility
        if hasattr(self, '_pill_sync_btn'):
            self._pill_sync_btn.setVisible(role in {"admin", "data_manager", "field_supervisor"})

    # -- Public API --

    def set_current_tab(self, index: int):
        if 0 <= index < len(self.tab_buttons):
            self._set_active_tab(index)

    def get_current_tab(self) -> int:
        return self.current_tab_index

    def set_user_id(self, user_id: str):
        self.user_id = user_id
        if hasattr(self, 'id_badge'):
            self.id_badge.set_user_id(user_id)

    def update_language(self, is_arabic: bool):
        # Update tab titles
        for i, key in enumerate(self._tab_keys):
            if i < len(self.tab_buttons):
                self.tab_buttons[i].set_text(tr(key))

        # Update pill button texts
        if hasattr(self, '_pill_trigger'):
            self._pill_trigger.setText("\u25C8  " + tr("navbar.pill.settings"))
        if hasattr(self, '_pill_sync_btn'):
            self._load_pill_icon(self._pill_sync_btn, "fluent", tr("navbar.menu.sync_data"))
        if hasattr(self, '_pill_pwd_btn'):
            self._load_pill_icon(self._pill_pwd_btn, "safe", tr("navbar.menu.change_password"))
        if hasattr(self, '_pill_logout_btn'):
            self._load_pill_icon(self._pill_logout_btn, "logout", tr("navbar.menu.logout"))
        if hasattr(self, '_pill_lang_btn'):
            self._update_pill_lang_text()

        # Update search placeholder
        if hasattr(self, 'search_input'):
            mode = getattr(self, 'search_mode', 'default')
            placeholder_map = {
                'default': "navbar.search.default",
                'name': "navbar.search.by_name",
                'claim_id': "navbar.search.by_claim_id",
                'building': "navbar.search.by_building",
            }
            self.search_input.setPlaceholderText(tr(placeholder_map.get(mode, "navbar.search.default")))

        # Update ID badge
        if hasattr(self, 'id_badge'):
            self.id_badge.update_language(is_arabic)

        # Reposition indicator after tab text change
        QTimer.singleShot(50, lambda: self._update_indicator_for_tab(
            self.current_tab_index, animate=False
        ))

    def show_sync_notification(self, count: int):
        if hasattr(self, '_pill_sync_badge'):
            self._pill_sync_badge.setText(str(count) if count <= 9 else "9+")
            self._pill_sync_badge.show()
            self._pill_sync_badge.raise_()
            btn = self._pill_sync_btn
            self._pill_sync_badge.move(btn.width() - 10, -2)

    def hide_sync_notification(self):
        if hasattr(self, '_pill_sync_badge'):
            self._pill_sync_badge.hide()

    # -- Signal Handlers --

    def _on_logout_requested(self):
        self.logout_requested.emit()

    def _on_language_change_requested(self):
        self.language_change_requested.emit()

    def _on_sync_requested(self):
        self.sync_requested.emit()

    def _on_password_change_requested(self):
        self.password_change_requested.emit()

    def _on_import_requested(self):
        self.import_requested.emit()

    def _on_search(self):
        text = self.search_input.text()
        self.clear_btn.setVisible(bool(text.strip()))
        self.search_requested.emit(text)

    def _on_search_text_changed(self, text: str):
        self.clear_btn.setVisible(bool(text.strip()))

    def _on_search_menu_clicked(self):
        from .dialogs.search_filter_dialog import SearchFilterDialog
        filters = SearchFilterDialog.get_filters(parent=self.window())
        if filters is None:
            return
        if any(v for v in filters.values() if v):
            self.filter_applied.emit(filters)

    def _on_clear_search(self):
        self.search_input.clear()
        self.clear_btn.setVisible(False)
        self.search_requested.emit("")

    # -- Events --

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, '_pulsing_logo'):
            self._pulsing_logo.start_pulse()

    def hideEvent(self, event):
        if hasattr(self, '_pulsing_logo'):
            self._pulsing_logo.stop_pulse()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_tabs_bar_frame') and self.tab_buttons:
            QTimer.singleShot(0, lambda: self._update_indicator_for_tab(
                self.current_tab_index, animate=False
            ))


class SimpleNavbar(QFrame):
    """Simplified Navbar without tabs for secondary pages."""

    search_requested = pyqtSignal(str)
    back_clicked = pyqtSignal()

    def __init__(self, title="", user_id="12345", show_search=True, show_back=False, parent=None):
        super().__init__(parent)
        self.setObjectName("simple_navbar")
        self.user_id = user_id
        self.title = title
        self.show_search = show_search
        self.show_back = show_back
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        if self.show_back:
            back_btn = QPushButton("\u2190")
            back_btn.setFixedSize(ScreenScale.w(40), ScreenScale.h(40))
            back_btn.setFont(create_font(size=15, weight=QFont.Normal))
            back_btn.setCursor(QCursor(Qt.PointingHandCursor))
            back_btn.setStyleSheet("""
                QPushButton { background: transparent; color: white; border: none; }
                QPushButton:hover { background: rgba(255,255,255,0.1); border-radius: 6px; }
            """)
            back_btn.clicked.connect(self.back_clicked.emit)
            layout.addWidget(back_btn)

        logo = LogoWidget(height=20)
        layout.addWidget(logo)

        id_badge = IDBadgeWidget(user_id=self.user_id)
        layout.addWidget(id_badge)

        if self.title:
            title_label = QLabel(self.title)
            title_label.setFont(create_font(size=12, weight=QFont.DemiBold, letter_spacing=0))
            title_label.setStyleSheet("color: white; background: transparent;")
            layout.addWidget(title_label)

        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        if self.show_search:
            search_widget = QWidget()
            search_widget.setMinimumWidth(ScreenScale.w(200))
            search_widget.setMaximumWidth(ScreenScale.w(320))
            search_layout = QHBoxLayout(search_widget)
            search_layout.setContentsMargins(0, 0, 0, 0)
            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText(tr("navbar.search.simple"))
            self.search_input.setFont(create_font(size=10, weight=QFont.Normal, letter_spacing=0))
            self.search_input.setFixedHeight(ScreenScale.h(36))
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Colors.SEARCH_BG};
                    color: white; border: none; border-radius: 6px; padding: 8px 16px;
                }}
                QLineEdit::placeholder {{ color: rgba(255,255,255,0.5); }}
            """)
            self.search_input.returnPressed.connect(self._on_search)
            search_layout.addWidget(self.search_input)
            layout.addWidget(search_widget)

        self.setFixedHeight(ScreenScale.h(60))

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QFrame#simple_navbar {{ background-color: {Colors.NAVBAR_BG}; border: none; }}
        """)

    def _on_search(self):
        if self.show_search and hasattr(self, 'search_input'):
            text = self.search_input.text().strip()
            if text:
                self.search_requested.emit(text)
