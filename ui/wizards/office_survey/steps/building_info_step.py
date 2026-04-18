# -*- coding: utf-8 -*-
"""
Building Info Step - Step 0 of Office Survey Wizard.

Displays selected building data in read-only mode matching AddBuildingPage layout:
  Card 1 — بيانات البناء  (administrative location)
  Card 2 — حالة البناء   (status / units)
  Card 3 — موقع البناء   (map placeholder + docs + description)
"""

from datetime import datetime

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget,
    QLineEdit, QTextEdit, QScrollArea, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.wizard_styles import (
    STEP_CARD_STYLE, READONLY_FIELD_STYLE, SECTION_HEADER_STYLE,
    make_step_card, make_icon_header, make_divider, DIVIDER_COLOR,
)
from ui.design_system import Colors, ScreenScale
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.display_mappings import get_building_type_display, get_building_status_display
from services.translation_manager import tr, get_layout_direction
from services.api_client import get_api_client
from services.api_worker import ApiWorker
from utils.logger import get_logger

logger = get_logger(__name__)

_TEXTAREA_STYLE = """
    QTextEdit {
        background-color: #F8FAFF;
        border: 1px solid #dcdfe6;
        border-radius: 8px;
        padding: 8px 12px;
        color: #606266;
        font-size: 10pt;
    }
"""
# BuildingInfoStep

class BuildingInfoStep(BaseStep):
    """
    Step 0: Building Information (Read-Only).

    Three-card layout mirroring AddBuildingPage visual design.
    No user input — validation passes if context.building is set.
    """

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self._survey_api_service = get_api_client()
    # UI construction

    def setup_ui(self):
        self.main_layout.setContentsMargins(0, 4, 0, 16)
        self.main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + StyleManager.scrollbar()
        )

        content = QWidget()
        content.setStyleSheet("background: transparent;")

        outer_grid = QGridLayout(content)
        outer_grid.setContentsMargins(0, 0, 0, 0)
        outer_grid.setHorizontalSpacing(ScreenScale.w(12))
        outer_grid.setVerticalSpacing(ScreenScale.h(12))
        outer_grid.setColumnStretch(0, 1)
        outer_grid.setColumnStretch(1, 1)

        outer_grid.addWidget(self._build_merged_card(), 0, 0)
        outer_grid.addWidget(self._build_card3(), 0, 1)

        scroll.setWidget(content)
        self.main_layout.addWidget(scroll)

    # --- Merged card: بيانات + حالة البناء ----------------------------

    def _build_merged_card(self) -> QFrame:
        card = make_step_card()
        card.setMinimumWidth(ScreenScale.w(360))

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(ScreenScale.h(10))

        grid1 = self._add_card_section(
            layout,
            tr("wizard.building_info.card1_title"),
            tr("wizard.building_info.card1_subtitle"),
            "card1",
            columns=3,
        )
        self.lbl_governorate,  self.f_governorate  = self._add_grid_field(grid1, tr("wizard.building_info.governorate_code"),  0, 0)
        self.lbl_district,     self.f_district     = self._add_grid_field(grid1, tr("wizard.building_info.district_code"),     0, 1)
        self.lbl_subdistrict,  self.f_subdistrict  = self._add_grid_field(grid1, tr("wizard.building_info.subdistrict_code"),  0, 2)
        self.lbl_community,    self.f_community    = self._add_grid_field(grid1, tr("wizard.building_info.community_code"),    1, 0)
        self.lbl_neighborhood, self.f_neighborhood = self._add_grid_field(grid1, tr("wizard.building_info.neighborhood_code"), 1, 1)
        self.lbl_bldg_number,  self.f_bldg_number  = self._add_grid_field(grid1, tr("wizard.building_info.building_number"),   1, 2)
        self.lbl_bldg_code,    self.f_bldg_code    = self._add_grid_field(grid1, tr("wizard.building_info.building_code"),     2, 0, col_span=3)

        layout.addSpacing(ScreenScale.h(6))

        self.card2_title_lbl = QLabel(tr("wizard.building_info.card2_title"))
        self.card2_title_lbl.hide()
        self.card2_subtitle_lbl = QLabel()
        self.card2_subtitle_lbl.hide()

        grid2 = QGridLayout()
        grid2.setHorizontalSpacing(ScreenScale.w(10))
        grid2.setVerticalSpacing(ScreenScale.h(10))
        grid2.setContentsMargins(0, 0, 0, 0)
        grid2.setColumnStretch(0, 1)
        grid2.setColumnStretch(1, 1)
        layout.addLayout(grid2)
        self.lbl_status,     self.f_status     = self._add_grid_field(grid2, tr("wizard.building_info.building_status"),  0, 0)
        self.lbl_type,       self.f_type       = self._add_grid_field(grid2, tr("wizard.building_info.building_type"),    0, 1)
        self.lbl_apartments, self.f_apartments = self._add_grid_field(grid2, tr("wizard.building_info.apartments_count"), 1, 0)
        self.lbl_shops,      self.f_shops      = self._add_grid_field(grid2, tr("wizard.building_info.shops_count"),      1, 1)
        self.lbl_floors,     self.f_floors     = self._add_grid_field(grid2, tr("wizard.building_info.floors_count"),     2, 0)
        self.lbl_total,      self.f_total      = self._add_grid_field(grid2, tr("wizard.building_info.total_units"),      2, 1)

        return card

    def _add_card_section(self, parent_layout, title: str, subtitle: str, attr_prefix: str, columns: int = 2) -> QGridLayout:
        header_layout, title_lbl, subtitle_lbl = make_icon_header(title, subtitle, "blue")
        setattr(self, f"{attr_prefix}_title_lbl", title_lbl)
        setattr(self, f"{attr_prefix}_subtitle_lbl", subtitle_lbl)
        parent_layout.addLayout(header_layout)
        parent_layout.addWidget(make_divider())

        grid = QGridLayout()
        grid.setHorizontalSpacing(ScreenScale.w(10))
        grid.setVerticalSpacing(ScreenScale.h(10))
        grid.setContentsMargins(0, 0, 0, 0)
        for col in range(columns):
            grid.setColumnStretch(col, 1)
        parent_layout.addLayout(grid)
        return grid

    # --- Card 3: موقع البناء (mirrors AddBuildingPage Card 3) ----------

    def _build_card3(self) -> QFrame:
        from PyQt5.QtWidgets import QPushButton, QGraphicsDropShadowEffect
        from PyQt5.QtGui import QCursor, QIcon, QColor
        from PyQt5.QtCore import QSize
        from ui.components.icon import Icon

        card = make_step_card()
        card.setMinimumWidth(ScreenScale.w(360))

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(ScreenScale.h(10))

        header_layout, self._card3_header_lbl, self._card3_subtitle_lbl = make_icon_header(
            tr("wizard.building_info.card3_title"),
            "",
            "blue",
        )
        card_layout.addLayout(header_layout)
        card_layout.addWidget(make_divider())

        self._map_container = QLabel()
        self._map_container.setMinimumSize(ScreenScale.w(320), ScreenScale.h(200))
        self._map_container.setMaximumHeight(ScreenScale.h(280))
        self._map_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._map_container.setAlignment(Qt.AlignCenter)
        self._map_container.setObjectName("mapContainer")
        self._map_container.setStyleSheet("""
            QLabel#mapContainer {
                background-color: #E8E8E8;
                border-radius: 8px;
            }
        """)

        map_bg = Icon.load_pixmap("image-40", size=None)
        if not map_bg or map_bg.isNull():
            map_bg = Icon.load_pixmap("map-placeholder", size=None)
        if map_bg and not map_bg.isNull():
            self._map_container.setPixmap(
                map_bg.scaled(
                    ScreenScale.w(800), ScreenScale.h(220),
                    Qt.IgnoreAspectRatio, Qt.SmoothTransformation,
                )
            )

        loc_icon_lbl = QLabel(self._map_container)
        loc_px = Icon.load_pixmap("carbon_location-filled", size=48)
        if loc_px and not loc_px.isNull():
            loc_icon_lbl.setPixmap(loc_px)
            loc_icon_lbl.setFixedSize(ScreenScale.w(48), ScreenScale.h(48))
            loc_icon_lbl.move(ScreenScale.w(160), ScreenScale.h(80))
            loc_icon_lbl.setStyleSheet("background: transparent;")
        self._map_loc_icon = loc_icon_lbl

        map_button = QPushButton(self._map_container)
        map_button.setMinimumSize(ScreenScale.w(96), ScreenScale.h(24))
        map_button.move(ScreenScale.w(8), ScreenScale.h(8))
        map_button.setCursor(Qt.PointingHandCursor)
        pill_px = Icon.load_pixmap("pill", size=12)
        if pill_px and not pill_px.isNull():
            map_button.setIcon(QIcon(pill_px))
            map_button.setIconSize(QSize(12, 12))
        map_button.setText(tr("wizard.building_info.open_map"))
        map_button.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        map_button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 5px;
                padding: 4px 10px;
                text-align: center;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(map_button)
        shadow.setBlurRadius(8)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 60))
        map_button.setGraphicsEffect(shadow)
        map_button.clicked.connect(self._open_map_view)
        self._map_button = map_button

        card_layout.addWidget(self._map_container, stretch=1)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(ScreenScale.w(10))

        self.f_location_status = QLabel("")
        self.f_location_status.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.f_location_status.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent;"
        )
        self.f_location_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        meta_row.addWidget(self.f_location_status, stretch=1)

        self._docs_btn = QPushButton(tr("wizard.building_info.show_documents"))
        self._docs_btn.setMinimumHeight(ScreenScale.h(36))
        self._docs_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._docs_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._docs_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._docs_btn.setStyleSheet("""
            QPushButton {
                background-color: #F8FAFF;
                color: #3890DF;
                border: 1.5px solid #3890DF;
                border-radius: 8px;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #EBF5FF; }
            QPushButton:pressed { background-color: #D6ECFF; }
        """)
        self._docs_btn.clicked.connect(self._on_show_documents)
        meta_row.addWidget(self._docs_btn, stretch=0)
        card_layout.addLayout(meta_row)

        desc_lbl = QLabel(tr("wizard.building_info.description_label"))
        desc_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        desc_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        card_layout.addWidget(desc_lbl)
        self._desc_lbl = desc_lbl

        self.f_description = QTextEdit()
        self.f_description.setReadOnly(True)
        self.f_description.setMinimumHeight(ScreenScale.h(100))
        self.f_description.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.f_description.setStyleSheet(_TEXTAREA_STYLE)
        self.f_description.setPlaceholderText(tr("wizard.building_info.no_description"))
        card_layout.addWidget(self.f_description, stretch=1)

        return card
    # Reusable builders

    def _make_card_shell(self, title: str, subtitle: str, icon_name: str, columns: int):
        """
        Create a card frame with icon+title+subtitle header, divider, and QGridLayout.
        Returns (card_frame, grid_layout).
        """
        card = make_step_card()
        card.setMinimumWidth(ScreenScale.w(360))

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(ScreenScale.h(10))

        header_layout, title_lbl, subtitle_lbl = make_icon_header(title, subtitle, icon_name)
        layout.addLayout(header_layout)

        layout.addWidget(make_divider())

        grid = QGridLayout()
        grid.setHorizontalSpacing(ScreenScale.w(10))
        grid.setVerticalSpacing(ScreenScale.h(10))
        grid.setContentsMargins(0, 0, 0, 0)
        for col in range(columns):
            grid.setColumnStretch(col, 1)
        layout.addLayout(grid)

        return card, grid, title_lbl, subtitle_lbl


    # _make_icon_header is now shared via wizard_styles.make_icon_header

    @staticmethod
    def _add_grid_field(
        grid: QGridLayout,
        label_text: str,
        row: int,
        col: int,
        col_span: int = 1,
    ) -> QLineEdit:
        """Add label+QLineEdit to grid, return the QLineEdit."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        vbox.addWidget(lbl)

        field = QLineEdit()
        field.setReadOnly(True)
        field.setMinimumHeight(ScreenScale.h(36))
        field.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        field.setAlignment(Qt.AlignCenter)
        field.setStyleSheet(READONLY_FIELD_STYLE)
        vbox.addWidget(field)

        grid.addWidget(container, row, col, 1, col_span)
        return lbl, field
    # Data population

    def populate_data(self):
        b = self.context.building
        if not b:
            return

        def _s(attr: str, fallback: str = "") -> str:
            val = getattr(b, attr, None)
            return str(val) if val else fallback

        # Card 1
        self.f_governorate.setText(_s("governorate_name_ar") or _s("governorate_code"))
        self.f_district.setText(_s("district_name_ar") or _s("district_code"))
        self.f_subdistrict.setText(_s("subdistrict_name_ar") or _s("subdistrict_code"))
        self.f_community.setText(_s("community_name_ar") or _s("community_code"))
        self.f_neighborhood.setText(_s("neighborhood_name_ar") or _s("neighborhood_code"))

        bldg_id = _s("building_id")
        self.f_bldg_number.setText(bldg_id[-5:] if len(bldg_id) >= 5 else bldg_id)
        self.f_bldg_code.setText(
            _s("building_id_formatted") or _s("building_id_display") or bldg_id
        )

        # Card 2
        self.f_status.setText(
            get_building_status_display(getattr(b, "building_status", None)) or "—"
        )
        self.f_type.setText(
            get_building_type_display(getattr(b, "building_type", None)) or "—"
        )
        self.f_apartments.setText(str(getattr(b, "number_of_apartments", 0) or 0))
        self.f_shops.setText(str(getattr(b, "number_of_shops", 0) or 0))
        self.f_floors.setText(str(getattr(b, "number_of_floors", 0) or 0))
        self.f_total.setText(str(getattr(b, "number_of_units", 0) or 0))

        # Card 3 — location status
        lat = getattr(b, "latitude", None)
        lon = getattr(b, "longitude", None)
        if lat and lon:
            self.f_location_status.setText(f"{tr('wizard.building_info.coordinates')}: {lat:.6f}, {lon:.6f}")
        else:
            self.f_location_status.setText("")

        # Card 3 — description
        desc = (
            getattr(b, "general_description", None)
            or getattr(b, "location_description", None)
            or ""
        )
        self.f_description.setPlainText(desc)

    def _on_show_documents(self):
        """Fetch building documents from API (non-blocking) and show in dialog."""
        b = self.context.building
        if not b:
            return

        uuid = getattr(b, "building_uuid", None)
        if not uuid:
            from ui.components.toast import Toast
            Toast.show_toast(self, tr("wizard.building_info.no_building_uuid"), Toast.WARNING)
            return

        api = get_api_client()
        if not api:
            from ui.components.toast import Toast
            Toast.show_toast(self, tr("wizard.building_info.api_unavailable"), Toast.WARNING)
            return

        self._docs_btn.setEnabled(False)
        self._docs_btn.setText(tr("wizard.building_info.loading"))

        def _do_fetch():
            return api.get_building_documents(uuid)

        def _on_docs_loaded(docs):
            self._docs_btn.setEnabled(True)
            self._docs_btn.setText(tr("wizard.building_info.show_documents"))
            if not docs:
                from ui.components.toast import Toast
                Toast.show_toast(self, tr("wizard.building_info.no_attachments"), Toast.INFO)
                return
            self._show_documents_dialog(docs)

        def _on_docs_error(msg):
            self._docs_btn.setEnabled(True)
            self._docs_btn.setText(tr("wizard.building_info.show_documents"))
            logger.warning(f"Failed to load building documents: {msg}")
            from ui.components.toast import Toast
            Toast.show_toast(self, tr("wizard.building_info.load_docs_failed"), Toast.WARNING)

        self._docs_worker = ApiWorker(_do_fetch)
        self._docs_worker.finished.connect(_on_docs_loaded)
        self._docs_worker.error.connect(_on_docs_error)
        self._docs_worker.start()

    def _show_documents_dialog(self, docs: list):
        """Show building documents in a simple dialog."""
        from PyQt5.QtWidgets import QDialog, QScrollArea, QPushButton
        from PyQt5.QtGui import QCursor

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dlg.setFixedSize(ScreenScale.w(500), ScreenScale.h(400))
        dlg.setStyleSheet("""
            QDialog {
                background-color: white;
                border: 1px solid #dcdfe6;
                border-radius: 12px;
            }
        """)

        main_lay = QVBoxLayout(dlg)
        main_lay.setContentsMargins(20, 16, 20, 16)
        main_lay.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel(f"{tr('wizard.building_info.documents_dialog_title')} ({len(docs)})")
        title.setFont(create_font(size=12, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet(f"color: {Colors.WIZARD_TITLE};")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("X")
        close_btn.setFixedSize(ScreenScale.w(32), ScreenScale.h(32))
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        close_btn.setStyleSheet("""
            QPushButton {
                background: #f0f0f0; border: none; border-radius: 16px;
                font-size: 14px; font-weight: bold; color: #666;
            }
            QPushButton:hover { background: #e0e0e0; }
        """)
        close_btn.clicked.connect(dlg.close)
        header.addWidget(close_btn)
        main_lay.addLayout(header)

        # Docs list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        list_lay = QVBoxLayout(container)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(8)

        for doc in docs:
            row = self._make_doc_row(doc)
            list_lay.addWidget(row)

        list_lay.addStretch()
        scroll.setWidget(container)
        main_lay.addWidget(scroll)

        dlg.exec_()

    def _make_doc_row(self, doc: dict) -> QFrame:
        """Create a row widget for a single document."""
        row = QFrame()
        row.setFixedHeight(ScreenScale.h(50))
        row.setStyleSheet("""
            QFrame {
                background-color: #F8FAFF;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }
            QFrame:hover { border-color: #3890DF; background-color: #EBF5FF; }
        """)
        row.setCursor(Qt.PointingHandCursor)

        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(10)

        mime_type = doc.get("mimeType", "")
        file_name = doc.get("originalFileName", "") or tr("wizard.building_info.document_fallback")
        file_path = doc.get("filePath", "")

        icon_text = "IMG" if mime_type.startswith("image/") else "PDF" if "pdf" in mime_type else "DOC"
        icon_bg = "#DBEAFE" if mime_type.startswith("image/") else "#FEE2E2" if "pdf" in mime_type else "#E5E7EB"
        icon_fg = "#1D4ED8" if mime_type.startswith("image/") else "#DC2626" if "pdf" in mime_type else "#374151"

        icon_lbl = QLabel(icon_text)
        icon_lbl.setFixedSize(ScreenScale.w(36), ScreenScale.h(36))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFont(create_font(size=8, weight=FontManager.WEIGHT_SEMIBOLD))
        icon_lbl.setStyleSheet(
            f"background: {icon_bg}; color: {icon_fg}; border-radius: 6px; border: none;"
        )
        lay.addWidget(icon_lbl)

        name_lbl = QLabel(file_name)
        name_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        name_lbl.setStyleSheet("color: #303133; border: none; background: transparent;")
        lay.addWidget(name_lbl, stretch=1)

        row.mousePressEvent = lambda event, fp=file_path: self._open_doc_file(fp)
        return row

    def _open_doc_file(self, file_path: str):
        """Open document file if available."""
        if file_path:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
    # Map viewer

    def _open_map_view(self):
        """Open BuildingMapDialog in read-only mode to show the selected building."""
        b = self.context.building
        if not b:
            return
        try:
            from ui.components.building_map_dialog_v2 import BuildingMapDialog
            building_id = (
                getattr(b, "building_uuid", None)
                or getattr(b, "building_id", None)
            )
            dialog = BuildingMapDialog(
                db=self.context.db,
                selected_building_id=str(building_id) if building_id else None,
                read_only=True,
                selected_building=b,
                parent=self,
            )
            dialog.exec_()
        except Exception as e:
            logger.warning(f"Could not open map view: {e}")
    # BaseStep interface

    def validate(self) -> StepValidationResult:
        result = StepValidationResult(is_valid=True, errors=[])
        if not self.context.building:
            result.add_error(tr("wizard.building_info.no_building_selected"))
            return result

        building_uuid = getattr(self.context.building, 'building_uuid', '') or ''
        existing_survey_id = self.context.get_data("survey_id")
        previous_building_uuid = self.context.get_data("survey_building_uuid")

        # Survey already created for this building — skip
        if existing_survey_id and previous_building_uuid == building_uuid:
            return result

        # Building changed — reset old survey context
        if existing_survey_id and previous_building_uuid != building_uuid:
            logger.info(f"Building changed ({previous_building_uuid} -> {building_uuid}), cleaning up")
            try:
                self.context.cleanup_on_building_change(self._survey_api_service)
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}")
            for key in ("survey_id", "survey_data", "survey_building_uuid"):
                self.context.update_data(key, None)

        # Create survey via API
        self._set_auth_token()
        survey_data = {
            "building_uuid": building_uuid,
            "surveyDate": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "inPersonVisit": True,
        }
        logger.info(f"Creating office survey for building: {building_uuid}")
        try:
            survey_response = self._survey_api_service.create_office_survey(survey_data)
            survey_id = survey_response.get("id") or survey_response.get("surveyId", "")
            self.context.update_data("survey_id", survey_id)
            self.context.update_data("survey_data", survey_response)
            self.context.update_data("survey_building_uuid", building_uuid)
            logger.info(f"Survey created successfully, survey_id: {survey_id}")
        except Exception as e:
            logger.error(f"Survey creation failed: {e}")
            result.add_error(tr("wizard.building_info.survey_creation_failed"))

        return result

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())
        # Card 1 field labels
        self.card1_title_lbl.setText(tr("wizard.building_info.card1_title"))
        self.card1_subtitle_lbl.setText(tr("wizard.building_info.card1_subtitle"))
        self.lbl_governorate.setText(tr("wizard.building_info.governorate_code"))
        self.lbl_district.setText(tr("wizard.building_info.district_code"))
        self.lbl_subdistrict.setText(tr("wizard.building_info.subdistrict_code"))
        self.lbl_community.setText(tr("wizard.building_info.community_code"))
        self.lbl_neighborhood.setText(tr("wizard.building_info.neighborhood_code"))
        self.lbl_bldg_number.setText(tr("wizard.building_info.building_number"))
        self.lbl_bldg_code.setText(tr("wizard.building_info.building_code"))
        # Card 2 field labels
        self.card2_title_lbl.setText(tr("wizard.building_info.card2_title"))
        self.card2_subtitle_lbl.setText(tr("wizard.building_info.card2_subtitle"))
        self.lbl_status.setText(tr("wizard.building_info.building_status"))
        self.lbl_type.setText(tr("wizard.building_info.building_type"))
        self.lbl_apartments.setText(tr("wizard.building_info.apartments_count"))
        self.lbl_shops.setText(tr("wizard.building_info.shops_count"))
        self.lbl_floors.setText(tr("wizard.building_info.floors_count"))
        self.lbl_total.setText(tr("wizard.building_info.total_units"))
        # Card 3
        self._card3_header_lbl.setText(tr("wizard.building_info.card3_title"))
        self._docs_btn.setText(tr("wizard.building_info.show_documents"))
        self._desc_lbl.setText(tr("wizard.building_info.description_label"))
        self.f_description.setPlaceholderText(tr("wizard.building_info.no_description"))
        self._map_button.setText(tr("wizard.building_info.open_map"))

    def collect_data(self) -> dict:
        return {}

    def get_name(self) -> str:
        return tr("wizard.step.building_registration")
