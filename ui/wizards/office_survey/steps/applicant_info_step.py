# -*- coding: utf-8 -*-
"""
Applicant Info Step - Step 1 of Office Survey Wizard.

Single-page form (no tabs). White rounded card with drop shadow.
Fields: first/last/father/mother name, birth year, gender, nationality,
        national ID, mobile (+963|09), landline, ID photo, in-person visit.

collect_data() stores context.applicant with backward-compat "full_name" key.
"""

import os
from typing import List

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QComboBox,
    QGridLayout, QCheckBox, QSizePolicy,
    QScrollArea, QFileDialog, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import Qt, QUrl, QRegExp as QtRegExp
from PyQt5.QtGui import QColor, QPixmap, QRegExpValidator, QDesktopServices

from app.config import Config
from ui.wizards.framework import BaseStep, StepValidationResult
from ui.wizards.office_survey.survey_context import SurveyContext
from ui.wizards.office_survey.wizard_styles import (
    STEP_CARD_STYLE, FORM_FIELD_STYLE,
)
from ui.design_system import Colors
from ui.font_utils import create_font, FontManager
from ui.components.rtl_combo import RtlCombo
from ui.style_manager import StyleManager
from services.display_mappings import get_gender_options, get_nationality_options
from services.translation_manager import tr, get_layout_direction
from ui.components.toast import Toast
from ui.components.loading_spinner import LoadingSpinnerOverlay
from utils.logger import get_logger

logger = get_logger(__name__)


class ApplicantInfoStep(BaseStep):
    """Step 1: Applicant (Visitor) Information — single-page form."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self.uploaded_files: List[str] = []
        self._field_styles: dict = {}
        from services.api_client import get_api_client
        self._api_client = get_api_client()
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

        # White rounded card with drop shadow
        card = QFrame()
        card.setObjectName("StepCard")
        card.setStyleSheet(STEP_CARD_STYLE)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 20))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        card_layout.setDirection(QVBoxLayout.TopToBottom)

        # Icon header
        card_layout.addLayout(self._make_icon_header(
            title=tr("wizard.step.applicant_info"),
            subtitle=tr("wizard.applicant.card_subtitle"),
            icon_name="user",
        ))

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet("border: none; background-color: #e1e8ee;")
        card_layout.addWidget(div)

        # Form grid
        card_layout.addLayout(self._build_form())

        # Wrap card in container to allow stretching below
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        wrap = QVBoxLayout(container)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.setSpacing(0)
        wrap.addWidget(card)
        wrap.addStretch()

        scroll.setWidget(container)
        self.main_layout.addWidget(scroll)

        # Loading spinner overlay
        self._spinner = LoadingSpinnerOverlay(self)

    def _build_form(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        _name_v = QRegExpValidator(QtRegExp("[\u0600-\u06FFa-zA-Z\\s.\\-']+"))
        row = 0

        # --- Row 1: الاسم الأول | الكنية ---
        grid.addWidget(self._lbl(tr("wizard.person_dialog.first_name") + " *"), row, 0)
        grid.addWidget(self._lbl(tr("wizard.person_dialog.last_name") + " *"), row, 1)
        row += 1

        self.first_name = self._field(tr("wizard.person_dialog.first_name_placeholder"), _name_v)
        self._first_name_error = self._err_lbl()
        fn_box = self._field_box(self.first_name, self._first_name_error)
        grid.addLayout(fn_box, row, 0)

        self.last_name = self._field(tr("wizard.person_dialog.last_name_placeholder"), _name_v)
        self._last_name_error = self._err_lbl()
        ln_box = self._field_box(self.last_name, self._last_name_error)
        grid.addLayout(ln_box, row, 1)
        row += 1

        # --- Row 2: اسم الأب | اسم الأم ---
        grid.addWidget(self._lbl(tr("wizard.person_dialog.father_name") + " *"), row, 0)
        grid.addWidget(self._lbl(tr("wizard.person_dialog.mother_name") + " *"), row, 1)
        row += 1

        self.father_name = self._field(tr("wizard.person_dialog.father_name_placeholder"), _name_v)
        self._father_name_error = self._err_lbl()
        fn_box = self._field_box(self.father_name, self._father_name_error)
        grid.addLayout(fn_box, row, 0)

        self.mother_name = self._field(tr("wizard.person_dialog.mother_name_placeholder"), _name_v)
        self._mother_name_error = self._err_lbl()
        mn_box = self._field_box(self.mother_name, self._mother_name_error)
        grid.addLayout(mn_box, row, 1)
        row += 1

        # --- Row 3: تاريخ الميلاد | الجنس ---
        grid.addWidget(self._lbl(tr("wizard.person_dialog.birth_date")), row, 0)
        grid.addWidget(self._lbl(tr("wizard.person_dialog.gender")), row, 1)
        row += 1

        birth_layout = QHBoxLayout()
        birth_layout.setSpacing(6)
        birth_layout.setContentsMargins(0, 0, 0, 0)

        self.birth_year_combo = QComboBox()
        self.birth_year_combo.setLayoutDirection(Qt.LeftToRight)
        self.birth_year_combo.setStyleSheet(self._input_style())
        self.birth_year_combo.addItem("--", None)
        for y in range(2010, 1919, -1):
            self.birth_year_combo.addItem(str(y), y)

        self.birth_month_combo = QComboBox()
        self.birth_month_combo.setLayoutDirection(Qt.LeftToRight)
        self.birth_month_combo.setStyleSheet(self._input_style())
        self.birth_month_combo.addItem("--", None)
        for m in range(1, 13):
            self.birth_month_combo.addItem(str(m), m)

        self.birth_day_combo = QComboBox()
        self.birth_day_combo.setLayoutDirection(Qt.LeftToRight)
        self.birth_day_combo.setStyleSheet(self._input_style())
        self.birth_day_combo.addItem("--", None)
        for d in range(1, 32):
            self.birth_day_combo.addItem(str(d), d)

        birth_layout.addWidget(self.birth_year_combo, 2)
        birth_layout.addWidget(self.birth_month_combo, 1)
        birth_layout.addWidget(self.birth_day_combo, 1)
        birth_container = QWidget()
        birth_container.setStyleSheet("background-color: transparent;")
        birth_container.setLayout(birth_layout)
        grid.addWidget(birth_container, row, 0)

        self.gender = RtlCombo()
        self.gender.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_gender_options():
            self.gender.addItem(display_name, code)
        self.gender.setStyleSheet(self._input_style())
        grid.addWidget(self.gender, row, 1)
        row += 1

        # --- Row 4: الجنسية | الرقم الوطني ---
        grid.addWidget(self._lbl(tr("wizard.person_dialog.nationality")), row, 0)
        grid.addWidget(self._lbl(tr("wizard.person_dialog.national_id")), row, 1)
        row += 1

        self.nationality = RtlCombo()
        self.nationality.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_nationality_options():
            self.nationality.addItem(display_name, code)
        self.nationality.setStyleSheet(self._input_style())
        grid.addWidget(self.nationality, row, 0)

        self.national_id = self._field("0000000000", QRegExpValidator(QtRegExp(r"\d{0,11}")))
        self._nid_error = self._err_lbl()
        nid_box = self._field_box(self.national_id, self._nid_error)
        grid.addLayout(nid_box, row, 1)
        row += 1

        # --- Row 5: رقم الجوال (full width) ---
        grid.addWidget(self._lbl(tr("wizard.person_dialog.mobile")), row, 0, 1, 2)
        row += 1
        mobile_container = QFrame()
        mobile_container.setStyleSheet(f"""
            QFrame {{
                border: 1.5px solid #D0D7E2;
                border-radius: 8px;
                background-color: #FFFFFF;
            }}
            QFrame:focus-within {{ border: 1.5px solid {Colors.PRIMARY_BLUE}; }}
        """)
        mob_layout = QHBoxLayout(mobile_container)
        mob_layout.setContentsMargins(0, 0, 0, 0)
        mob_layout.setSpacing(0)
        mob_layout.setDirection(QHBoxLayout.RightToLeft)
        prefix_lbl = QLabel("+963 | 09")
        prefix_lbl.setFixedWidth(90)
        prefix_lbl.setAlignment(Qt.AlignCenter)
        prefix_lbl.setStyleSheet(f"""
            QLabel {{
                color: {Colors.WIZARD_SUBTITLE};
                font-size: 10pt;
                border-left: 1px solid #D0D7E2;
                padding: 0 10px;
                background: transparent;
            }}
        """)
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("00000000")
        self.phone.setValidator(QRegExpValidator(QtRegExp(r"\d{0,8}")))
        self.phone.setStyleSheet("""
            QLineEdit {
                border: none; background: transparent;
                padding: 8px 12px; font-size: 10pt; color: #2C3E50;
            }
        """)
        mob_layout.addWidget(prefix_lbl)
        mob_layout.addWidget(self.phone)
        self._mobile_error = self._err_lbl()
        mob_outer = QVBoxLayout()
        mob_outer.setSpacing(2)
        mob_outer.setContentsMargins(0, 0, 0, 0)
        mob_outer.addWidget(mobile_container)
        mob_outer.addWidget(self._mobile_error)
        grid.addLayout(mob_outer, row, 0, 1, 2)
        row += 1

        # --- Row 6: رقم الهاتف الثابت (full width) ---
        grid.addWidget(self._lbl(tr("wizard.person_dialog.phone")), row, 0, 1, 2)
        row += 1
        self.landline = self._field("0000000", QRegExpValidator(QtRegExp(r"\d{0,7}")))
        self._landline_error = self._err_lbl()
        land_box = self._field_box(self.landline, self._landline_error)
        grid.addLayout(land_box, row, 0, 1, 2)
        row += 1

        # --- Row 7: ID photo upload (full width) ---
        grid.addWidget(self._lbl(tr("wizard.person_dialog.attach_id_photos")), row, 0, 1, 2)
        row += 1
        self._id_upload_frame = self._create_upload_frame(
            self._browse_files, "id_upload",
            button_text=tr("wizard.person_dialog.attach_id_photos"),
        )
        grid.addWidget(self._id_upload_frame, row, 0, 1, 2)
        row += 1

        # --- Row 8: زيارة حضورية (checkbox) ---
        self.in_person_check = QCheckBox(tr("wizard.applicant.in_person"))
        self.in_person_check.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        self.in_person_check.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.in_person_check.setChecked(True)
        grid.addWidget(self.in_person_check, row, 0, 1, 2)

        # Connect clear-error signals
        self.first_name.textChanged.connect(lambda: self._clear_err(self.first_name, self._first_name_error))
        self.last_name.textChanged.connect(lambda: self._clear_err(self.last_name, self._last_name_error))
        self.father_name.textChanged.connect(lambda: self._clear_err(self.father_name, self._father_name_error))
        self.mother_name.textChanged.connect(lambda: self._clear_err(self.mother_name, self._mother_name_error))
        self.national_id.textChanged.connect(lambda: self._clear_err(self.national_id, self._nid_error))
        self.phone.textChanged.connect(lambda: self._clear_err(self.phone, self._mobile_error))
        self.landline.textChanged.connect(lambda: self._clear_err(self.landline, self._landline_error))

        return grid
    # File upload helpers

    def _browse_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, tr("wizard.person_dialog.choose_files"), "",
            "Images (*.png *.jpg *.jpeg *.pdf)"
        )
        if file_paths:
            existing = {os.path.normpath(f) for f in self.uploaded_files}
            for fp in file_paths:
                if os.path.normpath(fp) not in existing:
                    self.uploaded_files.append(fp)
                    existing.add(os.path.normpath(fp))
            self._update_upload_thumbnails("id_upload", self.uploaded_files)

    def _remove_uploaded_file(self, file_path: str):
        if file_path in self.uploaded_files:
            self.uploaded_files.remove(file_path)
        self._update_upload_thumbnails("id_upload", self.uploaded_files)

    def _update_upload_thumbnails(self, obj_name: str, file_paths: list):
        frame = self.findChild(QFrame, obj_name)
        if not frame or not hasattr(frame, "_thumbnails_layout"):
            return
        layout = frame._thumbnails_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for fp in file_paths:
            layout.addWidget(self._create_thumbnail_widget(fp, self._remove_uploaded_file))

    def _create_thumbnail_widget(self, file_path: str, remove_callback) -> QWidget:
        container = QWidget()
        container.setFixedSize(48, 48)
        container.setStyleSheet("border: none; background: transparent;")

        thumb = QLabel(container)
        thumb.setFixedSize(44, 44)
        thumb.move(4, 4)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("""
            QLabel {
                border: 1px solid #E0E6ED; border-radius: 6px;
                background-color: #FFFFFF;
            }
        """)
        thumb.setCursor(Qt.PointingHandCursor)
        px = QPixmap(file_path)
        if not px.isNull():
            thumb.setPixmap(px.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            thumb.setText("📄")
        def _open_file(event, fp=file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(fp))

        thumb.mousePressEvent = _open_file

        x_btn = QLabel(container)
        x_btn.setFixedSize(18, 18)
        x_btn.move(0, 0)
        x_btn.setText("✕")
        x_btn.setAlignment(Qt.AlignCenter)
        x_btn.setStyleSheet("""
            QLabel {
                background-color: rgba(60,60,60,180); color: white;
                border-radius: 9px; font-size: 10px; font-weight: bold; border: none;
            }
        """)
        x_btn.setCursor(Qt.PointingHandCursor)
        x_btn.mousePressEvent = lambda e, fp=file_path: remove_callback(fp)
        return container
    # Widget factory helpers

    @staticmethod
    def _make_icon_header(title: str, subtitle: str, icon_name: str) -> QHBoxLayout:
        """Build icon + (title / subtitle) header row."""
        from ui.components.icon import Icon

        row = QHBoxLayout()
        row.setSpacing(10)
        row.setContentsMargins(0, 0, 0, 0)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #EBF5FF;
                border: 1px solid #DBEAFE;
                border-radius: 10px;
            }
        """)
        px = Icon.load_pixmap(icon_name, size=24)
        if px and not px.isNull():
            icon_lbl.setPixmap(px)
        else:
            icon_lbl.setStyleSheet(icon_lbl.styleSheet() + "font-size: 16px;")
            icon_lbl.setText("\U0001F464")

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

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        return lbl

    def _field(self, placeholder: str, validator=None) -> QLineEdit:
        f = QLineEdit()
        f.setPlaceholderText(placeholder)
        if validator:
            f.setValidator(validator)
        f.setStyleSheet(self._input_style())
        return f

    @staticmethod
    def _err_lbl() -> QLabel:
        lbl = QLabel("")
        lbl.setStyleSheet(f"color: {Colors.ERROR}; font-size: 9pt; font-weight: 600; background: transparent;")
        lbl.setVisible(False)
        return lbl

    @staticmethod
    def _field_box(field: QLineEdit, error_lbl: QLabel) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(2)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(field)
        box.addWidget(error_lbl)
        return box

    def _create_upload_frame(self, browse_callback, obj_name: str, button_text: str = None) -> QFrame:
        from ui.components.icon import Icon

        frame = QFrame()
        frame.setObjectName(obj_name)
        frame.setMinimumHeight(55)
        frame.setStyleSheet(f"""
            QFrame#{obj_name} {{
                border: 2px dashed rgba(56, 144, 223, 0.4);
                border-radius: 8px;
                background-color: #F8FAFF;
            }}
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)
        frame_layout.setSpacing(6)

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        thumbnails_container = QWidget()
        thumbnails_container.setStyleSheet("border: none; background: transparent;")
        thumbnails_layout = QHBoxLayout(thumbnails_container)
        thumbnails_layout.setContentsMargins(0, 0, 0, 0)
        thumbnails_layout.setSpacing(6)
        row_layout.addWidget(thumbnails_container)
        row_layout.addStretch()

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(22, 22)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        up_px = Icon.load_pixmap("upload_file", size=20)
        if up_px and not up_px.isNull():
            icon_lbl.setPixmap(up_px)
        else:
            icon_lbl.setText("📎")
            icon_lbl.setStyleSheet("border: none; font-size: 16px; background: transparent;")
        icon_lbl.setCursor(Qt.PointingHandCursor)
        icon_lbl.mousePressEvent = lambda e: browse_callback()
        row_layout.addWidget(icon_lbl)

        text_btn = QPushButton(button_text or tr("wizard.person_dialog.attach_id_photos"))
        text_btn.setStyleSheet("""
            QPushButton {
                color: #4a90e2; text-decoration: underline;
                border: none; background: transparent;
                font-size: 12px; font-weight: 500; padding: 0px;
            }
            QPushButton:hover { color: #357ABD; }
        """)
        text_btn.setCursor(Qt.PointingHandCursor)
        text_btn.clicked.connect(browse_callback)
        row_layout.addWidget(text_btn)
        row_layout.addStretch()
        frame_layout.addLayout(row_layout)

        frame._thumbnails_container = thumbnails_container
        frame._thumbnails_layout = thumbnails_layout
        frame._text_btn = text_btn
        return frame
    # Style helpers

    def _input_style(self) -> str:
        down_img = str(Config.IMAGES_DIR / "down.png").replace("\\", "/")
        return FORM_FIELD_STYLE + f"""
            QComboBox::down-arrow {{ image: url({down_img}); width: 12px; height: 12px; }}
        """

    def _input_error_style(self) -> str:
        return f"""
            QLineEdit, QComboBox, QSpinBox {{
                border: 2px solid {Colors.ERROR};
                border-radius: 8px;
                padding: 8px 12px;
                background-color: #FFF5F5;
                color: #2C3E50;
                font-size: 10pt;
                min-height: 26px;
            }}
        """

    def _set_err(self, field, error_lbl: QLabel):
        if field not in self._field_styles:
            self._field_styles[field] = field.styleSheet()
        field.setStyleSheet(self._input_error_style())
        error_lbl.setText("!")
        error_lbl.setVisible(True)

    def _clear_err(self, field, error_lbl: QLabel):
        field.setStyleSheet(self._field_styles.get(field, self._input_style()))
        error_lbl.setText("")
        error_lbl.setVisible(False)
    # BaseStep interface

    def validate(self) -> StepValidationResult:
        result = StepValidationResult(is_valid=True, errors=[])

        # 1. Local validation — required fields
        if not self.first_name.text().strip():
            self._set_err(self.first_name, self._first_name_error)
            result.add_error(tr("wizard.applicant.first_name_required"))
        if not self.last_name.text().strip():
            self._set_err(self.last_name, self._last_name_error)
            result.add_error(tr("wizard.applicant.last_name_required"))
        if not self.father_name.text().strip():
            self._set_err(self.father_name, self._father_name_error)
            result.add_error(tr("wizard.applicant.father_name_required"))
        if not self.mother_name.text().strip():
            self._set_err(self.mother_name, self._mother_name_error)
            result.add_error(tr("wizard.applicant.mother_name_required"))

        # Optional field format validation
        phone_text = self.phone.text().strip()
        if phone_text and len(phone_text) != 8:
            self._set_err(self.phone, self._mobile_error)
            result.add_error(tr("wizard.applicant.mobile_8_digits"))

        landline_text = self.landline.text().strip()
        if landline_text and len(landline_text) != 7:
            self._set_err(self.landline, self._landline_error)
            result.add_error(tr("wizard.applicant.landline_7_digits"))

        nid_text = self.national_id.text().strip()
        if not nid_text:
            self._set_err(self.national_id, self._nid_error)
            result.add_error(tr("wizard.applicant.national_id_required"))
        elif len(nid_text) != 11 or not nid_text.isdigit():
            self._set_err(self.national_id, self._nid_error)
            result.add_error(tr("wizard.applicant.national_id_11_digits"))

        if not result.is_valid:
            return result

        # 2. Require survey_id from previous step
        survey_id = self.context.get_data("survey_id")
        if not survey_id:
            result.add_error(tr("wizard.applicant.no_survey_error"))
            return result

        # 3. Collect data into context.applicant
        self.collect_data()

        # 4. Set auth token
        self._set_auth_token()

        self._spinner.show_loading(tr("component.loading.default"))
        try:
            # 5. Call API (skip if contact person already created for this survey)
            existing_cp_id = self.context.get_data("contact_person_id")
            if not existing_cp_id:
                try:
                    response = self._api_client.create_contact_person(survey_id, self.context.applicant)
                    self.context.update_data(
                        "contact_person_id",
                        response.get("id") or response.get("contactPersonId", "")
                    )
                except Exception as e:
                    from services.exceptions import ApiException
                    if isinstance(e, ApiException) and e.status_code == 409:
                        from services.error_mapper import build_duplicate_person_message
                        result.add_error(build_duplicate_person_message(e.response_data))
                    else:
                        logger.error(f"Contact person API failed: {e}")
                        result.add_error(tr("wizard.applicant.save_failed"))
            else:
                try:
                    self._api_client.update_contact_person(survey_id, existing_cp_id, self.context.applicant)
                    logger.info(f"Contact person {existing_cp_id} updated")
                except Exception as e:
                    from services.error_mapper import is_duplicate_nid_error, build_duplicate_person_message
                    if is_duplicate_nid_error(e):
                        result.add_error(build_duplicate_person_message(getattr(e, 'response_data', {})))
                    else:
                        logger.error(f"Contact person update failed: {e}")
                        result.add_error(tr("wizard.applicant.update_failed"))

            # 6. Upload ID photos (if any and not already uploaded)
            person_id = self.context.get_data("contact_person_id")
            if person_id and self.uploaded_files:
                already_uploaded = set(self.context.get_data("uploaded_id_photos") or [])
                new_files = [f for f in self.uploaded_files if f not in already_uploaded]
                for fp in new_files:
                    try:
                        self._api_client.upload_identification_document(
                            survey_id=survey_id,
                            person_id=person_id,
                            file_path=fp,
                        )
                        already_uploaded.add(fp)
                        logger.info(f"ID photo uploaded: {os.path.basename(fp)}")
                    except Exception as e:
                        logger.error(f"Failed to upload ID photo {fp}: {e}")
                        Toast.show_toast(self, tr("wizard.applicant.load_failed"), Toast.ERROR)
                self.context.update_data("uploaded_id_photos", list(already_uploaded))

            # 7. Cache contact person locally for draft resume
            self._save_contact_person_locally(survey_id)

            # 8. Save intervieweeName so it appears in the surveys list
            try:
                a = self.context.applicant or {}
                parts = [a.get("first_name_ar", ""), a.get("father_name_ar", ""), a.get("last_name_ar", "")]
                interviewee_name = " ".join(p for p in parts if p) or a.get("full_name")
                if interviewee_name:
                    self._api_client.save_draft_to_backend(survey_id, {"interviewee_name": interviewee_name})
                    logger.info(f"intervieweeName saved: {interviewee_name}")
            except Exception as e:
                logger.warning(f"Could not save interviewee name: {e}")
                Toast.show_toast(self, tr("wizard.applicant.load_failed"), Toast.ERROR)
        finally:
            self._spinner.hide_loading()

        return result

    def _save_contact_person_locally(self, survey_id: str):
        """Cache contact person data locally for draft resume."""
        try:
            from repositories.survey_repository import SurveyRepository
            repo = SurveyRepository(self.context.db)
            cp_id = self.context.get_data("contact_person_id")
            if cp_id and self.context.applicant:
                repo.save_contact_person_cache(survey_id, cp_id, self.context.applicant)
                logger.debug(f"Contact person cached locally for survey {survey_id}")
        except Exception as e:
            logger.warning(f"Failed to cache contact person locally: {e}")
            Toast.show_toast(self, tr("wizard.applicant.load_failed"), Toast.ERROR)

    def collect_data(self) -> dict:
        fn  = self.first_name.text().strip()
        fat = self.father_name.text().strip()
        ln  = self.last_name.text().strip()

        # Build birth_date from 3 combos
        y = self.birth_year_combo.currentData()
        m = self.birth_month_combo.currentData()
        d = self.birth_day_combo.currentData()
        birth_date = None
        if y:
            month = m if m else 1
            day = d if d else 1
            birth_date = f"{y:04d}-{month:02d}-{day:02d}"

        data = {
            "first_name_ar":  fn,
            "father_name_ar": fat,
            "mother_name_ar": self.mother_name.text().strip(),
            "last_name_ar":   ln,
            "birth_date":     birth_date,
            "gender":         self.gender.currentData(),
            "nationality":    self.nationality.currentData(),
            "national_id":    self.national_id.text().strip(),
            "phone":          f"09{self.phone.text().strip()}" if self.phone.text().strip() else "",
            "landline":       self.landline.text().strip(),
            "in_person":      self.in_person_check.isChecked(),
            "id_photo_paths": list(self.uploaded_files),
            "full_name": " ".join(p for p in [fn, fat, ln] if p),
        }
        self.context.applicant = data
        return data

    def reset(self):
        """Clear all applicant UI fields for a new wizard session."""
        if not self._is_initialized:
            return
        for field in [self.first_name, self.father_name, self.last_name,
                      self.mother_name, self.national_id, self.phone,
                      self.landline]:
            field.clear()
        self.birth_year_combo.setCurrentIndex(0)
        self.birth_month_combo.setCurrentIndex(0)
        self.birth_day_combo.setCurrentIndex(0)
        self.gender.setCurrentIndex(0)
        self.nationality.setCurrentIndex(0)
        self.in_person_check.setChecked(True)
        self.uploaded_files.clear()
        self._update_upload_thumbnails("id_upload", [])
        for err_lbl in [self._first_name_error, self._last_name_error,
                        self._father_name_error, self._mother_name_error,
                        self._mobile_error, self._landline_error]:
            err_lbl.setText("")
            err_lbl.setVisible(False)

    def populate_data(self):
        a = self.context.applicant
        if not a:
            self.reset()
            return

        self.first_name.setText(a.get("first_name_ar", ""))
        self.father_name.setText(a.get("father_name_ar", ""))
        self.mother_name.setText(a.get("mother_name_ar", ""))
        self.last_name.setText(a.get("last_name_ar", ""))

        # Populate birth date combos
        bd = a.get("birth_date") or ""
        if bd:
            parts = str(bd)[:10].split('-')
            if len(parts) >= 1 and parts[0].isdigit():
                idx = self.birth_year_combo.findData(int(parts[0]))
                if idx >= 0:
                    self.birth_year_combo.setCurrentIndex(idx)
            if len(parts) >= 2 and parts[1].isdigit():
                idx = self.birth_month_combo.findData(int(parts[1]))
                if idx >= 0:
                    self.birth_month_combo.setCurrentIndex(idx)
            if len(parts) >= 3 and parts[2].isdigit():
                idx = self.birth_day_combo.findData(int(parts[2]))
                if idx >= 0:
                    self.birth_day_combo.setCurrentIndex(idx)
        elif a.get("birth_year"):
            idx = self.birth_year_combo.findData(int(a["birth_year"]))
            if idx >= 0:
                self.birth_year_combo.setCurrentIndex(idx)

        gender_val = a.get("gender")
        for i in range(self.gender.count()):
            if self.gender.itemData(i) == gender_val:
                self.gender.setCurrentIndex(i)
                break

        nat_val = a.get("nationality")
        for i in range(self.nationality.count()):
            if self.nationality.itemData(i) == nat_val:
                self.nationality.setCurrentIndex(i)
                break

        self.national_id.setText(a.get("national_id", ""))
        phone_val = a.get("phone") or ""
        if phone_val.startswith("09"):
            phone_val = phone_val[2:]
        self.phone.setText(phone_val)
        self.landline.setText(a.get("landline", ""))
        self.in_person_check.setChecked(a.get("in_person", True))

        photos = a.get("id_photo_paths", [])
        self.uploaded_files = list(photos)
        if photos:
            self._update_upload_thumbnails("id_upload", photos)

    def update_language(self, is_arabic: bool):
        """Update layout direction when language changes."""
        self.setLayoutDirection(get_layout_direction())

    def get_name(self) -> str:
        return tr("wizard.step.applicant_info")
