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
    QLineEdit, QTextEdit, QScrollArea, QGridLayout
)
from PyQt5.QtCore import Qt

from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from services.display_mappings import get_building_type_display, get_building_status_display
from services.translation_manager import tr
from services.api_client import get_api_client
from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared styles (DRY — mirrors AddBuildingPage._get_card_style / field style)
# ---------------------------------------------------------------------------

_CARD_STYLE = """
    QFrame {
        background-color: white;
        border: 1px solid #e1e8ee;
        border-radius: 8px;
    }
    QLabel { border: none; }
"""

_FIELD_STYLE = """
    QLineEdit {
        background-color: #F8FAFF;
        border: 1px solid #dcdfe6;
        border-radius: 8px;
        padding: 8px 12px;
        color: #606266;
        font-size: 10pt;
    }
"""

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


# ---------------------------------------------------------------------------
# BuildingInfoStep
# ---------------------------------------------------------------------------

class BuildingInfoStep(BaseStep):
    """
    Step 0: Building Information (Read-Only).

    Three-card layout mirroring AddBuildingPage visual design.
    No user input — validation passes if context.building is set.
    """

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self._survey_api_service = get_api_client()
        self._use_api = getattr(Config, 'DATA_PROVIDER', 'local_db') == 'http'

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

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
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(12)

        vbox.addWidget(self._build_card1())
        vbox.addWidget(self._build_card2())
        vbox.addWidget(self._build_card3())
        vbox.addStretch()

        scroll.setWidget(content)
        self.main_layout.addWidget(scroll)

    # --- Card 1: بيانات البناء ----------------------------------------

    def _build_card1(self) -> QFrame:
        card, grid = self._make_card_shell(
            title="بيانات البناء",
            subtitle="معلومات الموقع الإداري للبناء",
            icon_name="blue",
            columns=3,
        )
        self.f_governorate  = self._add_grid_field(grid, "رمز المحافظة", 0, 0)
        self.f_district     = self._add_grid_field(grid, "رمز المنطقة",  0, 1)
        self.f_subdistrict  = self._add_grid_field(grid, "رمز الناحية",  0, 2)
        self.f_community    = self._add_grid_field(grid, "رمز المدينة",  1, 0)
        self.f_neighborhood = self._add_grid_field(grid, "رمز الحي",     1, 1)
        self.f_bldg_number  = self._add_grid_field(grid, "رقم البناء",   1, 2)
        self.f_bldg_code    = self._add_grid_field(grid, "رمز البناء",   2, 0, col_span=3)
        return card

    # --- Card 2: حالة البناء ------------------------------------------

    def _build_card2(self) -> QFrame:
        card, grid = self._make_card_shell(
            title="حالة البناء",
            subtitle="معلومات حالة البناء والمقاسم",
            icon_name="blue",
            columns=3,
        )
        self.f_status     = self._add_grid_field(grid, "حالة البناء",         0, 0)
        self.f_type       = self._add_grid_field(grid, "نوع البناء",          0, 1)
        self.f_apartments = self._add_grid_field(grid, "عدد الشقق",           0, 2)
        self.f_shops      = self._add_grid_field(grid, "عدد المحلات",         1, 0)
        self.f_floors     = self._add_grid_field(grid, "عدد الطوابق",         1, 1)
        self.f_total      = self._add_grid_field(grid, "العدد الكلي للمقاسم", 1, 2)
        return card

    # --- Card 3: موقع البناء (mirrors AddBuildingPage Card 3) ----------

    def _build_card3(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(_CARD_STYLE)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(0)

        # Simple text header — matches AddBuildingPage Card 3 exactly
        header = QLabel("موقع البناء")
        header.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        header.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        card_layout.addWidget(header)
        card_layout.addSpacing(12)

        content_row = QHBoxLayout()
        content_row.setSpacing(24)

        # --- Section 1: Map placeholder ---
        map_section = QVBoxLayout()
        map_section.setSpacing(4)

        map_align_lbl = QLabel("")
        map_align_lbl.setFixedHeight(16)
        map_section.addWidget(map_align_lbl)

        self._map_container = QLabel()
        self._map_container.setFixedSize(400, 130)
        self._map_container.setAlignment(Qt.AlignCenter)
        self._map_container.setObjectName("mapContainer")
        self._map_container.setStyleSheet("""
            QLabel#mapContainer {
                background-color: #E8E8E8;
                border-radius: 8px;
            }
        """)

        from ui.components.icon import Icon
        map_bg = Icon.load_pixmap("image-40", size=None)
        if not map_bg or map_bg.isNull():
            map_bg = Icon.load_pixmap("map-placeholder", size=None)
        if map_bg and not map_bg.isNull():
            self._map_container.setPixmap(
                map_bg.scaled(400, 130, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            )

        loc_icon_lbl = QLabel(self._map_container)
        loc_px = Icon.load_pixmap("carbon_location-filled", size=56)
        if loc_px and not loc_px.isNull():
            loc_icon_lbl.setPixmap(loc_px)
            loc_icon_lbl.setFixedSize(56, 56)
            loc_icon_lbl.move(172, 37)
            loc_icon_lbl.setStyleSheet("background: transparent;")

        from PyQt5.QtWidgets import QPushButton
        from PyQt5.QtGui import QIcon
        from PyQt5.QtCore import QSize
        map_button = QPushButton(self._map_container)
        map_button.setFixedSize(94, 20)
        map_button.move(8, 8)
        map_button.setCursor(Qt.PointingHandCursor)
        pill_px = Icon.load_pixmap("pill", size=12)
        if pill_px and not pill_px.isNull():
            map_button.setIcon(QIcon(pill_px))
            map_button.setIconSize(QSize(12, 12))
        map_button.setText("فتح الخريطة")
        map_button.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        map_button.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {Colors.PRIMARY_BLUE};
                border: none;
                border-radius: 5px;
                padding: 4px;
                text-align: center;
            }}
        """)
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        from PyQt5.QtGui import QColor
        shadow = QGraphicsDropShadowEffect(map_button)
        shadow.setBlurRadius(8)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 60))
        map_button.setGraphicsEffect(shadow)
        map_button.setEnabled(True)
        map_button.clicked.connect(self._open_map_view)
        self._map_button = map_button

        map_section.addWidget(self._map_container)

        self.f_location_status = QLabel("")
        self.f_location_status.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self.f_location_status.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent;"
        )
        map_section.addWidget(self.f_location_status)
        map_section.addStretch(1)

        content_row.addLayout(map_section, stretch=1)

        # --- Section 2: وثائق المبنى ---
        docs_section = QVBoxLayout()
        docs_section.setSpacing(4)

        docs_lbl = QLabel("وثائق المبنى")
        docs_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        docs_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        docs_section.addWidget(docs_lbl)

        self.docs_scroll = QScrollArea()
        self.docs_scroll.setFixedHeight(130)
        self.docs_scroll.setWidgetResizable(True)
        self.docs_scroll.setFrameShape(QFrame.NoFrame)
        self.docs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.docs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.docs_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #F8FAFF;
                border: 1px solid #dcdfe6;
                border-radius: 8px;
            }
        """)

        self.docs_container = QWidget()
        self.docs_container.setStyleSheet("background: transparent;")
        self.docs_layout = QHBoxLayout(self.docs_container)
        self.docs_layout.setContentsMargins(8, 8, 8, 8)
        self.docs_layout.setSpacing(8)
        self.docs_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._docs_empty_lbl = QLabel("لا توجد وثائق")
        self._docs_empty_lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        self._docs_empty_lbl.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; background: transparent;"
        )
        self._docs_empty_lbl.setAlignment(Qt.AlignCenter)
        self.docs_layout.addWidget(self._docs_empty_lbl)
        self.docs_layout.addStretch()

        self.docs_scroll.setWidget(self.docs_container)
        docs_section.addWidget(self.docs_scroll)
        docs_section.addStretch(1)

        content_row.addLayout(docs_section, stretch=1)

        # --- Section 3: وصف البناء ---
        desc_section = QVBoxLayout()
        desc_section.setSpacing(4)

        desc_lbl = QLabel("وصف البناء")
        desc_lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        desc_lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        desc_section.addWidget(desc_lbl)

        self.f_description = QTextEdit()
        self.f_description.setReadOnly(True)
        self.f_description.setFixedHeight(130)
        self.f_description.setStyleSheet(_TEXTAREA_STYLE)
        self.f_description.setPlaceholderText("لا يوجد وصف")
        desc_section.addWidget(self.f_description)
        desc_section.addStretch(1)

        content_row.addLayout(desc_section, stretch=1)

        card_layout.addLayout(content_row)
        return card

    # ------------------------------------------------------------------
    # Reusable builders (DRY)
    # ------------------------------------------------------------------

    def _make_card_shell(self, title: str, subtitle: str, icon_name: str, columns: int):
        """
        Create a card frame with icon+title+subtitle header, divider, and QGridLayout.
        Returns (card_frame, grid_layout).
        """
        card = QFrame()
        card.setStyleSheet(_CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        layout.addLayout(self._make_icon_header(title, subtitle, icon_name))

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet("border: none; background-color: #e1e8ee;")
        layout.addWidget(divider)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)
        for col in range(columns):
            grid.setColumnStretch(col, 1)
        layout.addLayout(grid)

        return card, grid

    @staticmethod
    def _make_icon_header(title: str, subtitle: str, icon_name: str) -> QHBoxLayout:
        """Build icon + (title / subtitle) header row — matches AddBuildingPage Card 1/2."""
        from ui.components.icon import Icon

        row = QHBoxLayout()
        row.setSpacing(10)
        row.setContentsMargins(0, 0, 0, 0)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)
        px = Icon.load_pixmap(icon_name, size=24)
        if px and not px.isNull():
            icon_lbl.setPixmap(px)
        else:
            icon_lbl.setStyleSheet(icon_lbl.styleSheet() + "font-size: 16px;")
            icon_lbl.setText("🏢")

        row.addWidget(icon_lbl)

        col = QVBoxLayout()
        col.setSpacing(1)

        t = QLabel(title)
        t.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        t.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")

        s = QLabel(subtitle)
        s.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        s.setStyleSheet(f"color: {Colors.WIZARD_SUBTITLE}; background: transparent;")

        col.addWidget(t)
        col.addWidget(s)
        row.addLayout(col)
        row.addStretch()
        return row

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
        field.setFixedHeight(40)
        field.setAlignment(Qt.AlignCenter)
        field.setStyleSheet(_FIELD_STYLE)
        vbox.addWidget(field)

        grid.addWidget(container, row, col, 1, col_span)
        return field

    # ------------------------------------------------------------------
    # Data population
    # ------------------------------------------------------------------

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
            self.f_location_status.setText(f"الإحداثيات: {lat:.6f}, {lon:.6f}")
        else:
            self.f_location_status.setText("")

        # Card 3 — description
        desc = (
            getattr(b, "general_description", None)
            or getattr(b, "location_description", None)
            or ""
        )
        self.f_description.setPlainText(desc)

        # Card 3 — documents
        uuid = getattr(b, "building_uuid", None)
        if uuid:
            self._load_building_documents(uuid)

    def _load_building_documents(self, building_uuid: str):
        """Fetch and display building document thumbnails (mirrors AddBuildingPage)."""
        while self.docs_layout.count() > 0:
            item = self.docs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        try:
            from services.api_client import get_api_client
            api = get_api_client()
            if not api:
                self._add_no_docs_label()
                return
            docs = api.get_building_documents(building_uuid)
        except Exception as e:
            logger.warning(f"Failed to load building documents: {e}")
            self._add_no_docs_label()
            return

        if not docs:
            self._add_no_docs_label()
            return

        from PyQt5.QtWidgets import QSizePolicy
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices

        for doc in docs:
            card = self._make_doc_card(doc)
            self.docs_layout.addWidget(card)
        self.docs_layout.addStretch()

    def _add_no_docs_label(self):
        lbl = QLabel("لا يوجد وثائق مرفقة")
        lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        lbl.setStyleSheet(f"color: #909399; background: transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        self.docs_layout.addWidget(lbl)
        self.docs_layout.addStretch()

    def _make_doc_card(self, doc: dict) -> QFrame:
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices

        card = QFrame()
        card.setFixedSize(70, 100)
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #E1E8ED;
                border-radius: 6px;
            }
            QFrame:hover { border-color: #3890DF; }
        """)
        card.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        mime_type = doc.get("mimeType", "")
        file_path = doc.get("filePath", "")
        file_name = doc.get("originalFileName", "")

        thumb = QLabel()
        thumb.setFixedSize(60, 60)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("border: none; background: transparent;")

        if mime_type.startswith("image/") and file_path:
            px = QPixmap(file_path)
            if not px.isNull():
                thumb.setPixmap(px.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                thumb.setText("🖼")
                thumb.setFont(create_font(size=20, weight=FontManager.WEIGHT_REGULAR))
        else:
            thumb.setText("📄")
            thumb.setFont(create_font(size=20, weight=FontManager.WEIGHT_REGULAR))

        layout.addWidget(thumb, alignment=Qt.AlignCenter)

        name_lbl = QLabel(file_name[:10] + "..." if len(file_name) > 10 else file_name)
        name_lbl.setFont(create_font(size=7, weight=FontManager.WEIGHT_REGULAR))
        name_lbl.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;"
        )
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl)

        card.mousePressEvent = lambda event, fp=file_path: (
            QDesktopServices.openUrl(QUrl.fromLocalFile(fp)) if fp else None
        )
        return card

    # ------------------------------------------------------------------
    # Map viewer
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # BaseStep interface
    # ------------------------------------------------------------------

    def validate(self) -> StepValidationResult:
        result = StepValidationResult(is_valid=True, errors=[])
        if not self.context.building:
            result.add_error("لم يتم اختيار البناء")
            return result

        if not self._use_api:
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
            result.add_error("فشل إنشاء المسح على السيرفر. يرجى المحاولة مجدداً.")

        return result

    def collect_data(self) -> dict:
        return {}

    def get_name(self) -> str:
        return tr("wizard.step.building_registration")
