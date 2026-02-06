# -*- coding: utf-8 -*-
"""
Field Work Preparation - Step 2: Select Field Researcher
UC-012: Assign Buildings to Field Teams

Select researcher to assign buildings for field work.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QFrame, QToolButton, QSizePolicy, QListWidget, QListWidgetItem,
    QRadioButton, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon

from ui.components.icon import Icon
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from utils.i18n import I18n
from utils.logger import get_logger

logger = get_logger(__name__)


class ResearcherRadioItem(QWidget):
    """Custom radio button item for researcher list."""

    def __init__(self, researcher_id, available, parent=None):
        super().__init__(parent)
        self.researcher_id = researcher_id
        self.available = available
        self.setCursor(Qt.PointingHandCursor)

        # Set minimum height (same as Step 1)
        self.setMinimumHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # === Radio button (circular checkbox with thick visible border) ===
        self.radio = QRadioButton()
        self.radio.setFixedSize(20, 20)
        self.radio.setStyleSheet("""
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border: 3px solid #C4CDD5;
                border-radius: 10px;
                background: white;
            }
            QRadioButton::indicator:hover {
                border-color: #3890DF;
            }
            QRadioButton::indicator:checked {
                background: white;
                border: 3px solid #3890DF;
            }
            QRadioButton::indicator:checked:after {
                content: "";
                width: 10px;
                height: 10px;
                border-radius: 5px;
                background: #3890DF;
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
            }
        """)
        layout.addWidget(self.radio)

        # Icon container - Darker background to show Vector icon better
        icon_container = QLabel()
        icon_container.setFixedSize(32, 32)
        icon_container.setAlignment(Qt.AlignCenter)
        icon_container.setStyleSheet("""
            QLabel {
                background-color: #d6e9ff;
                border-radius: 6px;
            }
        """)
        # Use Vector icon (same pattern as building-03 in Step 1)
        icon_pixmap = Icon.load_pixmap("Vector", size=20)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_container.setPixmap(icon_pixmap)
        else:
            icon_container.setText("👤")
        layout.addWidget(icon_container)

        # Text with researcher ID (no stretch factor - text is short)
        item_text = f"ID {researcher_id}"
        text_label = QLabel(item_text)
        text_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        text_label.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent;")
        layout.addWidget(text_label)  # No stretch - keeps text next to icon

        # Add stretch at the end to push all elements together on the right
        layout.addStretch(1)

    def mousePressEvent(self, event):
        """Handle click on entire row - select radio button."""
        self.radio.setChecked(True)
        super().mousePressEvent(event)


class FieldWorkPreparationStep2(QWidget):
    """
    Step 2: Select field researcher.

    Content only (no header/footer) - same structure as Step 1.
    """

    researcher_selected = pyqtSignal(str)  # Emits researcher name

    def __init__(self, selected_buildings, i18n: I18n, parent=None):
        super().__init__(parent)
        self.selected_buildings = selected_buildings
        self.i18n = i18n
        self.page = parent  # Store reference to parent page
        self._selected_researcher = None
        self._is_initialized = False  # Flag to prevent auto-showing suggestions

        # Mock researchers list (replace with actual data later)
        # Format: (ID, Available)
        self._researchers = [
            ("12345", True),
            ("12346", True),
            ("12347", False),
            ("12348", True),
            ("12349", True)
        ]

        self._setup_ui()
        self._is_initialized = True  # Mark as initialized

    def _setup_ui(self):
        """Setup UI - content only (no header/footer)."""
        self.setLayoutDirection(Qt.RightToLeft)

        # Background
        self.setStyleSheet("background: transparent;")

        # === MAIN LAYOUT (No padding - parent has padding) ===
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === CARDS CONTAINER ===
        cards_container = QWidget()
        cards_container.setStyleSheet("background-color: transparent;")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 15, 0, 16)
        cards_layout.setSpacing(15)

        # ===== Card: اختر الباحث الميداني =====
        card = QFrame()
        card.setObjectName("researcherCard")
        card.setStyleSheet("""
            QFrame#researcherCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
        """)

        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(6)

        # Label: اختر الباحث الميداني
        label = QLabel("اختر الباحث الميداني")
        label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        card_layout.addWidget(label)

        # === Search bar (same as Step 1) ===
        search_bar = QFrame()
        search_bar.setObjectName("searchBar")
        search_bar.setFixedHeight(42)
        search_bar.setStyleSheet(f"""
            QFrame#searchBar {{
                background-color: {Colors.SEARCH_BAR_BG};
                border: 1px solid {Colors.SEARCH_BAR_BORDER};
                border-radius: 8px;
            }}
        """)
        search_bar.setLayoutDirection(Qt.LeftToRight)

        sb = QHBoxLayout(search_bar)
        sb.setContentsMargins(14, 8, 14, 8)
        sb.setSpacing(8)

        # Search icon button
        search_icon_btn = QToolButton()
        search_icon_btn.setCursor(Qt.PointingHandCursor)
        search_icon_btn.setFixedSize(30, 30)
        search_icon_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
            }
            QToolButton:hover {
                background-color: #EEF6FF;
                border-radius: 8px;
            }
        """)
        search_pixmap = Icon.load_pixmap("search", size=20)
        if search_pixmap and not search_pixmap.isNull():
            search_icon_btn.setIcon(QIcon(search_pixmap))
            search_icon_btn.setIconSize(QSize(20, 20))
        else:
            search_icon_btn.setText("🔍")

        search_icon_btn.clicked.connect(self._on_search)

        # Input
        self.researcher_search = QLineEdit()
        self.researcher_search.setPlaceholderText("ابحث عن اسم جامع البيانات او معرف الجهاز")
        self.researcher_search.setLayoutDirection(Qt.RightToLeft)
        self.researcher_search.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                font-family: 'IBM Plex Sans Arabic';
                font-size: 10pt;
                padding: 0px 6px;
                min-height: 28px;
                color: #2C3E50;
            }
        """)
        self.researcher_search.textChanged.connect(self._on_search_text_changed)
        # Hide suggestions when Enter is pressed
        self.researcher_search.returnPressed.connect(self._on_search_enter)
        # Show suggestions on focus
        self.researcher_search.focusInEvent = lambda event: self._on_search_focus(event)

        # Assemble search bar
        sb.addWidget(self.researcher_search)
        sb.addWidget(search_icon_btn, 1)

        card_layout.addWidget(search_bar)

        cards_layout.addWidget(card)

        # === Suggestions list (same as Step 1) ===
        self.researchers_list = QListWidget()
        self.researchers_list.setVisible(False)
        self.researchers_list.setFixedHeight(0)
        self.researchers_list.setFixedWidth(1225)

        # Hide scrollbar but keep scrolling
        self.researchers_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.researchers_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.researchers_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                background-color: {Colors.SURFACE};
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-bottom: none;
            }}
            QListWidget::item:selected {{
                background-color: #EFF6FF;
            }}
        """)

        # Position list: overlaps with card's bottom padding
        cards_layout.addSpacing(-27)

        # Center the list horizontally
        list_container = QHBoxLayout()
        list_container.addStretch(1)
        list_container.addWidget(self.researchers_list)
        list_container.addStretch(1)

        cards_layout.addLayout(list_container)

        # Correct spacing
        cards_layout.addSpacing(42)

        # ===== Card: العناصر المحفوظة (Selected Researcher) =====
        self.selected_card = QFrame()
        self.selected_card.setObjectName("selectedCard")
        self.selected_card.setStyleSheet("""
            QFrame#selectedCard {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
        """)
        self.selected_card.setVisible(False)  # Initially hidden
        self.selected_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        selected_card_layout = QVBoxLayout(self.selected_card)
        selected_card_layout.setContentsMargins(12, 12, 12, 12)
        selected_card_layout.setSpacing(12)

        # Header: title + count + availability (like Step 1, but with availability)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)

        self.selected_title = QLabel("العناصر المحفوظة")
        self.selected_title.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.selected_title.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        header_layout.addWidget(self.selected_title)

        # Count: "2 بناء" (not "(2)")
        self.selected_count_label = QLabel(f"{len(self.selected_buildings)} بناء")
        self.selected_count_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.selected_count_label.setStyleSheet("color: #3890DF; background: transparent;")
        header_layout.addWidget(self.selected_count_label)

        # Small space (not stretch!)
        header_layout.addSpacing(8)

        # Availability status (no label, just value)
        self.availability_value = QLabel("متوفر")
        self.availability_value.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self.availability_value.setStyleSheet("color: #10B981; background: transparent;")
        header_layout.addWidget(self.availability_value)

        header_layout.addStretch()

        selected_card_layout.addLayout(header_layout)

        # Content layout for selected researcher
        self.selected_content_layout = QVBoxLayout()
        self.selected_content_layout.setContentsMargins(0, 0, 0, 0)
        self.selected_content_layout.setSpacing(0)

        selected_card_layout.addLayout(self.selected_content_layout)

        cards_layout.addWidget(self.selected_card)

        # Load researchers into list
        self._load_researchers()

        # Add cards to main layout
        main_layout.addWidget(cards_container)

        # Add stretch to push content to top
        main_layout.addStretch(1)

    def mousePressEvent(self, event):
        """Handle click outside suggestions to hide them and show selected card."""
        # Check if suggestions list is visible
        if self.researchers_list.isVisible():
            # Check if click is outside the suggestions list and search field
            if not self.researchers_list.underMouse() and not self.researcher_search.underMouse():
                # Hide suggestions
                self._set_suggestions_visible(False)

                # Show selected card if researcher is selected
                if self._selected_researcher:
                    self._show_selected_card()

        super().mousePressEvent(event)

    def _load_researchers(self):
        """Load researchers into the list."""
        self.researchers_list.clear()

        for researcher_id, available in self._researchers:
            item = QListWidgetItem(self.researchers_list)

            # Create custom widget with radio button
            widget = ResearcherRadioItem(researcher_id, available, self)
            widget.radio.toggled.connect(
                lambda checked, rid=researcher_id, avail=available:
                self._on_researcher_selected(rid, avail, checked)
            )

            # Set item size
            item.setSizeHint(widget.sizeHint())

            self.researchers_list.addItem(item)
            self.researchers_list.setItemWidget(item, widget)

    def _on_researcher_selected(self, researcher_id, available, checked):
        """Handle researcher selection (hide suggestions like Step 1)."""
        if checked:
            self._selected_researcher = {
                'id': researcher_id,
                'name': f"ID {researcher_id}",
                'available': available
            }
            logger.info(f"Researcher selected: ID {researcher_id}")

            # Update search field with selected researcher ID
            self.researcher_search.setText(f"ID {researcher_id}")

            # Hide suggestions and show selected card (like Step 1)
            self._set_suggestions_visible(False)
            self._show_selected_card()

            # Enable next button via parent page
            if self.page and hasattr(self.page, 'enable_next_button'):
                self.page.enable_next_button(True)

            # Emit signal
            self.researcher_selected.emit(researcher_id)

    def _on_search_focus(self, event):
        """Show suggestions when search field gets focus (only if initialized)."""
        # Call the original focusInEvent
        from PyQt5.QtWidgets import QLineEdit
        QLineEdit.focusInEvent(self.researcher_search, event)

        # Only show suggestions if widget is fully initialized
        # This prevents auto-showing on initial load
        if self._is_initialized:
            self._set_suggestions_visible(True)
            self._filter_researchers()

    def _on_search(self):
        """Handle search icon click."""
        search_text = self.researcher_search.text().strip()
        logger.debug(f"Searching for researcher: {search_text}")
        self._filter_researchers()

    def _on_search_text_changed(self, text):
        """Filter suggestions on text change (don't auto-show/hide)."""
        # Only filter, don't auto-show suggestions
        # Suggestions are shown on focus, hidden on selection
        self._filter_researchers()

    def _on_search_enter(self):
        """Handle Enter key press - hide suggestions and show selected card."""
        # Hide suggestions
        self._set_suggestions_visible(False)

        # Show selected card if researcher is selected
        if self._selected_researcher:
            self._show_selected_card()

        # Update selected card visibility
        self._update_selected_card_visibility()

    def _filter_researchers(self):
        """Filter researchers list based on search text."""
        search_text = self.researcher_search.text().lower()

        for i in range(self.researchers_list.count()):
            item = self.researchers_list.item(i)
            widget = self.researchers_list.itemWidget(item)

            if widget and hasattr(widget, 'researcher_id'):
                researcher_id = widget.researcher_id

                # Search text match
                text_match = (
                    search_text in researcher_id.lower() if researcher_id else False
                ) if search_text else True

                # Show only if matches
                item.setHidden(not text_match)

    def _set_suggestions_visible(self, visible: bool):
        """Show/hide suggestions list with proper height adjustment."""
        self.researchers_list.setVisible(visible)
        self.researchers_list.setFixedHeight(179 if visible else 0)

        # Update selected card visibility (show only when suggestions are hidden)
        self._update_selected_card_visibility()

    def _update_selected_card_visibility(self):
        """Show selected card only when suggestions are hidden and researcher is selected."""
        suggestions_hidden = not self.researchers_list.isVisible()
        has_researcher = self._selected_researcher is not None

        # Show card only if has researcher AND suggestions are hidden
        should_show = has_researcher and suggestions_hidden

        if should_show:
            self._show_selected_card()
        else:
            self.selected_card.setVisible(False)

    def _show_selected_card(self):
        """Show selected buildings (exact copy from Step 1)."""
        if not self._selected_researcher:
            self.selected_card.setVisible(False)
            return

        # Clear existing content
        while self.selected_content_layout.count():
            item = self.selected_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        available = self._selected_researcher.get('available', True)

        # Update count label
        self.selected_count_label.setText(f"{len(self.selected_buildings)} بناء")

        # Update availability in header
        self.availability_value.setText("متوفر" if available else "غير متوفر")
        self.availability_value.setStyleSheet(f"color: {'#10B981' if available else '#EF4444'}; background: transparent;")

        # Add building rows (exact same as Step 1)
        for building in self.selected_buildings:
            self._create_building_row(building)

        # Show the card
        self.selected_card.setVisible(True)

    def _create_building_row(self, building):
        """Create building row (EXACT copy from Step 1 with checkbox)."""
        # === Checkbox with checkmark overlay (same as Step 1) ===
        checkbox_container = QWidget()
        checkbox_container.setFixedSize(20, 20)

        # Checkbox - border only - positioned at (0,0)
        checkbox = QCheckBox(checkbox_container)
        checkbox.setGeometry(0, 0, 20, 20)
        checkbox.setChecked(True)  # Already selected
        checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #3890DF;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: white;
                border-color: #3890DF;
            }
            QCheckBox::indicator:hover {
                border-color: #3890DF;
            }
        """)

        # Checkmark overlay (only visible when checked) - overlaid on top at (0,0)
        check_label = QLabel("✓", checkbox_container)
        check_label.setGeometry(0, 0, 20, 20)
        check_label.setStyleSheet("color: #3890DF; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        check_label.setAlignment(Qt.AlignCenter)
        check_label.setVisible(True)  # Visible by default (checked)
        # Make checkmark transparent to mouse clicks (so checkbox underneath can be clicked)
        check_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Update checkmark visibility when checkbox state changes
        checkbox.stateChanged.connect(lambda state: check_label.setVisible(state == Qt.Checked))

        # Create row container
        row = QWidget()
        row.setObjectName(f"row_{building.building_id}")
        row.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }
        """)
        row.setMinimumHeight(48)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 12, 0, 0)
        row_layout.setSpacing(16)

        row_layout.addWidget(checkbox_container)

        # === Icon in 32×32 square with #f0f7ff background ===
        icon_container = QLabel()
        icon_container.setFixedSize(32, 32)
        icon_container.setStyleSheet("""
            QLabel {
                background-color: #f0f7ff;
                border-radius: 6px;
            }
        """)
        icon_container.setAlignment(Qt.AlignCenter)

        # Try to load building-03 icon
        icon_pixmap = Icon.load_pixmap("building-03", size=20)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_container.setPixmap(icon_pixmap)
        else:
            icon_container.setText("🏢")
            icon_container.setStyleSheet("""
                QLabel {
                    background-color: #f0f7ff;
                    border-radius: 6px;
                    font-size: 16px;
                }
            """)
        row_layout.addWidget(icon_container)

        # === Building ID (formatted with dashes) ===
        formatted_id = self._format_building_id(building.building_id)
        id_label = QLabel(formatted_id)
        id_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        id_label.setStyleSheet(f"color: {Colors.PAGE_SUBTITLE}; background: transparent;")
        row_layout.addWidget(id_label)

        row_layout.addStretch()

        # Add row to table
        self.selected_content_layout.addWidget(row)

    def _format_building_id(self, building_id: str) -> str:
        """Format building ID with dashes (exact copy from Step 1)."""
        if not building_id:
            return ""

        if len(building_id) == 17:
            parts = [
                building_id[0:2],
                building_id[2:4],
                building_id[4:6],
                building_id[6:8],
                building_id[8:10],
                building_id[10:12],
                building_id[12:14],
                building_id[14:16],
                building_id[16:17]
            ]
            return "-".join(parts)

        return building_id

    def get_selected_researcher(self):
        """Get selected researcher info."""
        return self._selected_researcher
