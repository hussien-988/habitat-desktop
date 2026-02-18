"""
Reusable UI Components Library
Based on UN-Habitat Design System

All components follow the new Figma design specifications.
"""

from PyQt5.QtWidgets import (
    QPushButton, QLineEdit, QLabel, QFrame, QHBoxLayout,
    QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QComboBox, QTextEdit, QDialog, QDialogButtonBox,
    QTabWidget, QTabBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette

from ..design_system import DesignTokens, Colors, Typography, Spacing, BorderRadius
from ..font_utils import create_font, FontManager


class Button(QPushButton):
    """
    Styled button component
    Based on Figma button specifications
    """
    def __init__(self, text="", variant="primary", size="medium", icon=None, parent=None):
        super().__init__(text, parent)
        self.variant = variant
        self.size = size

        if icon:
            self.setIcon(icon)

        self._apply_style()

    def _apply_style(self):
        """Apply design system styles"""
        self.setStyleSheet(DesignTokens.components.get_button_style(
            variant=self.variant,
            size=self.size
        ))
        self.setCursor(Qt.PointingHandCursor)

        # Set minimum size based on size variant
        size_map = {
            "small": QSize(80, 32),
            "medium": QSize(100, 40),
            "large": QSize(120, 48)
        }
        self.setMinimumSize(size_map.get(self.size, size_map["medium"]))


class SearchBar(QLineEdit):
    """
    Search bar component for navbar
    Based on Figma pages 1-5 design
    """
    def __init__(self, placeholder="ابحث عن المراد أو المسودة...", parent=None):
        super().__init__(parent)
        self.setObjectName("search_bar")
        self.setPlaceholderText(placeholder)
        self.setStyleSheet(DesignTokens.components.get_search_bar_style())
        self.setMinimumWidth(300)
        self.setFont(Typography.get_body_font())


class Input(QLineEdit):
    """
    Standard input field component
    """
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet(DesignTokens.components.get_input_style())
        self.setFont(Typography.get_body_font())
        self.setMinimumHeight(40)


class TextArea(QTextEdit):
    """
    Multi-line text area component
    """
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet(DesignTokens.components.get_input_style())
        self.setFont(Typography.get_body_font())
        self.setMinimumHeight(100)


class Dropdown(QComboBox):
    """
    Dropdown/Select component
    """
    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        if items:
            self.addItems(items)

        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {Colors.INPUT_BG};
                border: 1px solid {Colors.INPUT_BORDER};
                border-radius: {BorderRadius.SM}px;
                padding: {Spacing.SM}px {Spacing.MD}px;
                font-size: {Typography.SIZE_BODY}px;
                min-height: 40px;
            }}
            QComboBox:hover {{
                border-color: {Colors.PRIMARY_BLUE};
            }}
            QComboBox:focus {{
                border-color: {Colors.INPUT_BORDER_FOCUS};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: url(:/icons/chevron-down.svg);
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: {BorderRadius.SM}px;
                selection-background-color: {Colors.TABLE_ROW_SELECTED};
                selection-color: {Colors.TEXT_PRIMARY};
            }}
        """)
        self.setFont(Typography.get_body_font())


class Card(QFrame):
    """
    Card container component
    Based on Figma card design
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(DesignTokens.components.get_card_style())
        self.setFrameShape(QFrame.StyledPanel)


class Badge(QLabel):
    """
    Badge/Chip component for status indicators
    Based on Figma pages 4-5 status badges
    """
    def __init__(self, text="", status="info", parent=None):
        super().__init__(text, parent)
        self.status = status
        self._apply_style()

    def _apply_style(self):
        """Apply badge styles based on status"""
        status_colors = {
            "draft": (Colors.BADGE_DRAFT, Colors.PRIMARY_WHITE),
            "finalized": (Colors.BADGE_FINALIZED, Colors.PRIMARY_WHITE),
            "pending": (Colors.BADGE_PENDING, Colors.PRIMARY_WHITE),
            "rejected": (Colors.BADGE_REJECTED, Colors.PRIMARY_WHITE),
            "info": (Colors.INFO, Colors.PRIMARY_WHITE),
            "success": (Colors.SUCCESS, Colors.PRIMARY_WHITE),
            "warning": (Colors.WARNING, Colors.PRIMARY_WHITE),
            "error": (Colors.ERROR, Colors.PRIMARY_WHITE),
        }

        bg_color, text_color = status_colors.get(self.status, status_colors["info"])

        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: {BorderRadius.SM}px;
                padding: {Spacing.XS}px {Spacing.MD}px;
                font-size: {Typography.SIZE_CAPTION}px;
                font-weight: {Typography.WEIGHT_MEDIUM};
            }}
        """)
        self.setAlignment(Qt.AlignCenter)


class Heading(QLabel):
    """
    Heading component (H1, H2, H3)
    """
    def __init__(self, text="", level=1, parent=None):
        super().__init__(text, parent)
        self.level = level
        self.setFont(Typography.get_heading_font(level))
        self.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")


class EmptyState(QWidget):
    """
    Empty state component
    Based on Figma page 3 design
    """
    def __init__(self, icon_text="➕", title="لا توجد بيانات بعد",
                 message="ابدأ بإضافة الحالات لإظهارها هنا", parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(Spacing.MD)

        # Icon
        icon_label = QLabel(icon_text)
        icon_label.setFont(create_font(size=48, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0))
        icon_label.setStyleSheet(f"""
            color: {Colors.PRIMARY_BLUE};
            background-color: {Colors.BACKGROUND};
            border-radius: {BorderRadius.FULL}px;
            padding: {Spacing.LG}px;
        """)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(100, 100)

        # Title
        title_label = Heading(title, level=2)
        title_label.setAlignment(Qt.AlignCenter)

        # Message
        message_label = QLabel(message)
        message_label.setFont(Typography.get_body_font())
        message_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(message_label)

        self.setLayout(layout)


class DataTable(QTableWidget):
    """
    Styled table component
    Based on Figma table design (pages 4-5)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(DesignTokens.components.get_table_style())

        # Table settings
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)

        # Enable sorting
        self.setSortingEnabled(True)

        # Set row height
        self.verticalHeader().setDefaultSectionSize(48)


class Modal(QDialog):
    """
    Modal/Dialog component
    Based on Figma modal designs (pages 7, 11-13, 16-18)
    """
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setStyleSheet(DesignTokens.components.get_dialog_style())
        self.setModal(True)
        self.setMinimumWidth(500)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(Spacing.LG)
        main_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        # Title
        if title:
            title_label = Heading(title, level=2)
            main_layout.addWidget(title_label)

        # Content area (to be filled by subclass)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(Spacing.MD)
        main_layout.addLayout(self.content_layout)

        # Button box
        self.button_box = QDialogButtonBox()
        self.button_box.setStyleSheet(f"""
            QPushButton {{
                min-width: 100px;
                min-height: 40px;
            }}
        """)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)

    def add_content(self, widget):
        """Add content to the modal"""
        self.content_layout.addWidget(widget)

    def set_buttons(self, accept_text="حفظ", reject_text="إلغاء"):
        """Set modal buttons"""
        self.button_box.clear()

        accept_btn = Button(accept_text, variant="primary")
        reject_btn = Button(reject_text, variant="secondary")

        self.button_box.addButton(accept_btn, QDialogButtonBox.AcceptRole)
        self.button_box.addButton(reject_btn, QDialogButtonBox.RejectRole)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)


class ConfirmDialog(Modal):
    """
    Confirmation dialog component
    Based on Figma pages 24-25
    """
    def __init__(self, title="تأكيد", message="هل أنت متأكد؟",
                 icon="⚠️", parent=None):
        super().__init__(title, parent)

        # Icon and message layout
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setSpacing(Spacing.MD)

        # Warning icon
        icon_label = QLabel(icon)
        icon_label.setFont(create_font(size=32, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0))
        icon_label.setStyleSheet(f"color: {Colors.WARNING};")

        # Message
        message_label = QLabel(message)
        message_label.setFont(Typography.get_body_font())
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")

        content_layout.addWidget(icon_label)
        content_layout.addWidget(message_label, 1)

        self.add_content(content)
        self.set_buttons(accept_text="تأكيد", reject_text="إلغاء")


class SuccessDialog(Modal):
    """
    Success message dialog
    Based on Figma page 24
    """
    def __init__(self, title="تمت الإضافة بنجاح",
                 message="تم حفظ جميع المعلومات",
                 reference_code="", parent=None):
        super().__init__(title, parent)

        # Success content
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignCenter)
        content_layout.setSpacing(Spacing.MD)

        # Success icon
        icon_label = QLabel("👍")
        icon_label.setFont(create_font(size=48, weight=FontManager.WEIGHT_REGULAR, letter_spacing=0))
        icon_label.setAlignment(Qt.AlignCenter)

        # Message
        message_label = QLabel(message)
        message_label.setFont(Typography.get_body_font())
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")

        content_layout.addWidget(icon_label)

        if reference_code:
            ref_label = Heading(reference_code, level=2)
            ref_label.setAlignment(Qt.AlignCenter)
            ref_label.setStyleSheet(f"color: {Colors.PRIMARY_BLUE};")
            content_layout.addWidget(ref_label)

        content_layout.addWidget(message_label)

        self.add_content(content)
        self.set_buttons(accept_text="حسناً", reject_text="")

        # Hide reject button
        buttons = self.button_box.buttons()
        if len(buttons) > 1:
            buttons[1].hide()


class FormField(QWidget):
    """
    Form field with label and input
    Based on Figma form designs (pages 6-23)
    """
    def __init__(self, label_text="", input_type="text", placeholder="",
                 required=False, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setSpacing(Spacing.LABEL_SPACING)
        layout.setContentsMargins(0, 0, 0, 0)

        # Label
        label = QLabel(label_text)
        label.setFont(Typography.get_body_font(bold=True))
        label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")

        if required:
            label.setText(f"{label_text} *")
            label.setStyleSheet(f"color: {Colors.ERROR};")

        # Input based on type
        if input_type == "textarea":
            self.input = TextArea(placeholder)
        elif input_type == "dropdown":
            self.input = Dropdown()
        else:
            self.input = Input(placeholder)

        layout.addWidget(label)
        layout.addWidget(self.input)

        self.setLayout(layout)

    def get_value(self):
        """Get input value"""
        if isinstance(self.input, QComboBox):
            return self.input.currentText()
        else:
            return self.input.toPlainText() if isinstance(self.input, QTextEdit) else self.input.text()

    def set_value(self, value):
        """Set input value"""
        if isinstance(self.input, QComboBox):
            index = self.input.findText(value)
            if index >= 0:
                self.input.setCurrentIndex(index)
        elif isinstance(self.input, QTextEdit):
            self.input.setPlainText(value)
        else:
            self.input.setText(value)
