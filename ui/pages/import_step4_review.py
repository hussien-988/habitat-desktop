# -*- coding: utf-8 -*-
"""Import wizard step 3: review staged entities before commit.

Used by the 3-step wizard as the Review & Approve pill's content.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from ui.components.empty_state import EmptyState
from ui.design_system import Colors, PageDimensions, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.translation_manager import tr, get_layout_direction, get_text_alignment
from utils.logger import get_logger
import re

logger = get_logger(__name__)


_BUILDING_TYPE_KEYS = {
    "residential": "wizard.import.step4.bldg_residential",
    "commercial": "wizard.import.step4.bldg_commercial",
    "mixed": "wizard.import.step4.bldg_mixed",
    "industrial": "wizard.import.step4.bldg_industrial",
    "public": "wizard.import.step4.bldg_public",
}

_UNIT_TYPE_KEYS = {
    "apartment": "wizard.import.step4.unit_apartment",
    "shop": "wizard.import.step4.unit_shop",
    "office": "wizard.import.step4.unit_office",
    "warehouse": "wizard.import.step4.unit_warehouse",
    "house": "wizard.import.step4.unit_house",
    "other": "wizard.import.step4.unit_other",
}


def _localize_building_display(value: str) -> str:
    """Translate strings like "Residential, 2 units" → "سكني، 2 وحدة"."""
    m = re.match(r"^([A-Za-z]+),\s*(\d+)\s+units?$", value.strip())
    if not m:
        return value
    type_word, count = m.group(1), m.group(2)
    type_key = _BUILDING_TYPE_KEYS.get(type_word.lower())
    type_ar = tr(type_key) if type_key else type_word
    units_ar = tr("wizard.import.step4.units_count", count=count)
    return f"{type_ar}، {units_ar}"


def _localize_unit_display(value: str) -> str:
    """Translate strings like "Apartment, Floor 3" → "شقة، طابق 3"."""
    m = re.match(r"^([A-Za-z]+),\s*Floor\s*(\d+)$", value.strip(), re.IGNORECASE)
    if not m:
        return value
    type_word, floor = m.group(1), m.group(2)
    type_key = _UNIT_TYPE_KEYS.get(type_word.lower())
    type_ar = tr(type_key) if type_key else type_word
    floor_ar = tr("wizard.import.step4.floor_label", floor=floor)
    return f"{type_ar}، {floor_ar}"


def _translate_display(entity_type: str, field: str, value: str) -> str:
    """Translate API display values to Arabic using vocab service."""
    if not value or value == "-":
        return value

    # Households: "Size: N" → "N أفراد"
    size_match = re.match(r"^Size:\s*(\d+)$", value, re.IGNORECASE)
    if size_match:
        return tr("wizard.import.step4.household_members", count=size_match.group(1))

    # Buildings: "Residential, 2 units" → "سكني، 2 وحدة"
    if entity_type == "buildings" and field == "displayInfo":
        return _localize_building_display(value)

    # Property units: "Apartment, Floor 3" → "شقة، طابق 3"
    if entity_type == "propertyUnits" and field == "displayInfo":
        return _localize_unit_display(value)

    # Use vocab service for known types
    if entity_type == "personPropertyRelations" and field == "displayInfo":
        from services.display_mappings import get_relation_type_display
        label = get_relation_type_display(value)
        if label and label != value:
            return label

    if entity_type == "claims" and field == "identifier":
        _claim_type_keys = {
            "Ownership": "wizard.import.step4.claim_ownership",
            "Tenancy": "wizard.import.step4.claim_tenancy",
            "Occupancy": "wizard.import.step4.claim_occupancy",
            "Inheritance": "wizard.import.step4.claim_inheritance",
            "Other": "wizard.import.step4.claim_other",
        }
        # Backend sometimes appends the "Claim" suffix (e.g. "OwnershipClaim").
        normalized = value[:-5] if value.endswith("Claim") else value
        key = _claim_type_keys.get(normalized)
        return tr(key) if key else value

    if entity_type == "claims" and field == "displayInfo":
        _collection_keys = {
            "FieldCollection": "wizard.import.step4.collection_field",
            "OfficeEntry": "wizard.import.step4.collection_office",
            "Import": "wizard.import.step4.collection_import",
            "Migration": "wizard.import.step4.collection_migration",
        }
        key = _collection_keys.get(value)
        return tr(key) if key else value

    return value

# Entity sections matching API response keys
_ENTITY_SECTION_KEYS = [
    ('surveys', 'wizard.import.entity.surveys', '#6366F1', '#EEF2FF'),
    ('buildings', 'wizard.import.entity.buildings', '#3890DF', '#EBF5FF'),
    ('propertyUnits', 'wizard.import.entity.property_units', '#10B981', '#ECFDF5'),
    ('persons', 'wizard.import.entity.persons', '#8B5CF6', '#F5F3FF'),
    ('households', 'wizard.import.entity.households', '#EC4899', '#FDF2F8'),
    ('personPropertyRelations', 'wizard.import.entity.person_property_relations', '#14B8A6', '#F0FDFA'),
    ('evidences', 'wizard.import.entity.evidences', '#F97316', '#FFF7ED'),
    ('claims', 'wizard.import.entity.claims', '#F59E0B', '#FFFBEB'),
]


def _get_entity_sections():
    return [(k, tr(tr_key), c, bg) for k, tr_key, c, bg in _ENTITY_SECTION_KEYS]

# Validation status display
_STATUS_CONFIG_KEYS = {
    'Valid': {'tr_key': 'wizard.import.step4.status_valid', 'color': '#10B981', 'bg': '#ECFDF5'},
    'Invalid': {'tr_key': 'wizard.import.step4.status_invalid', 'color': '#EF4444', 'bg': '#FEF2F2'},
    'Warning': {'tr_key': 'wizard.import.step4.status_warning', 'color': '#F59E0B', 'bg': '#FFFBEB'},
    'Pending': {'tr_key': 'wizard.import.step4.status_pending', 'color': '#9CA3AF', 'bg': '#F3F4F6'},
    'Skipped': {'tr_key': 'wizard.import.step4.status_skipped', 'color': '#6B7280', 'bg': '#F9FAFB'},
}

_DEFAULT_STATUS_KEY = {'tr_key': 'wizard.import.step4.status_unknown', 'color': '#9CA3AF', 'bg': '#F3F4F6'}


def _get_status_config(status_key):
    cfg = _STATUS_CONFIG_KEYS.get(status_key, _DEFAULT_STATUS_KEY)
    return {'label': tr(cfg['tr_key']), 'color': cfg['color'], 'bg': cfg['bg']}


class ImportStep4Review(QWidget):
    """Step 3 (Review): Review all staged entities before commit."""

    def __init__(self, import_controller, package_id, skip_load=False, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._package_id = package_id
        self._data = {}
        self._dots_count = 0
        self._setup_ui()
        self._loading_overlay = self._create_loading_overlay()
        if not skip_load:
            self.load_entities(package_id)

    def _setup_ui(self):
        self.setLayoutDirection(get_layout_direction())
        self.setStyleSheet("background: transparent;")

        # Two-card horizontal split. The viewport is wider than tall, so we
        # use the horizontal axis for the summary card on one side and the
        # entity table on the other — no page scroll needed.
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(
            ScreenScale.w(20), ScreenScale.h(16),
            ScreenScale.w(20), ScreenScale.h(16),
        )
        outer_layout.setSpacing(ScreenScale.w(16))

        # --- Card 1: Summary counts (LEFT, ~1/3 width) -----------------------
        summary_card = self._create_card()
        summary_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        summary_card.setMinimumWidth(ScreenScale.w(360))
        summary_card.setMaximumWidth(ScreenScale.w(460))
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(24, 20, 24, 20)
        summary_layout.setSpacing(12)

        self._summary_title = QLabel(tr("wizard.import.step4.title"))
        self._summary_title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        self._summary_title.setStyleSheet("color: #212B36; background: transparent;")
        summary_layout.addWidget(self._summary_title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        summary_layout.addWidget(sep)

        # Total count
        self._total_label = QLabel(tr("wizard.import.step4.total_entities", count=0))
        self._total_label.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._total_label.setStyleSheet("color: #212B36; background: transparent;")
        summary_layout.addWidget(self._total_label)

        # Count badges — stacked vertically in the narrow card.
        self._count_labels = {}
        self._count_name_labels = {}
        entity_sections = _get_entity_sections()
        for key, ar_name, color, bg in entity_sections:
            badge, count_label, name_label = self._create_count_badge(ar_name, "0", color, bg)
            self._count_labels[key] = count_label
            self._count_name_labels[key] = name_label
            summary_layout.addWidget(badge)
        summary_layout.addStretch()

        outer_layout.addWidget(summary_card, 1)

        # --- Card 2: Entities table (RIGHT, ~2/3 width) ----------------------
        table_card = self._create_card()
        table_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(24, 20, 24, 20)
        table_layout.setSpacing(12)

        self._table_title = QLabel(tr("wizard.import.step4.entity_details"))
        self._table_title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        self._table_title.setStyleSheet("color: #212B36; background: transparent;")
        table_layout.addWidget(self._table_title)

        # Empty state label
        self._empty_label = EmptyState(
            icon_name="save",
            title=tr("wizard.import.step4.no_staged_entities"),
        )
        self._empty_label.setMinimumHeight(ScreenScale.h(200))
        self._empty_label.setVisible(False)
        table_layout.addWidget(self._empty_label)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            tr("wizard.import.step4.col_type"),
            tr("wizard.import.step4.col_identifier"),
            tr("wizard.import.step4.col_description"),
            tr("wizard.import.step4.col_validation_status"),
            tr("wizard.import.step4.col_approved"),
        ])
        self._table.setLayoutDirection(get_layout_direction())
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Lock all columns: type/status/approved have fixed widths; identifier
        # and description stretch to fill remaining space. The header is no
        # longer interactively resizable.
        header = self._table.horizontalHeader()
        header.setSectionsMovable(False)
        header.setSectionsClickable(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self._table.setColumnWidth(0, ScreenScale.w(140))
        self._table.setColumnWidth(3, ScreenScale.w(120))
        self._table.setColumnWidth(4, ScreenScale.w(120))

        self._table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                gridline-color: #F4F6F8;
            }
            QTableWidget::item {
                padding: 8px 12px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #EFF6FF;
                color: #212B36;
            }
            QHeaderView::section {
                background-color: #F8F9FA;
                color: #637381;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid #E1E8ED;
                font-weight: 600;
            }
        """ + StyleManager.scrollbar())
        self._table.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        header.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))

        # Identifier column supports click-to-copy when the raw value is a
        # searchable key (national ID, building number, unit identifier,
        # survey reference, evidence file name).
        self._table.cellClicked.connect(self._on_cell_clicked)

        table_layout.addWidget(self._table, 1)

        outer_layout.addWidget(table_card, 2)

    def _create_card(self) -> QFrame:
        card = QFrame()
        # Scope the border to the card itself via objectName; otherwise the
        # `QFrame {...}` rule cascades onto every descendant QLabel (QLabel
        # inherits QFrame in Qt5) and paints stray rectangles around titles.
        card.setObjectName("importReviewCard")
        card.setStyleSheet("""
            QFrame#importReviewCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F7FAFF, stop:1 #F0F5FF);
                border-radius: 16px;
                border: 1px solid #E2EAF2;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 22))
        card.setGraphicsEffect(shadow)
        return card

    def _create_count_badge(self, label_text: str, count_text: str,
                            color: str, bg: str):
        """Create a summary count badge. Returns (container, count_label, name_label)."""
        container = QFrame()
        container.setFixedHeight(ScreenScale.h(50))
        container.setMinimumWidth(ScreenScale.w(130))
        container.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {bg}, stop:1 #FFFFFF);
                border-radius: 10px;
                border: none;
            }}
            QFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(12, 6, 12, 6)
        c_layout.setSpacing(8)

        count_label = QLabel(count_text)
        count_label.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        count_label.setStyleSheet(f"color: {color};")
        c_layout.addWidget(count_label)

        name_label = QLabel(label_text)
        name_label.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        name_label.setStyleSheet("color: #637381;")
        c_layout.addWidget(name_label)

        return container, count_label, name_label

    # -- Loading overlay -------------------------------------------------------

    def _create_loading_overlay(self) -> QFrame:
        overlay = QFrame(self)
        overlay.setStyleSheet("QFrame { background-color: rgba(255, 255, 255, 200); }")
        overlay.setVisible(False)

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedSize(ScreenScale.w(240), ScreenScale.h(90))
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 12px;
                border: 1px solid #E1E8ED;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(6)

        self._loading_label = QLabel(tr("wizard.import.step4.loading"))
        self._loading_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_SEMIBOLD))
        self._loading_label.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_label)

        self._loading_dots = QLabel("")
        self._loading_dots.setFont(create_font(size=14, weight=FontManager.WEIGHT_BOLD))
        self._loading_dots.setStyleSheet("color: #3890DF; background: transparent; border: none;")
        self._loading_dots.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self._loading_dots)

        overlay_layout.addWidget(card)

        self._dots_timer = QTimer(self)
        self._dots_timer.timeout.connect(self._animate_dots)

        return overlay

    def _show_loading(self, message: str):
        self._loading_label.setText(message)
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.raise_()
        self._loading_overlay.setVisible(True)
        self._dots_count = 0
        self._dots_timer.start(400)

    def _hide_loading(self):
        self._dots_timer.stop()
        self._loading_overlay.setVisible(False)

    def _animate_dots(self):
        self._dots_count = (self._dots_count + 1) % 4
        self._loading_dots.setText("." * self._dots_count)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    # -- Data loading ----------------------------------------------------------

    def load_entities(self, package_id: str):
        """Load staged entities from the controller (grouped response)."""
        logger.info(f"Loading staged entities for package {package_id}")
        self._package_id = package_id

        self._show_loading(tr("wizard.import.step4.loading_entities"))
        result = self.import_controller.get_staged_entities(package_id)
        self._hide_loading()

        if not result.success:
            logger.error(f"Failed to load entities: {result.message}")
            from ui.components.message_dialog import MessageDialog
            MessageDialog.error(self, tr("wizard.import.step4.error"), result.message_ar or tr("wizard.import.step4.entities_load_failed"))
            return

        self._data = result.data or {}
        self._update_ui()

    def _update_ui(self):
        """Update UI with grouped entity data."""
        d = self._data
        total = d.get("totalCount", 0)
        self._total_label.setText(tr("wizard.import.step4.total_entities", count=total))

        # Update count badges
        for key, _, _, _ in _ENTITY_SECTION_KEYS:
            section_items = d.get(key, [])
            count = len(section_items) if isinstance(section_items, list) else 0
            if key in self._count_labels:
                self._count_labels[key].setText(str(count))

        # Build per-package lookups so relations and claims can show readable
        # cross-referenced labels (person/unit, survey reference) instead of
        # bare GUIDs or untranslated enum names.
        self._build_lookups()

        # Flatten all entities for the table
        all_rows = []

        for key, ar_name, _, _ in _get_entity_sections():
            section_items = d.get(key, [])
            if not isinstance(section_items, list):
                continue
            for entity in section_items:
                all_rows.append((key, ar_name, entity))

        # Empty state
        if not all_rows:
            self._table.setVisible(False)
            self._empty_label.setVisible(True)
            return

        self._table.setVisible(True)
        self._empty_label.setVisible(False)

        self._table.setRowCount(len(all_rows))
        for row_idx, (type_key, type_name, entity) in enumerate(all_rows):
            raw_identifier = entity.get("identifier", "")
            display_info = entity.get("displayInfo", "")
            validation_status = entity.get("validationStatus", "Pending")
            is_approved = entity.get("isApprovedForCommit", False)

            # Build the user-facing identifier and decide whether it is a
            # useful search key (eligible for click-to-copy).
            identifier, copy_value = self._resolve_identifier(
                type_key, str(raw_identifier), entity
            )
            display_info = _translate_display(type_key, "displayInfo", str(display_info))

            # Type column
            type_item = QTableWidgetItem(type_name)
            type_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, 0, type_item)

            # Identifier column — stash the copy value in UserRole so
            # _on_cell_clicked can read it back without re-parsing the cell.
            id_item = QTableWidgetItem(str(identifier))
            id_item.setTextAlignment(get_text_alignment() | Qt.AlignVCenter)
            if copy_value:
                id_item.setData(Qt.UserRole, str(copy_value))
                id_item.setToolTip(
                    f"{copy_value}\n\n{tr('wizard.import.step4.copy_hint')}"
                )
            self._table.setItem(row_idx, 1, id_item)

            # Display info column
            info_item = QTableWidgetItem(str(display_info))
            info_item.setTextAlignment(get_text_alignment() | Qt.AlignVCenter)
            self._table.setItem(row_idx, 2, info_item)

            # Validation status column
            status_config = _get_status_config(validation_status)
            status_widget = self._create_status_badge(status_config)
            self._table.setCellWidget(row_idx, 3, status_widget)

            # Approved column
            approved_widget = self._create_approval_badge(is_approved)
            self._table.setCellWidget(row_idx, 4, approved_widget)

            self._table.setRowHeight(row_idx, 44)

    # -- Cross-reference lookups + identifier resolution ----------------------

    def _build_lookups(self):
        """Index persons / units / surveys so we can render readable
        identifiers for relations and claims.

        Each entity in the response is a wrapper carrying a top-level
        ``identifier`` (the backend's best-effort display string) plus the
        full DTO under ``stagingData`` / ``entityData``. We index by every
        plausible id key because the wrapper may expose ids at the top
        level or only inside the inner DTO."""
        d = self._data or {}

        self._persons_by_id = {}
        self._units_by_id = {}
        self._units_to_building_id = {}
        self._surveys_by_building_id = {}

        for p in d.get("persons") or []:
            inner = self._inner_dto(p)
            # Prefer displayInfo (full name) over identifier (national ID) so
            # relation rows show "خالد حسن الحسن / شقة 18" instead of
            # "64542116439 / شقة 18". Fall back to identifier when displayInfo
            # is empty (older packages may not carry it).
            person_label = p.get("displayInfo") or p.get("identifier") or ""
            for pid in self._collect_ids(p, inner, ("id", "personId")):
                self._persons_by_id[pid] = person_label

        for u in d.get("propertyUnits") or []:
            inner = self._inner_dto(u)
            for uid in self._collect_ids(u, inner, ("id", "propertyUnitId")):
                self._units_by_id[uid] = u.get("identifier") or ""
                bid = inner.get("buildingId") or inner.get("building_id")
                if bid:
                    self._units_to_building_id[uid] = str(bid)

        for s in d.get("surveys") or []:
            inner = self._inner_dto(s)
            ref = (
                inner.get("referenceCode")
                or inner.get("reference_code")
                or s.get("identifier")
                or ""
            )
            bid = inner.get("buildingId") or inner.get("building_id")
            if bid and ref:
                self._surveys_by_building_id[str(bid)] = str(ref)

    @staticmethod
    def _inner_dto(wrapper: dict) -> dict:
        """Return the inner DTO from a staged-entity wrapper, parsing JSON if
        the backend serialized it as a string."""
        payload = wrapper.get("stagingData") or wrapper.get("entityData") or {}
        if isinstance(payload, str):
            try:
                import json
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _collect_ids(wrapper: dict, inner: dict, keys: tuple) -> list:
        ids = []
        for src in (wrapper, inner):
            for k in keys:
                val = src.get(k)
                if val:
                    ids.append(str(val))
        # Also try originalEntityId / stagedEntityId on the wrapper itself.
        for extra_key in ("originalEntityId", "stagedEntityId", "entityId"):
            val = wrapper.get(extra_key)
            if val:
                ids.append(str(val))
        return ids

    def _resolve_identifier(self, type_key: str, raw_identifier: str,
                             entity: dict) -> tuple:
        """Return (display_text, copy_value).

        copy_value is the searchable identifier to write to clipboard on
        click — only set when the value is genuinely useful to search for
        (national ID, building number, unit identifier, survey reference,
        evidence filename). For composite displays (person/unit, claim type
        + owner) we leave copy_value empty."""
        # Relations: replace `{personId} → {propertyUnitId}` with names.
        if type_key == "personPropertyRelations":
            person_id, unit_id = self._extract_relation_ids(raw_identifier, entity)
            person_name = self._persons_by_id.get(person_id, "") if person_id else ""
            unit_name = self._units_by_id.get(unit_id, "") if unit_id else ""
            if person_name or unit_name:
                return (f"{person_name or '-'} / {unit_name or '-'}", "")
            # Fallback: keep the raw value visible if cross-reference fails.
            return (raw_identifier, "")

        # Claims: prefer the linked survey reference; fall back to "{type} — {owner}".
        if type_key == "claims":
            survey_ref = self._lookup_survey_ref_for_claim(entity)
            if survey_ref:
                return (survey_ref, survey_ref)
            type_translated = _translate_display(type_key, "identifier", raw_identifier)
            owner_name = self._lookup_claim_owner_name(entity)
            if owner_name:
                return (
                    tr("wizard.import.step4.claim_with_owner").format(
                        claim_type=type_translated, owner=owner_name
                    ),
                    "",
                )
            return (type_translated, "")

        # Default path for buildings / persons / units / households / surveys
        # / evidences: translate via the standard map. The raw identifier is
        # the searchable key for the first four types; households and
        # composite displays don't expose a useful search value.
        translated = _translate_display(type_key, "identifier", raw_identifier)
        searchable_types = {
            "buildings", "persons", "propertyUnits", "surveys", "evidences",
        }
        copy_value = raw_identifier if type_key in searchable_types else ""
        return (translated, copy_value)

    def _extract_relation_ids(self, raw_identifier: str, entity: dict) -> tuple:
        # The backend's identifier for a relation is "{personId} → {propertyUnitId}".
        if raw_identifier and "→" in raw_identifier:
            parts = [p.strip() for p in raw_identifier.split("→", 1)]
            if len(parts) == 2:
                return parts[0], parts[1]
        inner = self._inner_dto(entity)
        person_id = str(
            entity.get("personId")
            or inner.get("personId")
            or inner.get("person_id")
            or ""
        )
        unit_id = str(
            entity.get("propertyUnitId")
            or inner.get("propertyUnitId")
            or inner.get("property_unit_id")
            or ""
        )
        return person_id, unit_id

    def _lookup_survey_ref_for_claim(self, entity: dict) -> str:
        inner = self._inner_dto(entity)
        unit_id = str(
            entity.get("propertyUnitId")
            or inner.get("propertyUnitId")
            or inner.get("property_unit_id")
            or ""
        )
        if not unit_id:
            return ""
        building_id = self._units_to_building_id.get(unit_id)
        if not building_id:
            return ""
        return self._surveys_by_building_id.get(building_id, "")

    def _lookup_claim_owner_name(self, entity: dict) -> str:
        inner = self._inner_dto(entity)
        claimant_id = str(
            inner.get("primaryClaimantId")
            or inner.get("primary_claimant_id")
            or ""
        )
        if not claimant_id:
            return ""
        return self._persons_by_id.get(claimant_id, "")

    def _on_cell_clicked(self, row: int, col: int):
        """Copy the identifier to clipboard when the user clicks an
        identifier cell that carries a searchable value."""
        if col != 1:
            return
        item = self._table.item(row, col)
        if item is None:
            return
        copy_value = item.data(Qt.UserRole)
        if not copy_value:
            return
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(str(copy_value))
        try:
            from ui.components.toast import Toast
            Toast.show_toast(
                self, tr("wizard.import.step4.copied_to_clipboard"), Toast.SUCCESS
            )
        except Exception as exc:
            logger.warning(f"Toast on copy failed: {exc}")

    def _create_status_badge(self, config: dict) -> QWidget:
        """Create a validation status badge widget for table cell."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignCenter)

        badge = QLabel(config['label'])
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(26))
        badge.setMinimumWidth(ScreenScale.w(80))
        badge.setStyleSheet(f"""
            padding: 2px 12px;
            border-radius: 13px;
            color: {config['color']};
            background-color: {config['bg']};
        """)
        layout.addWidget(badge)
        return container

    def _create_approval_badge(self, is_approved: bool) -> QWidget:
        """Create an approval status badge."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setAlignment(Qt.AlignCenter)

        if is_approved:
            label = tr("wizard.import.step4.approved")
            color = "#10B981"
            bg = "#ECFDF5"
        else:
            label = tr("wizard.import.step4.not_approved")
            color = "#9CA3AF"
            bg = "#F3F4F6"

        badge = QLabel(label)
        badge.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(ScreenScale.h(26))
        badge.setMinimumWidth(ScreenScale.w(80))
        badge.setStyleSheet(f"""
            padding: 2px 12px;
            border-radius: 13px;
            color: {color};
            background-color: {bg};
        """)
        layout.addWidget(badge)
        return container

    def get_entities(self) -> dict:
        """Return the loaded grouped entities dict."""
        return self._data

    def reset(self):
        """Reset the step to initial state."""
        self._data = {}
        self._total_label.setText(tr("wizard.import.step4.total_entities", count=0))
        for label in self._count_labels.values():
            label.setText("0")
        self._table.setRowCount(0)
        self._table.setVisible(True)
        self._empty_label.setVisible(False)

    def update_language(self, is_arabic: bool):
        """Update all translatable texts after language change."""
        self.setLayoutDirection(get_layout_direction())

        # Card titles
        self._summary_title.setText(tr("wizard.import.step4.title"))
        self._table_title.setText(tr("wizard.import.step4.entity_details"))

        # Count badge entity names
        for key, ar_name, _, _ in _get_entity_sections():
            if key in self._count_name_labels:
                self._count_name_labels[key].setText(ar_name)

        # Total label
        total = self._data.get("totalCount", 0) if self._data else 0
        self._total_label.setText(tr("wizard.import.step4.total_entities", count=total))

        # Empty state label
        self._empty_label.set_title(tr("wizard.import.step4.no_staged_entities"))

        # Loading label
        self._loading_label.setText(tr("wizard.import.step4.loading"))

        # Table header labels
        self._table.setHorizontalHeaderLabels([
            tr("wizard.import.step4.col_type"),
            tr("wizard.import.step4.col_identifier"),
            tr("wizard.import.step4.col_description"),
            tr("wizard.import.step4.col_validation_status"),
            tr("wizard.import.step4.col_approved"),
        ])
        self._table.setLayoutDirection(get_layout_direction())

        # Re-populate table and count badges with updated translations
        if self._data:
            self._update_ui()
