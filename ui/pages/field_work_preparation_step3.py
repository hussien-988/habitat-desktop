# -*- coding: utf-8 -*-
"""Field work preparation step 3: review assignment before submission."""

from collections import deque
from datetime import date

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea
)
from PyQt5.QtCore import Qt, QTimer

from services.api_worker import ApiWorker
from services.translation_manager import tr, get_layout_direction
from ui.components.icon import Icon
from ui.components.toast import Toast
from ui.animation_utils import stagger_fade_in
from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.logger import get_logger

logger = get_logger(__name__)

def _get_unit_type_labels():
    return {
        1: tr("wizard.step3.unit_apartment"), 2: tr("wizard.step3.unit_shop"),
        3: tr("wizard.step3.unit_office"), 4: tr("wizard.step3.unit_warehouse"),
        5: tr("wizard.step3.unit_other"),
        "apartment": tr("wizard.step3.unit_apartment"), "shop": tr("wizard.step3.unit_shop"),
        "office": tr("wizard.step3.unit_office"), "warehouse": tr("wizard.step3.unit_warehouse"),
        "garage": tr("wizard.step3.unit_garage"), "other": tr("wizard.step3.unit_other"),
    }


class FieldWorkPreparationStep3(QWidget):
    """Review assignment with buildings, units, and visit type selection."""

    def __init__(self, buildings: list, researcher: dict,
                 revisit_unit_id=None, revisit_building_id=None,
                 parent=None):
        super().__init__(parent)
        self._ui_ready = False
        self._disposed = False
        self.buildings = buildings or []
        self.researcher = researcher or {}
        self._building_units = {}  # building_id -> units already fetched this step
        self._unit_uuids = {}  # building_id -> API UUID
        self._unit_count_badges = {}  # building_id -> QLabel
        self._accordion_bodies = {}  # building_id -> QWidget
        self._accordion_arrows = {}  # building_id -> QLabel
        self._units_labels = {}  # building_id -> QLabel (rendered units heading)
        self._unit_status_labels = {}  # building_id -> QLabel
        self._unit_retry_buttons = {}  # created only on failures
        self._unit_states = {}  # building_id -> idle/loading/ready/empty/error
        self._rendered_unit_ids = set()
        self._pending_unit_ids = deque()
        self._queued_unit_ids = set()
        self._active_unit_id = None
        self._active_unit_worker = None
        # Keep references while threads may still be running (QThread lifetime).
        self._unit_workers = []
        self._revisit_unit_id = revisit_unit_id
        self._revisit_building_id = revisit_building_id
        self._revisit_reason_input = None

        # Build only the building headers. Fetch each building's units on
        # expansion; the assignment payload does not depend on these details.
        from ui.components.loading_spinner import LoadingSpinnerOverlay
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._spinner = LoadingSpinnerOverlay(self, timeout_ms=120_000)
        self._spinner.show_loading(tr("wizard.step3.loading_summary"))
        # Let the wizard display this page before assembling 100 headers.
        QTimer.singleShot(0, self._finish_initial_ui)

    def dispose_unit_requests(self):
        """Discard queued GETs and UI updates after the page is replaced.

        An active HTTP request may finish, but its result must no longer
        update the discarded page or trigger the next queued request.
        """
        self._disposed = True
        self._pending_unit_ids.clear()
        self._queued_unit_ids.clear()

    def _finish_initial_ui(self):
        """Hide the initial spinner only after the summary is constructed."""
        if self._disposed:
            return
        try:
            self._setup_ui()
            self._ui_ready = True
        except Exception:
            logger.exception("Could not construct fieldwork summary")
            Toast.show_toast(self, tr("wizard.step3.err_load_summary"), Toast.ERROR)
        finally:
            self._spinner.hide_loading()

    @staticmethod
    def _fetch_single_building_units(building_uuid):
        """Fetch one building's units off the GUI thread."""
        from services.api_client import get_api_client
        result = get_api_client().get_assignment_property_units(building_uuid)
        if result is None:
            return []
        if not isinstance(result, list):
            raise ValueError("Unexpected property-units response type")
        return result

    def _queue_unit_fetch(self, building_id):
        """Queue at most one request per building, using one API worker at a time.

        The API client shares a requests.Session, so issuing many concurrent
        requests against that client could introduce thread-safety problems.
        """
        if self._disposed:
            return
        if (building_id in self._building_units
                or building_id in self._queued_unit_ids
                or building_id == self._active_unit_id):
            return
        if not self._unit_uuids.get(building_id):
            self._set_unit_state(building_id, "error")
            return
        self._unit_states[building_id] = "loading"
        self._set_unit_state(building_id, "loading")
        self._pending_unit_ids.append(building_id)
        self._queued_unit_ids.add(building_id)
        self._process_unit_queue()

    def _process_unit_queue(self):
        """Run one queued request; completed workers unlock the next."""
        if self._disposed:
            return
        if self._active_unit_id is not None:
            return
        # The ApiWorker data signal is emitted just before its QThread exits.
        # Do not start a second request using the shared session until it has
        # actually stopped, even if the previous result was already delivered.
        if self._active_unit_worker is not None:
            if self._active_unit_worker.isRunning():
                QTimer.singleShot(25, self._process_unit_queue)
                return
            self._active_unit_worker = None
        while self._pending_unit_ids:
            building_id = self._pending_unit_ids.popleft()
            self._queued_unit_ids.discard(building_id)
            if building_id in self._building_units:
                continue
            self._active_unit_id = building_id
            worker = ApiWorker(
                self._fetch_single_building_units, self._unit_uuids[building_id]
            )
            self._unit_workers.append(worker)
            self._active_unit_worker = worker
            worker.finished.connect(
                lambda units, bid=building_id:
                self._on_single_units_loaded(bid, units)
            )
            worker.error.connect(
                lambda message, bid=building_id:
                self._on_single_units_error(bid, message)
            )
            worker.start()
            return

    def _on_single_units_loaded(self, building_id, units):
        """Cache the result; render cards only if this accordion is open."""
        if self._disposed:
            return
        self._building_units[building_id] = units
        badge = self._unit_count_badges.get(building_id)
        if badge is not None:
            badge.setText(tr("wizard.step3.units_count", count=len(units)))
            badge.show()
        self._set_unit_state(building_id, "ready" if units else "empty")
        body = self._accordion_bodies.get(building_id)
        if body is not None and body.isVisible():
            self._render_units_if_needed(building_id)
        self._finish_unit_request(building_id)

    def _on_single_units_error(self, building_id, message):
        if self._disposed:
            return
        self._set_unit_state(building_id, "error")
        self._finish_unit_request(building_id)

    def _finish_unit_request(self, building_id):
        if self._active_unit_id == building_id:
            self._active_unit_id = None
        # Defer the next request to avoid overlapping use of the shared
        # requests.Session while the previous QThread is still returning.
        QTimer.singleShot(0, self._process_unit_queue)

    def _set_unit_state(self, building_id, state):
        """Update per-accordion loading/error/empty feedback."""
        self._unit_states[building_id] = state
        label = self._unit_status_labels.get(building_id)
        if label is None:
            return
        key_by_state = {
            "loading": "wizard.step3.loading_units",
            "empty": "wizard.step3.no_units",
            "error": "wizard.step3.units_load_failed",
        }
        key = key_by_state.get(state)
        label.setText(tr(key) if key else "")
        label.setVisible(bool(key))

        retry = self._unit_retry_buttons.get(building_id)
        if state == "error" and retry is None:
            from PyQt5.QtWidgets import QPushButton
            retry = QPushButton(tr("wizard.step3.retry_units"))
            retry.setCursor(Qt.PointingHandCursor)
            retry.clicked.connect(
                lambda _checked=False, bid=building_id: self._queue_unit_fetch(bid)
            )
            self._accordion_bodies[building_id].layout().addWidget(retry)
            self._unit_retry_buttons[building_id] = retry
        if retry is not None:
            retry.setVisible(state == "error")

    def _render_units_if_needed(self, building_id):
        """Create unit widgets at most once for each expanded building."""
        if building_id in self._rendered_unit_ids:
            return
        units = self._building_units.get(building_id)
        if not units:
            return
        body = self._accordion_bodies.get(building_id)
        if body is None:
            return
        layout = body.layout()
        units_label = QLabel(tr("wizard.step3.units_label"))
        units_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        units_label.setStyleSheet("color: #4B5563; background: transparent; border: none;")
        layout.addWidget(units_label)
        self._units_labels[building_id] = units_label
        for unit in units:
            layout.addWidget(self._create_unit_card(unit))
        self._rendered_unit_ids.add(building_id)

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())

        outer = self._outer_layout
        outer.setSpacing(0)

        # Page-level scroll — the whole step scrolls, not individual cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(0, ScreenScale.h(24), 0, 0)
        layout.setSpacing(ScreenScale.h(16))
        info_card = QFrame()
        info_card.setStyleSheet(StyleManager.data_card())
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(
            ScreenScale.w(24), ScreenScale.h(20),
            ScreenScale.w(24), ScreenScale.h(20),
        )
        info_layout.setSpacing(ScreenScale.h(12))

        self._info_title_label = QLabel(tr("wizard.step3.assignment_info"))
        self._info_title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._info_title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        info_layout.addWidget(self._info_title_label)

        researcher_name = (
            self.researcher.get('name')
            or self.researcher.get('display_name')
            or self.researcher.get('id', '')
        )
        assignment_date = date.today().strftime("%Y-%m-%d")

        self._info_row_labels = []
        self._info_row_values = []
        self._avail_badge = None

        for label_text, value_text, value_color in [
            (tr("wizard.step3.field_researcher"), researcher_name, Colors.PAGE_TITLE),
            (tr("wizard.step3.building_count"), str(len(self.buildings)), Colors.PRIMARY_BLUE),
            (tr("wizard.step3.assignment_date"), assignment_date, Colors.PAGE_TITLE),
        ]:
            row = QHBoxLayout()
            row.setSpacing(ScreenScale.w(12))

            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet("color: #4B5563; background: transparent; border: none;")
            lbl.setFixedWidth(ScreenScale.w(160))
            row.addWidget(lbl)
            self._info_row_labels.append(lbl)

            val = QLabel(value_text)
            val.setFont(create_font(size=10, weight=FontManager.WEIGHT_MEDIUM))
            val.setStyleSheet(f"color: {value_color}; background: transparent; border: none;")
            row.addWidget(val)
            self._info_row_values.append(val)

            row.addStretch()
            info_layout.addLayout(row)

        layout.addWidget(info_card)
        buildings_card = QFrame()
        buildings_card.setStyleSheet(StyleManager.data_card())
        buildings_card_layout = QVBoxLayout(buildings_card)
        buildings_card_layout.setContentsMargins(
            ScreenScale.w(24), ScreenScale.h(16),
            ScreenScale.w(24), ScreenScale.h(16),
        )
        buildings_card_layout.setSpacing(ScreenScale.h(6))

        self._buildings_title_label = QLabel(tr("wizard.step3.buildings_and_units"))
        self._buildings_title_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._buildings_title_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        buildings_card_layout.addWidget(self._buildings_title_label)
        buildings_card_layout.addSpacing(ScreenScale.h(6))

        for i, building in enumerate(self.buildings):
            building_id = (
                getattr(building, 'building_id', None)
                or getattr(building, 'id', None)
                or str(building)
            )
            accordion = self._create_accordion_item(i + 1, building, building_id)
            buildings_card_layout.addWidget(accordion)

        layout.addWidget(buildings_card)

        if self._revisit_unit_id:
            reason_card = self._create_revisit_reason_card()
            layout.addWidget(reason_card)

        layout.addStretch()

        scroll.setWidget(scroll_content)
        outer.addWidget(scroll)

        stagger_fade_in([info_card, buildings_card])

    def _create_accordion_item(self, index, building, building_id):
        """Create an accordion item for a building."""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background: transparent;
                border: 1px solid #F0F0F0;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #FAFBFC;
                border: none;
                border-radius: 8px;
            }
            QFrame:hover {
                background-color: #F0F4F8;
            }
        """)
        header.setCursor(Qt.PointingHandCursor)
        header.setFixedHeight(ScreenScale.h(52))

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(ScreenScale.w(16), 0, ScreenScale.w(16), 0)
        header_layout.setSpacing(ScreenScale.w(12))

        # Arrow
        arrow = QLabel("\u25B6")
        arrow.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        arrow.setStyleSheet("color: #637381; background: transparent; border: none;")
        arrow.setFixedWidth(ScreenScale.w(16))
        self._accordion_arrows[building_id] = arrow
        header_layout.addWidget(arrow)

        # Building icon
        icon_container = QLabel()
        icon_container.setFixedSize(ScreenScale.w(28), ScreenScale.h(28))
        icon_container.setStyleSheet(
            "QLabel { background-color: #f0f7ff; border-radius: 6px; border: none; }"
        )
        icon_container.setAlignment(Qt.AlignCenter)
        icon_pixmap = Icon.load_pixmap("building-03", size=16)
        if icon_pixmap and not icon_pixmap.isNull():
            icon_container.setPixmap(icon_pixmap)
        else:
            icon_container.setText("B")
        header_layout.addWidget(icon_container)

        # Building ID
        display_id = self._format_building_id(building_id)
        id_label = QLabel(f"{index}. {display_id}")
        id_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        id_label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        header_layout.addWidget(id_label)

        header_layout.addStretch()

        # Units are loaded only when this building is expanded.
        self._unit_uuids[building_id] = (
            getattr(building, 'building_uuid', None)
            or getattr(building, 'id', None)
        )
        self._unit_states[building_id] = "idle"

        # Before expansion, show the count already known from the building.
        num_units = getattr(building, 'number_of_units', 0) or 0
        badge = QLabel(tr("wizard.step3.units_count", count=num_units) if num_units > 0 else "")
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setStyleSheet(f"""
            color: {Colors.PRIMARY_BLUE};
            background-color: #EBF5FF;
            padding: 2px 10px;
            border-radius: 10px;
            border: none;
        """)
        # Keep the badge in the layout even when the initial count is unknown.
        header_layout.addWidget(badge)
        badge.setVisible(bool(badge.text()))
        self._unit_count_badges[building_id] = badge

        container_layout.addWidget(header)
        body = QWidget()
        body.setStyleSheet("background: transparent; border: none;")
        body.setVisible(False)
        self._accordion_bodies[building_id] = body

        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(44, 8, 16, 12)
        body_layout.setSpacing(10)

        status_label = QLabel("")
        status_label.setWordWrap(True)
        status_label.setStyleSheet("color: #4B5563; background: transparent; border: none;")
        status_label.hide()
        self._unit_status_labels[building_id] = status_label
        body_layout.addWidget(status_label)

        container_layout.addWidget(body)

        # Click handler for header
        header.mousePressEvent = lambda event, bid=building_id: self._toggle_accordion(bid)

        return container

    def _create_unit_card(self, unit_data: dict) -> QFrame:
        """Create a read-only unit card with survey status badge."""
        unit_type = unit_data.get('unitType') or unit_data.get('unit_type') or 'other'
        try:
            unit_type = int(unit_type)
        except (ValueError, TypeError):
            pass
        lookup_key = unit_type if isinstance(unit_type, int) else str(unit_type).lower()
        ar_type = _get_unit_type_labels().get(lookup_key, str(unit_type))

        unit_code = unit_data.get('unitCode') or unit_data.get('unit_code') or '-'
        floor = unit_data.get('floorNumber')
        floor_str = str(floor) if floor is not None else '-'
        person_count = unit_data.get('personCount') or 0
        household_count = unit_data.get('householdCount') or 0
        claim_count = unit_data.get('claimCount') or 0
        has_survey = unit_data.get('hasCompletedSurvey', False)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E8EDF2;
                border-radius: 8px;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            ScreenScale.w(12), ScreenScale.h(8),
            ScreenScale.w(12), ScreenScale.h(8),
        )
        card_layout.setSpacing(ScreenScale.h(6))

        # Survey status badge row
        status_row = QHBoxLayout()
        status_row.setSpacing(ScreenScale.w(6))
        if has_survey:
            status_badge = QLabel(tr("wizard.step3.survey_done"))
            status_badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            status_badge.setStyleSheet("""
                color: #10B981;
                background-color: #ECFDF5;
                padding: 2px 8px;
                border-radius: 8px;
            """)
        else:
            status_badge = QLabel(tr("wizard.step3.survey_not_done"))
            status_badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
            status_badge.setStyleSheet("""
                color: #F59E0B;
                background-color: #FFFBEB;
                padding: 2px 8px;
                border-radius: 8px;
            """)
        status_row.addWidget(status_badge)
        status_row.addStretch()
        card_layout.addLayout(status_row)

        # Data grid
        grid = QHBoxLayout()
        grid.setSpacing(0)

        data_points = [
            (tr("wizard.step3.unit_code"), unit_code),
            (tr("wizard.step3.floor"), floor_str),
            (tr("wizard.step3.type"), ar_type),
            (tr("wizard.step3.persons"), str(person_count)),
            (tr("wizard.step3.households"), str(household_count)),
            (tr("wizard.step3.claims"), str(claim_count)),
        ]

        for i, (label_text, value_text) in enumerate(data_points):
            col = QVBoxLayout()
            col.setSpacing(ScreenScale.h(2))
            col.setContentsMargins(ScreenScale.w(6), 0, ScreenScale.w(6), 0)
            col.setAlignment(Qt.AlignCenter)

            lbl = QLabel(label_text)
            lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            lbl.setStyleSheet("color: #4B5563;")
            lbl.setAlignment(Qt.AlignCenter)
            col.addWidget(lbl)

            val = QLabel(value_text)
            val.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
            val.setStyleSheet(f"color: {Colors.PAGE_TITLE};")
            val.setAlignment(Qt.AlignCenter)
            col.addWidget(val)

            grid.addLayout(col, stretch=1)

            if i < len(data_points) - 1:
                sep = QFrame()
                sep.setFixedWidth(1)
                sep.setFixedHeight(ScreenScale.h(34))
                sep.setStyleSheet("background-color: #E5E7EB; border: none;")
                grid.addWidget(sep)

        card_layout.addLayout(grid)

        return card

    def _toggle_accordion(self, building_id):
        """Toggle accordion expand/collapse."""
        body = self._accordion_bodies.get(building_id)
        arrow = self._accordion_arrows.get(building_id)
        if body is None:
            return

        is_visible = body.isVisible()
        body.setVisible(not is_visible)

        if arrow:
            arrow.setText("\u25BC" if not is_visible else "\u25B6")

        if not is_visible:
            if building_id in self._building_units:
                self._render_units_if_needed(building_id)
            elif self._unit_states.get(building_id) == "idle":
                self._queue_unit_fetch(building_id)

    def _format_building_id(self, building_id: str) -> str:
        """Format building ID with dashes: GG-DD-SS-CCC-NNN-BBBBB."""
        if not building_id:
            return ""
        clean = str(building_id).replace("-", "")
        if len(clean) == 17:
            return (
                f"{clean[0:2]}-{clean[2:4]}-{clean[4:6]}-"
                f"{clean[6:9]}-{clean[9:12]}-{clean[12:17]}"
            )
        return building_id

    def _create_revisit_reason_card(self) -> QFrame:
        """Create a card with a required reason input for revisit mode."""
        from PyQt5.QtWidgets import QLineEdit
        reason_card = QFrame()
        reason_card.setStyleSheet(StyleManager.data_card())
        reason_layout = QVBoxLayout(reason_card)
        reason_layout.setContentsMargins(
            ScreenScale.w(24), ScreenScale.h(16),
            ScreenScale.w(24), ScreenScale.h(16),
        )
        reason_layout.setSpacing(ScreenScale.h(8))

        label = QLabel(tr("wizard.step3.revisit_reason_label") + " *")
        label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        label.setStyleSheet(f"color: {Colors.PAGE_TITLE}; background: transparent; border: none;")
        reason_layout.addWidget(label)
        self._revisit_reason_label = label

        self._revisit_reason_input = QLineEdit()
        self._revisit_reason_input.setFont(create_font(size=11))
        self._revisit_reason_input.setFixedHeight(ScreenScale.h(38))
        self._revisit_reason_input.setPlaceholderText(
            tr("wizard.step3.revisit_reason_placeholder")
        )
        self._revisit_reason_input.setStyleSheet("""
            QLineEdit {
                background: #F8FAFC;
                border: 1.5px solid #E2E8F0;
                border-radius: 10px;
                padding: 0 12px;
                color: #1E293B;
            }
            QLineEdit:focus {
                border-color: #3890DF;
            }
        """)
        reason_layout.addWidget(self._revisit_reason_input)
        return reason_card

    def update_language(self, is_arabic: bool = True):
        """Update UI text after language change."""
        self.setLayoutDirection(get_layout_direction())

        # Update info card title
        if hasattr(self, '_info_title_label'):
            self._info_title_label.setText(tr("wizard.step3.assignment_info"))

        # Update info row labels (researcher, building count, date)
        if hasattr(self, '_info_row_labels') and len(self._info_row_labels) >= 3:
            self._info_row_labels[0].setText(tr("wizard.step3.field_researcher"))
            self._info_row_labels[1].setText(tr("wizard.step3.building_count"))
            self._info_row_labels[2].setText(tr("wizard.step3.assignment_date"))

        # Update researcher name on language change
        if hasattr(self, '_info_row_values') and self._info_row_values:
            researcher_name = (
                self.researcher.get('name')
                or self.researcher.get('display_name')
                or self.researcher.get('id', '')
            )
            self._info_row_values[0].setText(researcher_name)

        # Update buildings card title
        if hasattr(self, '_buildings_title_label'):
            self._buildings_title_label.setText(tr("wizard.step3.buildings_and_units"))

        for building_id in self._units_labels:
            self._units_labels[building_id].setText(tr("wizard.step3.units_label"))
        # Re-translate feedback for in-flight and completed unit fetches.
        for building_id, state in list(self._unit_states.items()):
            if state in ("loading", "empty", "error"):
                self._set_unit_state(building_id, state)
        for retry in self._unit_retry_buttons.values():
            retry.setText(tr("wizard.step3.retry_units"))

        if hasattr(self, '_revisit_reason_label') and self._revisit_reason_label:
            self._revisit_reason_label.setText(tr("wizard.step3.revisit_reason_label") + " *")
        if hasattr(self, '_revisit_reason_input') and self._revisit_reason_input:
            self._revisit_reason_input.setPlaceholderText(tr("wizard.step3.revisit_reason_placeholder"))

    def validate(self) -> bool:
        # The UI is scheduled for the next Qt event-loop turn; never submit
        # before the revisit reason field and building summary are ready.
        if not self._ui_ready:
            return False
        # Avoid starting the assignment POST while this step is using the
        # shared API client's session for a unit-details GET.
        worker_busy = (self._active_unit_worker is not None
                       and self._active_unit_worker.isRunning())
        if worker_busy or self._pending_unit_ids:
            Toast.show_toast(self, tr("wizard.step3.wait_for_units"), Toast.WARNING)
            return False
        if self._revisit_unit_id and self._revisit_reason_input is not None:
            if not self._revisit_reason_input.text().strip():
                Toast.show_toast(self, tr("wizard.step3.revisit_reason_required"), Toast.WARNING)
                return False
        return True

    def get_summary(self) -> dict:
        summary = {
            'buildings': self.buildings,
            'researcher': self.researcher,
        }
        if (self._revisit_unit_id and self._revisit_building_id
                and self._revisit_reason_input is not None):
            reason = self._revisit_reason_input.text().strip()
            if reason:
                summary['revisit_reasons'] = {self._revisit_building_id: reason}
        return summary
