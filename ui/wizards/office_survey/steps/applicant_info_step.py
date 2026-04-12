# -*- coding: utf-8 -*-
"""
Applicant Info Step - Step 1 of Office Survey Wizard.

Single-page form with grouped sections: Personal Info, Contact Details,
Visit Type, ID Photos. White rounded card with left blue accent.

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
    make_step_card, make_icon_header, make_divider, make_sub_section_header,
)
from ui.design_system import Colors, ScreenScale
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
    """Step 1: Applicant (Visitor) Information — grouped-section form."""

    def __init__(self, context: SurveyContext, parent=None):
        super().__init__(context, parent)
        self.uploaded_files: List[str] = []
        self._field_styles: dict = {}
        from services.api_client import get_api_client
        self._api_client = get_api_client()

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

        card = make_step_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(20)

        # Icon header
        header_layout, self.app_title_lbl, self.app_subtitle_lbl = make_icon_header(
            title=tr("wizard.step.applicant_info"),
            subtitle=tr("wizard.applicant.card_subtitle"),
            icon_name="user",
)

        card_layout.addLayout(header_layout)

        card_layout.addWidget(make_divider())

        # Section 1: Personal Information
        
        self.section_personal_header = make_sub_section_header(tr("wizard.section.personal_info"))
        card_layout.addWidget(self.section_personal_header)
        card_layout.addLayout(self._build_personal_section())

        # Section 2: Contact Details
        
        self.section_contact_header = make_sub_section_header(tr("wizard.section.contact_details"))
        card_layout.addWidget(self.section_contact_header)
        card_layout.addLayout(self._build_contact_section())

        # Section 3: Visit Type
        
        self.section_visit_header = make_sub_section_header(tr("wizard.section.visit_type"))
        card_layout.addWidget(self.section_visit_header)
        card_layout.addLayout(self._build_visit_section())

        # Section 4: ID Photos
        
        self.section_id_header = make_sub_section_header(tr("wizard.section.id_photos"))
        card_layout.addWidget(self.section_id_header)

        from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel
        doc_type_row = QHBoxLayout()
        doc_type_row.setContentsMargins(0, 0, 0, 4)
        self.lbl_id_doc_type = QLabel(tr("wizard.person_dialog.id_document_type"))
        self.lbl_id_doc_type.setStyleSheet("color: #5A6B7F; font-weight: 600; font-size: 12px;")
        self._id_doc_type_combo = QComboBox()
        from services.display_mappings import get_identification_document_type_options
        for code, label in get_identification_document_type_options():
            if code == 0:
                continue
            self._id_doc_type_combo.addItem(label, code)
        self._id_doc_type_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #D0D7E2; border-radius: 8px;
                padding: 6px 10px; background: #F8FAFF; color: #2C3E50;
                font-size: 13px; min-height: 28px;
            }
            QComboBox:focus { border: 1.5px solid #3890DF; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox::down-arrow {
                image: none; width: 0; height: 0;
                border-left: 5px solid transparent; border-right: 5px solid transparent;
                border-top: 5px solid #7F8C9B;
            }
        """)
        doc_type_row.addWidget(self.lbl_id_doc_type)
        doc_type_row.addWidget(self._id_doc_type_combo, 1)
        card_layout.addLayout(doc_type_row)

        self._id_upload_frame = self._create_upload_frame(
            self._browse_files, "id_upload",
            button_text=tr("wizard.person_dialog.attach_id_photos"),
        )
        card_layout.addWidget(self._id_upload_frame)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        wrap = QVBoxLayout(container)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.setSpacing(0)
        wrap.addWidget(card)
        wrap.addStretch()

        scroll.setWidget(container)
        self.main_layout.addWidget(scroll)

        self._spinner = LoadingSpinnerOverlay(self)

    def _build_personal_section(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        _name_v = QRegExpValidator(QtRegExp("[\u0600-\u06FFa-zA-Z\\s.\\-']+"))
        row = 0

    # Row 1: First Name | Father Name
        self.lbl_first_name = self._lbl(tr("wizard.person_dialog.first_name") + " *")
        self.lbl_father_name = self._lbl(tr("wizard.person_dialog.father_name") + " *")
        grid.addWidget(self.lbl_first_name, row, 0)
        grid.addWidget(self.lbl_father_name, row, 1)
        row += 1

        self.first_name = self._field(tr("wizard.person_dialog.first_name_placeholder"), _name_v)
        self._first_name_error = self._err_lbl()
        grid.addLayout(self._field_box(self.first_name, self._first_name_error), row, 0)

        self.father_name = self._field(tr("wizard.person_dialog.father_name_placeholder"), _name_v)
        self._father_name_error = self._err_lbl()
        grid.addLayout(self._field_box(self.father_name, self._father_name_error), row, 1)
        row += 1

    # Row 2: Last Name | Mother Name
        self.lbl_last_name = self._lbl(tr("wizard.person_dialog.last_name") + " *")
        self.lbl_mother_name = self._lbl(tr("wizard.person_dialog.mother_name") + " *")
        grid.addWidget(self.lbl_last_name, row, 0)
        grid.addWidget(self.lbl_mother_name, row, 1)
        row += 1

        self.last_name = self._field(tr("wizard.person_dialog.last_name_placeholder"), _name_v)
        self._last_name_error = self._err_lbl()
        grid.addLayout(self._field_box(self.last_name, self._last_name_error), row, 0)

        self.mother_name = self._field(tr("wizard.person_dialog.mother_name_placeholder"), _name_v)
        self._mother_name_error = self._err_lbl()
        grid.addLayout(self._field_box(self.mother_name, self._mother_name_error), row, 1)
        row += 1

    # Row 3: Birth Date | Gender
        self.lbl_birth_date = self._lbl(tr("wizard.person_dialog.birth_date"))
        self.lbl_gender = self._lbl(tr("wizard.person_dialog.gender"))
        grid.addWidget(self.lbl_birth_date, row, 0)
        grid.addWidget(self.lbl_gender, row, 1)
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

    # Row 4: Nationality | National ID
        self.lbl_nationality = self._lbl(tr("wizard.person_dialog.nationality"))
        self.lbl_national_id = self._lbl(tr("wizard.person_dialog.national_id"))
        grid.addWidget(self.lbl_nationality, row, 0)
        grid.addWidget(self.lbl_national_id, row, 1)
        row += 1

        self.nationality = RtlCombo()
        self.nationality.addItem(tr("wizard.person_dialog.select"), None)
        for code, display_name in get_nationality_options():
            self.nationality.addItem(display_name, code)
        self.nationality.setStyleSheet(self._input_style())
        grid.addWidget(self.nationality, row, 0)

        self.national_id = self._field("0000000000", QRegExpValidator(QtRegExp(r"\d{0,11}")))
        self._nid_error = self._err_lbl()
        grid.addLayout(self._field_box(self.national_id, self._nid_error), row, 1)

    # Connect clear-error signals
        self.first_name.textChanged.connect(lambda: self._clear_err(self.first_name, self._first_name_error))
        self.last_name.textChanged.connect(lambda: self._clear_err(self.last_name, self._last_name_error))
        self.father_name.textChanged.connect(lambda: self._clear_err(self.father_name, self._father_name_error))
        self.mother_name.textChanged.connect(lambda: self._clear_err(self.mother_name, self._mother_name_error))
        self.national_id.textChanged.connect(lambda: self._clear_err(self.national_id, self._nid_error))

        return grid


    def _build_contact_section(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # Mobile number
        
        self.lbl_mobile = self._lbl(tr("wizard.person_dialog.mobile"))
        layout.addWidget(self.lbl_mobile)
        self._mobile_container = QFrame()
        self._mobile_container.setStyleSheet(f"""
            QFrame {{
                border: 1.5px solid #D0D7E2;
                border-radius: 10px;
                background-color: #f0f7ff;
            }}
            QFrame:focus-within {{ border: 1.5px solid {Colors.PRIMARY_BLUE}; }}
        """)
        mob_layout = QHBoxLayout(self._mobile_container)
        mob_layout.setContentsMargins(0, 0, 0, 0)
        mob_layout.setSpacing(0)
        mob_layout.setDirection(QHBoxLayout.RightToLeft)
        self.lbl_mobile_prefix = QLabel("+963 | 09")
        self.lbl_mobile_prefix.setFixedWidth(ScreenScale.w(90))
        self.lbl_mobile_prefix.setAlignment(Qt.AlignCenter)
        self.lbl_mobile_prefix.setStyleSheet(f"""
            QLabel {{
                color: {Colors.WIZARD_SUBTITLE};
                font-size: 10pt;
                border-left: 1px solid rgba(56,144,223,0.25);
                padding: 0 10px;
                background: transparent;
            }}
        """)
        self.phone = QLineEdit()
        self.phone.setPlaceholderText("xxxxxxxx")
        self.phone.setValidator(QRegExpValidator(QtRegExp(r"\d{0,8}")))
        self.phone.setLayoutDirection(Qt.LeftToRight)
        self.phone.setStyleSheet("""
            QLineEdit {
                border: none; background: transparent;
                padding: 10px 14px; font-size: 10pt; color: #2C3E50;
                min-height: 30px;
            }
        """)
        mob_layout.addWidget(self.lbl_mobile_prefix)
        mob_layout.addWidget(self.phone)
        self._mobile_error = self._err_lbl()
        mob_outer = QVBoxLayout()
        mob_outer.setSpacing(2)
        mob_outer.setContentsMargins(0, 0, 0, 0)
        mob_outer.addWidget(self._mobile_container)
        mob_outer.addWidget(self._mobile_error)
        layout.addLayout(mob_outer)

        # Landline
        _area_codes = [
            ("011", "011 - دمشق"), ("012", "012 - حمص"), ("013", "013 - حماة"),
            ("014", "014 - القنيطرة"), ("015", "015 - درعا"), ("016", "016 - السويداء"),
            ("017", "017 - اللاذقية"), ("018", "018 - طرطوس"), ("021", "021 - حلب"),
            ("022", "022 - الرقة"), ("023", "023 - إدلب"), ("024", "024 - دير الزور"),
            ("052", "052 - الحسكة"),
        ]
        self.lbl_phone = self._lbl(tr("wizard.person_dialog.phone"))
        layout.addWidget(self.lbl_phone)
        self._landline_container = QFrame()
        self._landline_container.setStyleSheet(f"""
            QFrame {{
                border: 1.5px solid #D0D7E2;
                border-radius: 10px;
                background-color: #f0f7ff;
            }}
            QFrame:focus-within {{ border: 1.5px solid {Colors.PRIMARY_BLUE}; }}
        """)
        land_layout = QHBoxLayout(self._landline_container)
        land_layout.setContentsMargins(0, 0, 0, 0)
        land_layout.setSpacing(0)
        land_layout.setDirection(QHBoxLayout.RightToLeft)
        self.landline_prefix = RtlCombo()
        self.landline_prefix.setFixedWidth(ScreenScale.w(130))
        for _code, _display in _area_codes:
            self.landline_prefix.addItem(_display, _code)
        self.landline_prefix.setStyleSheet(f"""
            QComboBox {{
                border: none;
                background: transparent;
                padding: 0 4px 0 8px;
                font-size: 10pt;
                color: {Colors.WIZARD_SUBTITLE};
            }}
            QComboBox QLineEdit {{
                border: none;
                background: transparent;
                padding: 0;
                font-size: 10pt;
                color: {Colors.WIZARD_SUBTITLE};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                border: none;
                width: 18px;
            }}
            QComboBox::down-arrow {{
                width: 8px; height: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #FFFFFF;
                border: 1px solid #D0D7E2;
                border-radius: 8px;
                padding: 4px;
                selection-background-color: #EBF5FF;
                selection-color: #1E293B;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 32px;
                padding: 6px 10px;
                border-radius: 6px;
                color: #1E293B;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #F0F7FF;
            }}
        """)
        _land_sep = QFrame()
        _land_sep.setFrameShape(QFrame.VLine)
        _land_sep.setFixedWidth(1)
        _land_sep.setStyleSheet("background-color: rgba(56,144,223,0.3); border: none; margin: 7px 0;")
        self.landline_digits = QLineEdit()
        self.landline_digits.setPlaceholderText("xxxxxxx")
        self.landline_digits.setValidator(QRegExpValidator(QtRegExp(r"\d{0,7}")))
        self.landline_digits.setLayoutDirection(Qt.LeftToRight)
        self.landline_digits.setStyleSheet("""
            QLineEdit {
                border: none; background: transparent;
                padding: 10px 14px; font-size: 10pt; color: #2C3E50;
                min-height: 30px;
            }
        """)
        land_layout.addWidget(self.landline_prefix)
        land_layout.addWidget(_land_sep)
        land_layout.addWidget(self.landline_digits)
        self._landline_error = self._err_lbl()
        land_outer = QVBoxLayout()
        land_outer.setSpacing(2)
        land_outer.setContentsMargins(0, 0, 0, 0)
        land_outer.addWidget(self._landline_container)
        land_outer.addWidget(self._landline_error)
        layout.addLayout(land_outer)

        self.phone.textChanged.connect(lambda: self._clear_err(self.phone, self._mobile_error))
        self.landline_digits.textChanged.connect(lambda: self._clear_err(self.landline_digits, self._landline_error))

        return layout

    def _build_visit_section(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.in_person_check = QCheckBox(tr("wizard.applicant.in_person"))
        self.in_person_check.setFont(create_font(size=FontManager.WIZARD_CARD_LABEL, weight=FontManager.WEIGHT_REGULAR))
        self.in_person_check.setStyleSheet(f"color: {Colors.WIZARD_TITLE}; background: transparent;")
        self.in_person_check.setChecked(True)
        layout.addWidget(self.in_person_check)
        layout.addStretch()

        return layout

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
        container.setFixedSize(ScreenScale.w(52), ScreenScale.h(52))
        container.setStyleSheet("border: none; background: transparent;")

        thumb = QLabel(container)
        thumb.setFixedSize(ScreenScale.w(48), ScreenScale.h(48))
        thumb.move(4, 4)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("""
            QLabel {
                border: 1px solid #DBEAFE; border-radius: 8px;
                background-color: #F8FAFF;
            }
        """)
        thumb.setCursor(Qt.PointingHandCursor)
        px = QPixmap(file_path)
        if not px.isNull():
            thumb.setPixmap(px.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            thumb.setText("PDF")
            thumb.setStyleSheet(thumb.styleSheet() + "font-size: 9pt; color: #64748B;")

        def _open_file(event, fp=file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(fp))
        thumb.mousePressEvent = _open_file

        x_btn = QLabel(container)
        x_btn.setFixedSize(ScreenScale.w(18), ScreenScale.h(18))
        x_btn.move(0, 0)
        x_btn.setText("\u2715")
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

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(create_font(size=9, weight=FontManager.WEIGHT_SEMIBOLD))
        lbl.setStyleSheet("color: #64748B; background: transparent; border: none;")
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
        frame.setMinimumHeight(ScreenScale.h(60))
        frame.setStyleSheet(f"""
            QFrame#{obj_name} {{
                border: 2px dashed rgba(56, 144, 223, 0.35);
                border-radius: 12px;
                background-color: #F8FAFF;
            }}
            QFrame#{obj_name}:hover {{
                border-color: rgba(56, 144, 223, 0.6);
                background-color: #EBF5FF;
            }}
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(16, 10, 16, 10)
        frame_layout.setSpacing(8)

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        thumbnails_container = QWidget()
        thumbnails_container.setStyleSheet("border: none; background: transparent;")
        thumbnails_layout = QHBoxLayout(thumbnails_container)
        thumbnails_layout.setContentsMargins(0, 0, 0, 0)
        thumbnails_layout.setSpacing(6)
        row_layout.addWidget(thumbnails_container)
        row_layout.addStretch()

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(ScreenScale.w(24), ScreenScale.h(24))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        up_px = Icon.load_pixmap("upload_file", size=22)
        if up_px and not up_px.isNull():
            icon_lbl.setPixmap(up_px)
        else:
            icon_lbl.setText("+")
            icon_lbl.setStyleSheet("border: none; font-size: 18px; color: #3890DF; background: transparent;")
        icon_lbl.setCursor(Qt.PointingHandCursor)
        icon_lbl.mousePressEvent = lambda e: browse_callback()
        row_layout.addWidget(icon_lbl)

        text_btn = QPushButton(button_text or tr("wizard.person_dialog.attach_id_photos"))
        text_btn.setStyleSheet("""
            QPushButton {
                color: #3890DF; text-decoration: underline;
                border: none; background: transparent;
                font-size: 10pt; font-weight: 600; padding: 0px;
            }
            QPushButton:hover { color: #2E7BD6; }
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
                border-radius: 10px;
                padding: 8px 14px;
                background-color: #FFF5F5;
                color: #2C3E50;
                font-size: 10pt;
                min-height: 30px;
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

        # 1. Local validation
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

        phone_text = self.phone.text().strip()
        if phone_text and len(phone_text) != 8:
            self._set_err(self.phone, self._mobile_error)
            result.add_error(tr("wizard.applicant.mobile_8_digits"))

        landline_digits = self.landline_digits.text().strip()
        if landline_digits and len(landline_digits) != 7:
            self._set_err(self.landline_digits, self._landline_error)
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
            # 5. Call API
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

            # 6. Upload ID photos
            person_id = self.context.get_data("contact_person_id")
            if person_id and self.uploaded_files:
                already_uploaded = set(self.context.get_data("uploaded_id_photos") or [])
                new_files = [f for f in self.uploaded_files if f not in already_uploaded]
                for fp in new_files:
                    try:
                        doc_type = self._id_doc_type_combo.currentData() if hasattr(self, '_id_doc_type_combo') else None
                        self._api_client.upload_identification_document(
                            survey_id=survey_id,
                            person_id=person_id,
                            file_path=fp,
                            document_type=doc_type,
                        )
                        already_uploaded.add(fp)
                        logger.info(f"ID photo uploaded: {os.path.basename(fp)}")
                    except Exception as e:
                        logger.error(f"Failed to upload ID photo {fp}: {e}")
                        Toast.show_toast(self, tr("wizard.applicant.load_failed"), Toast.ERROR)
                self.context.update_data("uploaded_id_photos", list(already_uploaded))

            # 7. Cache contact person locally
            self._save_contact_person_locally(survey_id)

            # 8. Save intervieweeName
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

        y = self.birth_year_combo.currentData()
        m = self.birth_month_combo.currentData()
        d = self.birth_day_combo.currentData()
        birth_date = None
        if y:
            month = m if m else 1
            day = d if d else 1
            birth_date = f"{y:04d}-{month:02d}-{day:02d}"
        raw = self.phone.text().strip()

        if raw:
            full_mobile = f"09{raw}"
        else:
            full_mobile = ""
        data = {
            "first_name_ar":  fn,
            "father_name_ar": fat,
            "mother_name_ar": self.mother_name.text().strip(),
            "last_name_ar":   ln,
            "birth_date":     birth_date,
            "gender":         self.gender.currentData(),
            "nationality":    self.nationality.currentData(),
            "national_id":    self.national_id.text().strip(),

        
            "phone":          full_mobile,      
            "landline":       (self.landline_prefix.currentData() + self.landline_digits.text().strip()) if self.landline_digits.text().strip() else "",

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
                      self.mother_name, self.national_id, self.phone]:
            field.clear()
        self.landline_digits.clear()
        self.landline_prefix.setCurrentIndex(0)
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
        elif phone_val.startswith("+963"):
            phone_val = phone_val[4:]
        self.phone.setText(phone_val)
        _land_val = a.get("landline", "")
        if len(_land_val) == 10 and _land_val[0] == '0':
            _idx = self.landline_prefix.findData(_land_val[:3])
            self.landline_prefix.setCurrentIndex(_idx if _idx >= 0 else 0)
            self.landline_digits.setText(_land_val[3:])
        else:
            self.landline_digits.setText(_land_val)
        self.in_person_check.setChecked(a.get("in_person", True))

        photos = a.get("id_photo_paths", [])
        self.uploaded_files = list(photos)
        if photos:
            self._update_upload_thumbnails("id_upload", photos)
        else:
            self._download_id_photos_from_api()

    def _download_id_photos_from_api(self):
        """Download ID photos from server when resuming a draft (local paths gone)."""
        import tempfile
        from services.api_worker import ApiWorker

        applicant = self.context.applicant or {}
        evidences = applicant.get("id_photo_evidences", [])

        person_id = self.context.get_data("contact_person_id")
        if not evidences and not person_id:
            return

        self._set_auth_token()

        def _do_fetch():
            from utils.helpers import download_evidence_file
            docs = evidences
            if not docs and person_id:
                docs = self._api_client.get_person_identification_documents(person_id)
            if not docs:
                return []
            downloaded = []
            for doc in docs:
                ev_id = doc.get("id") or doc.get("evidenceId", "")
                if not ev_id:
                    continue
                file_name = doc.get("fileName") or doc.get("originalFileName") or f"{ev_id}.jpg"
                try:
                    result_path = download_evidence_file(ev_id, file_name)
                    if result_path:
                        downloaded.append(result_path)
                except Exception as e:
                    logger.warning(f"Failed to download ID photo {ev_id}: {e}")
            return downloaded

        def _on_done(downloaded):
            if downloaded:
                self.uploaded_files = downloaded
                self.context.update_data("uploaded_id_photos", list(set(downloaded)))
                self._update_upload_thumbnails("id_upload", downloaded)
                logger.info(f"Downloaded {len(downloaded)} ID photos from server")

        def _on_error(msg):
            logger.warning(f"Could not download ID photos from API: {msg}")

        self._id_photo_worker = ApiWorker(_do_fetch)
        self._id_photo_worker.finished.connect(_on_done)
        self._id_photo_worker.error.connect(_on_error)
        self._id_photo_worker.start()

    def update_language(self, is_arabic: bool):
        self.setLayoutDirection(get_layout_direction())

        # Phone/mobile fields must stay LTR for number format
        self._mobile_container.setLayoutDirection(Qt.LeftToRight)
        self.phone.setLayoutDirection(Qt.LeftToRight)
        self._landline_container.setLayoutDirection(Qt.LeftToRight)
        self.landline_digits.setLayoutDirection(Qt.LeftToRight)
        self.landline_prefix.setLayoutDirection(Qt.LeftToRight)

    # Card header
        self.app_title_lbl.setText(tr("wizard.step.applicant_info"))
        self.app_subtitle_lbl.setText(tr("wizard.applicant.card_subtitle"))

    # Section headers
        self.section_personal_header.setText(tr("wizard.section.personal_info"))
        self.section_contact_header.setText(tr("wizard.section.contact_details"))
        self.section_visit_header.setText(tr("wizard.section.visit_type"))
        self.section_id_header.setText(tr("wizard.section.id_photos"))

    # Personal section labels
        self.lbl_first_name.setText(tr("wizard.person_dialog.first_name") + " *")
        self.lbl_father_name.setText(tr("wizard.person_dialog.father_name") + " *")
        self.lbl_last_name.setText(tr("wizard.person_dialog.last_name") + " *")
        self.lbl_mother_name.setText(tr("wizard.person_dialog.mother_name") + " *")
        self.lbl_birth_date.setText(tr("wizard.person_dialog.birth_date"))
        self.lbl_gender.setText(tr("wizard.person_dialog.gender"))
        self.lbl_nationality.setText(tr("wizard.person_dialog.nationality"))
        self.lbl_national_id.setText(tr("wizard.person_dialog.national_id"))

    # Personal placeholders
        self.first_name.setPlaceholderText(tr("wizard.person_dialog.first_name_placeholder"))
        self.father_name.setPlaceholderText(tr("wizard.person_dialog.father_name_placeholder"))
        self.last_name.setPlaceholderText(tr("wizard.person_dialog.last_name_placeholder"))
        self.mother_name.setPlaceholderText(tr("wizard.person_dialog.mother_name_placeholder"))
        self.national_id.setPlaceholderText("00000000000")

    # Contact section labels
        
        self.lbl_mobile.setText(tr("wizard.person_dialog.mobile"))
        self.lbl_phone.setText(tr("wizard.person_dialog.phone"))

        self.phone.setPlaceholderText("00000000")
        self.landline_digits.setPlaceholderText("xxxxxxx")

    # Visit section
        
        self.section_visit_header.setText(tr("wizard.section.visit_type"))
        self.in_person_check.setText(tr("wizard.applicant.in_person"))

    # ID Photos section
        
        self.section_id_header.setText(tr("wizard.section.id_photos"))
        self.lbl_id_doc_type.setText(tr("wizard.person_dialog.id_document_type"))
        self._id_upload_frame._text_btn.setText(tr("wizard.person_dialog.attach_id_photos"))

    # Refill ID document type combo
        self._id_doc_type_combo.clear()

        from services.display_mappings import get_identification_document_type_options
        for code, label in get_identification_document_type_options():
            if code == 0:
                continue
            self._id_doc_type_combo.addItem(label, code)
    # Refill gender combo
        current_gender = self.gender.currentData()  # حفظ القيمة الحالية
        self.gender.clear()
        self.gender.addItem(tr("wizard.person_dialog.select"), None)

        from services.display_mappings import get_gender_options
        for code, label in get_gender_options():
            self.gender.addItem(label, code)

        # إعادة اختيار القيمة السابقة إذا كانت موجودة
        if current_gender is not None:
            index = self.gender.findData(current_gender)
            if index >= 0:
                self.gender.setCurrentIndex(index)
        # Refill nationality combo
        current_nat = self.nationality.currentData()
        self.nationality.clear()
        self.nationality.addItem(tr("wizard.person_dialog.select"), None)

        from services.display_mappings import get_nationality_options
        for code, label in get_nationality_options():
            self.nationality.addItem(label, code)

        if current_nat is not None:
            index = self.nationality.findData(current_nat)
            if index >= 0:
                self.nationality.setCurrentIndex(index)


    def get_name(self) -> str:
        return tr("wizard.step.applicant_info")
