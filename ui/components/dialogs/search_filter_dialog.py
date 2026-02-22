# -*- coding: utf-8 -*-
"""
Search Filter Dialog — ديالوغ الفلتر
Follows SecurityDialog/PasswordDialog container pattern (DRY).

Fields (matching Figma):
  1. رمز البناء — Building code text field with search icon
  2. العنوان — Address/governorate combo
  3. التاريخ — Single date picker
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect,
    QDateEdit, QComboBox
)
from PyQt5.QtCore import Qt, QDate, QSize
from PyQt5.QtGui import QColor, QFont, QIcon
from pathlib import Path

from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from services.translation_manager import tr


# Input field stylesheet (DRY — shared with PasswordDialog)
_INPUT_STYLE = """
    QLineEdit {
        background-color: #f0f7ff;
        border: 1px solid #E1E8ED;
        border-radius: 8px;
        padding: 0 14px;
        color: #2C3E50;
    }
    QLineEdit:focus {
        border: 2px solid #3890DF;
        padding: 0 13px;
    }
    QLineEdit::placeholder {
        color: #9CA3AF;
    }
"""

_COMBO_STYLE = f"""
    QComboBox {{
        background-color: #f0f7ff;
        border: 1px solid #E1E8ED;
        border-radius: 8px;
        padding: 0 14px;
        color: #2C3E50;
    }}
    QComboBox:focus {{
        border: 2px solid #3890DF;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center left;
        width: 30px;
        border: none;
    }}
    QComboBox::down-arrow {{
        image: none;
        width: 0;
    }}
    QComboBox QAbstractItemView {{
        background-color: white;
        border: 1px solid #E1E8ED;
        selection-background-color: {Colors.PRIMARY_BLUE};
        selection-color: white;
        outline: 0;
    }}
"""

_DATE_STYLE = f"""
    QDateEdit {{
        background-color: #f0f7ff;
        border: 1px solid #E1E8ED;
        border-radius: 8px;
        padding: 0 14px;
        color: #2C3E50;
    }}
    QDateEdit:focus {{
        border: 2px solid #3890DF;
    }}
    QDateEdit::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center left;
        width: 30px;
        border: none;
    }}
"""


class SearchFilterDialog(QDialog):
    """Dialog for filtering draft surveys.
    Closes when clicking outside the card (overlay dismiss pattern)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filters = None

        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Cover the entire parent window
        if parent:
            main_win = parent.window() or parent
            self.setGeometry(main_win.geometry())

        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)

        # Overlay: semi-transparent background that covers everything
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        overlay = QFrame()
        overlay.setObjectName("filterOverlay")
        overlay.setStyleSheet("""
            QFrame#filterOverlay {
                background-color: rgba(0, 0, 0, 0.3);
            }
        """)
        # Click on overlay → close
        overlay.mousePressEvent = lambda e: self.reject()

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        # White container card (DRY: same pattern as SecurityDialog/PasswordDialog)
        container = QFrame()
        container.setObjectName("filterContainer")
        container.setFixedWidth(476)
        container.setLayoutDirection(Qt.RightToLeft)
        container.setStyleSheet("""
            QFrame#filterContainer {
                background-color: #FFFFFF;
                border-radius: 24px;
            }
            QFrame#filterContainer QLabel {
                background-color: transparent;
            }
        """)
        # Prevent clicks on card from reaching overlay
        container.mousePressEvent = lambda e: e.accept()

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel(tr("navbar.filter.title"))
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        title.setAlignment(Qt.AlignRight)
        layout.addWidget(title)

        # --- Field 1: رمز البناء (Building Code) ---
        self.building_code_input = self._create_field_with_icon(
            layout,
            tr("navbar.filter.building_code"),
            tr("navbar.filter.building_code_hint"),
        )

        # --- Field 2: العنوان (Address/Governorate) ---
        addr_label = QLabel(tr("navbar.filter.address"))
        addr_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        addr_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        addr_label.setAlignment(Qt.AlignRight)
        layout.addWidget(addr_label)

        self.address_combo = QComboBox()
        self.address_combo.setFixedHeight(42)
        self.address_combo.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        self.address_combo.setStyleSheet(_COMBO_STYLE)
        self.address_combo.addItem(tr("navbar.filter.choose"), "")
        self._populate_governorates()
        layout.addWidget(self.address_combo)

        # --- Field 3: التاريخ (Date) ---
        date_label = QLabel(tr("navbar.filter.date"))
        date_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        date_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        date_label.setAlignment(Qt.AlignRight)
        layout.addWidget(date_label)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.setFixedHeight(42)
        self.date_input.setStyleSheet(_DATE_STYLE)
        self.date_input.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        self.date_input.setLayoutDirection(Qt.LeftToRight)
        layout.addWidget(self.date_input)

        # Button: تطبيق (Apply) only
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        apply_btn = self._create_button(tr("navbar.filter.apply"), primary=True)
        apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(apply_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        overlay_layout.addWidget(container)
        outer.addWidget(overlay)

    def _create_field_with_icon(self, parent_layout, label_text, placeholder):
        """Create building code field with search icon (matching Figma)."""
        label = QLabel(label_text)
        label.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        label.setAlignment(Qt.AlignRight)
        parent_layout.addWidget(label)

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFixedHeight(42)
        field.setFont(create_font(size=FontManager.SIZE_BODY, weight=FontManager.WEIGHT_REGULAR))
        field.setStyleSheet(_INPUT_STYLE)

        # Add search icon action inside the field
        search_icon_path = Path(__file__).parent.parent.parent / "assets" / "images" / "search.png"
        if search_icon_path.exists():
            icon = QIcon(str(search_icon_path))
            field.addAction(icon, QLineEdit.LeadingPosition)

        parent_layout.addWidget(field)
        return field

    def _populate_governorates(self):
        """Populate address combo with governorates from DivisionsService."""
        try:
            from services.divisions_service import DivisionsService
            service = DivisionsService()
            for code, name_en, name_ar in service.get_governorates():
                self.address_combo.addItem(name_ar, code)
        except Exception:
            pass

    def _create_button(self, text: str, primary: bool) -> QPushButton:
        """DRY: Same button pattern as SecurityDialog/PasswordDialog."""
        btn = QPushButton(text)
        btn.setFixedSize(170, 50)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFont(create_font(size=10, weight=QFont.Medium))

        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.PRIMARY_BLUE};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: #2D7BC9;
                }}
                QPushButton:pressed {{
                    background-color: #2468B0;
                }}
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    color: #6B7280;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #F9FAFB;
                }
                QPushButton:pressed {
                    background-color: #F3F4F6;
                }
            """)
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(8)
            shadow.setXOffset(0)
            shadow.setYOffset(2)
            shadow.setColor(QColor(0, 0, 0, 25))
            btn.setGraphicsEffect(shadow)

        return btn

    def _on_apply(self):
        gov_code = self.address_combo.currentData() or ""
        self.filters = {
            'building_code': self.building_code_input.text().strip(),
            'governorate_code': gov_code,
            'date': self.date_input.date().toString("yyyy-MM-dd") if gov_code or self.building_code_input.text().strip() else "",
        }
        # Always include date if user explicitly interacted
        self.filters['date'] = self.date_input.date().toString("yyyy-MM-dd")
        self.accept()

    def showEvent(self, event):
        """Ensure dialog covers entire parent on show."""
        super().showEvent(event)
        parent = self.parent()
        if parent:
            main_win = parent.window() or parent
            self.setGeometry(main_win.geometry())

    def keyPressEvent(self, event):
        """Allow Escape key to close."""
        if event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def get_filters(parent=None) -> Optional[dict]:
        """Show filter dialog. Returns filters dict or None if cancelled."""
        dialog = SearchFilterDialog(parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.filters
        return None
