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
    QGridLayout, QCheckBox, QSizePolicy, QRadioButton, QButtonGroup,
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
    make_editable_date_combo, read_int_from_combo,
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

        content = QWidget()
        content.setStyleSheet("background: transparent;")

        outer_grid = QGridLayout(content)
        outer_grid.setContentsMargins(0, 0, 0, 0)
        outer_grid.setHorizontalSpacing(ScreenScale.w(12))
        outer_grid.setVerticalSpacing(ScreenScale.h(12))
        outer_grid.setColumnStretch(0, 1)
        outer_grid.setColumnStretch(1, 1)

        outer_grid.addWidget(self._build_card_a(), 0, 0)
        outer_grid.addWidget(self._build_card_b(), 0, 1)

        scroll.setWidget(content)
        self.main_layout.addWidget(scroll)

        self._spinner = LoadingSpinnerOverlay(self)

    def _build_card_a(self) -> QFrame:
        card = make_step_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(ScreenScale.h(10))

        header_layout, self.app_title_lbl, self.app_subtitle_lbl = make_icon_header(
            title=tr("wizard.step.applicant_info"),
            subtitle=tr("wizard.applicant.card_subtitle"),
            icon_name="user",
        )
        card_layout.addLayout(header_layout)
        card_layout.addWidget(make_divider())

        self.section_personal_header = make_sub_section_header(tr("wizard.section.personal_info"))
        card_layout.addWidget(self.section_personal_header)
        card_layout.addLayout(self._build_personal_section())

        self.section_visit_header = make_sub_section_header(tr("wizard.section.visit_type"))
        self.section_visit_header.hide()

        self.in_person_check = QCheckBox()
        self.in_person_check.setChecked(True)
        self.in_person_check.hide()

        card_layout.addStretch()

        return card

    def _build_card_b(self) -> QFrame:
        card = make_step_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(ScreenScale.h(10))

        self.section_contact_header = make_sub_section_header(tr("wizard.section.contact_details"))
        card_layout.addWidget(self.section_contact_header)
        card_layout.addLayout(self._build_contact_section())

        card_layout.addSpacing(ScreenScale.h(4))
        card_layout.addWidget(make_divider())

        self.section_id_header = make_sub_section_header(tr("wizard.section.id_photos"))
        card_layout.addWidget(self.section_id_header)

        doc_type_row = QHBoxLayout()
        doc_type_row.setContentsMargins(0, 0, 0, 4)
        self.lbl_id_doc_type = QLabel(tr("wizard.person_dialog.id_document_type"))
        self.lbl_id_doc_type.setStyleSheet("color: #5A6B7F; font-weight: 600; font-size: 12px;")
        self._id_doc_type_combo = QComboBox()
        self._id_doc_type_combo.setFocusPolicy(Qt.ClickFocus)
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
                outline: none;
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
        card_layout.addStretch()

        return card

    def _build_personal_section(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(ScreenScale.w(10))
        grid.setVerticalSpacing(ScreenScale.h(8))
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        _name_v = QRegExpValidator(QtRegExp("[\u0600-\u06FFa-zA-Z\\s.\\-']+"))
        row = 0

        # Row 0 labels: الاسم الأول | اسم الأب | الكنية
        self.lbl_first_name  = self._lbl(tr("wizard.person_dialog.first_name")  + " *")
        self.lbl_father_name = self._lbl(tr("wizard.person_dialog.father_name") + " *")
        self.lbl_last_name   = self._lbl(tr("wizard.person_dialog.last_name")   + " *")
        grid.addWidget(self.lbl_first_name,  row, 0)
        grid.addWidget(self.lbl_father_name, row, 1)
        grid.addWidget(self.lbl_last_name,   row, 2)
        row += 1

        self.first_name  = self._field(tr("wizard.person_dialog.first_name_placeholder"),  _name_v)
        self.father_name = self._field(tr("wizard.person_dialog.father_name_placeholder"), _name_v)
        self.last_name   = self._field(tr("wizard.person_dialog.last_name_placeholder"),   _name_v)
        self._first_name_error  = self._err_lbl()
        self._father_name_error = self._err_lbl()
        self._last_name_error   = self._err_lbl()
        grid.addLayout(self._field_box(self.first_name,  self._first_name_error),  row, 0)
        grid.addLayout(self._field_box(self.father_name, self._father_name_error), row, 1)
        grid.addLayout(self._field_box(self.last_name,   self._last_name_error),   row, 2)
        row += 1

        # Row 2 labels: اسم الأم | تاريخ الميلاد (col_span=2)
        self.lbl_mother_name = self._lbl(tr("wizard.person_dialog.mother_name") + " *")
        self.lbl_birth_date  = self._lbl(tr("wizard.person_dialog.birth_date"))
        grid.addWidget(self.lbl_mother_name, row, 0)
        grid.addWidget(self.lbl_birth_date,  row, 1, 1, 2)
        row += 1

        self.mother_name = self._field(tr("wizard.person_dialog.mother_name_placeholder"), _name_v)
        self._mother_name_error = self._err_lbl()
        grid.addLayout(self._field_box(self.mother_name, self._mother_name_error), row, 0)

        birth_layout = QHBoxLayout()
        birth_layout.setSpacing(6)
        birth_layout.setContentsMargins(0, 0, 0, 0)
        self.birth_day_combo = make_editable_date_combo(
            items=[(str(d), d) for d in range(1, 32)],
            max_digits=2, placeholder=tr("wizard.person_dialog.day_placeholder"),
        )
        self.birth_month_combo = make_editable_date_combo(
            items=[(str(m), m) for m in range(1, 13)],
            max_digits=2, placeholder=tr("wizard.person_dialog.month_placeholder"),
        )
        self.birth_year_combo = make_editable_date_combo(
            items=[(str(y), y) for y in range(2010, 1919, -1)],
            max_digits=4, placeholder=tr("wizard.person_dialog.year_placeholder"),
        )
        birth_layout.addWidget(self.birth_day_combo, 1)
        birth_layout.addWidget(self.birth_month_combo, 1)
        birth_layout.addWidget(self.birth_year_combo, 2)
        birth_container = QWidget()
        birth_container.setStyleSheet("background-color: transparent;")
        birth_container.setLayout(birth_layout)
        grid.addWidget(birth_container, row, 1, 1, 2)
        row += 1

        # Row 4 labels: الجنسية | الرقم الوطني | الجنس
        self.lbl_nationality = self._lbl(tr("wizard.person_dialog.nationality"))
        self.lbl_national_id = self._lbl(tr("wizard.person_dialog.national_id") + " *")
        self.lbl_gender      = self._lbl(tr("wizard.person_dialog.gender"))
        grid.addWidget(self.lbl_nationality, row, 0)
        grid.addWidget(self.lbl_national_id, row, 1)
        grid.addWidget(self.lbl_gender,      row, 2)
        row += 1

        self.nationality = RtlCombo()
        self.nationality.setFocusPolicy(Qt.ClickFocus)
        self.nationality.addItem(tr("wizard.person_dialog.select"), None)

        for code, display_name in get_nationality_options():
            self.nationality.addItem(display_name, code)
        self.nationality.setStyleSheet(self._input_style())
        grid.addWidget(self.nationality, row, 0)

        self.national_id = self._field("0000000000", QRegExpValidator(QtRegExp(r"\d{0,11}")))
        self._nid_error = self._err_lbl()
        grid.addLayout(self._field_box(self.national_id, self._nid_error), row, 1)

        self.gender = self._build_gender_radios()
        grid.addWidget(self.gender, row, 2)

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
        self._mobile_container.setLayoutDirection(Qt.LeftToRight)
        mob_layout = QHBoxLayout(self._mobile_container)
        mob_layout.setContentsMargins(0, 0, 0, 0)
        mob_layout.setSpacing(0)
        self.lbl_mobile_prefix = QLabel("+963 | 09")
        self.lbl_mobile_prefix.setFixedWidth(ScreenScale.w(90))
        self.lbl_mobile_prefix.setAlignment(Qt.AlignCenter)
        self.lbl_mobile_prefix.setStyleSheet(f"""
            QLabel {{
                color: {Colors.WIZARD_SUBTITLE};
                font-size: 10pt;
                border-right: 1px solid rgba(56,144,223,0.25);
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
        self._landline_container.setLayoutDirection(Qt.LeftToRight)
        land_layout = QHBoxLayout(self._landline_container)
        land_layout.setContentsMargins(0, 0, 0, 0)
        land_layout.setSpacing(0)
        self.lbl_landline_prefix = QLabel("0")
        self.lbl_landline_prefix.setFixedWidth(ScreenScale.w(40))
        self.lbl_landline_prefix.setAlignment(Qt.AlignCenter)
        self.lbl_landline_prefix.setStyleSheet(f"""
            QLabel {{
                color: {Colors.WIZARD_SUBTITLE};
                font-size: 10pt;
                border-right: 1px solid rgba(56,144,223,0.25);
                padding: 0 10px;
                background: transparent;
            }}
        """)
        self.landline_digits = QLineEdit()
        self.landline_digits.setPlaceholderText("xxxxxxxxx")
        self.landline_digits.setValidator(QRegExpValidator(QtRegExp(r"\d{0,9}")))
        self.landline_digits.setLayoutDirection(Qt.LeftToRight)
        self.landline_digits.setStyleSheet("""
            QLineEdit {
                border: none; background: transparent;
                padding: 10px 14px; font-size: 10pt; color: #2C3E50;
                min-height: 30px;
            }
        """)
        land_layout.addWidget(self.lbl_landline_prefix)
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
        lbl.setFont(create_font(size=10, weight=FontManager.WEIGHT_BOLD))
        lbl.setStyleSheet("color: #1E293B; background: transparent; border: none;")
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

    # Editable birth combos + gender radios

    def _make_editable_combo(self, items, max_digits: int, placeholder: str = "") -> QComboBox:
        combo = QComboBox()
        combo.setLayoutDirection(Qt.LeftToRight)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        for label, data in items:
            combo.addItem(label, data)
        line_edit = combo.lineEdit()
        if line_edit is not None:
            line_edit.setValidator(QRegExpValidator(QtRegExp(rf"\d{{0,{max_digits}}}")))
            line_edit.setAlignment(Qt.AlignCenter)
            if placeholder:
                line_edit.setPlaceholderText(placeholder)
        combo.setCurrentIndex(-1)
        combo.clearEditText()
        combo.setStyleSheet(self._input_style())
        return combo

    @staticmethod
    def _read_int_from_combo(combo: QComboBox):
        val = combo.currentData()
        if val is not None:
            return val
        text = combo.currentText().strip()
        if text.isdigit():
            try:
                return int(text)
            except ValueError:
                return None
        return None

    def _build_gender_radios(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(container)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(ScreenScale.w(16))

        self._gender_group = QButtonGroup(container)
        self._gender_group.setExclusive(True)
        self._gender_btns = []

        radio_css = f"""
            QRadioButton {{
                color: {Colors.WIZARD_TITLE};
                background: transparent;
                font-size: 10pt;
                spacing: 6px;
                padding: 2px 4px;
            }}
            QRadioButton::indicator {{
                width: 16px; height: 16px;
                border: 1.5px solid #B0BEC5;
                border-radius: 9px;
                background: white;
            }}
            QRadioButton::indicator:checked {{
                border: 1.5px solid {Colors.PRIMARY_BLUE};
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                    stop:0 {Colors.PRIMARY_BLUE}, stop:0.55 {Colors.PRIMARY_BLUE},
                    stop:0.6 white, stop:1 white);
            }}
        """
        for code, label in get_gender_options():
            btn = QRadioButton(label)
            btn.setStyleSheet(radio_css)
            btn.setProperty("gender_code", code)
            btn.setProperty("gender_label", label)
            lay.addWidget(btn)
            self._gender_group.addButton(btn)
            self._gender_btns.append(btn)
        lay.addStretch()
        return container

    def _get_gender(self):
        for btn in getattr(self, "_gender_btns", []):
            if btn.isChecked():
                return btn.property("gender_code")
        return None

    def _set_gender(self, code):
        for btn in getattr(self, "_gender_btns", []):
            if btn.property("gender_code") == code:
                btn.setChecked(True)
                return
        self._gender_group.setExclusive(False)
        for btn in getattr(self, "_gender_btns", []):
            btn.setChecked(False)
        self._gender_group.setExclusive(True)

    def _refill_gender_radios(self):
        options = list(get_gender_options())
        current = self._get_gender()
        for btn, (code, label) in zip(self._gender_btns, options):
            btn.setText(label)
            btn.setProperty("gender_code", code)
            btn.setProperty("gender_label", label)
        if current is not None:
            self._set_gender(current)

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
        if landline_digits and len(landline_digits) != 9:
            self._set_err(self.landline_digits, self._landline_error)
            result.add_error(tr("wizard.applicant.landline_9_digits"))

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

        y = read_int_from_combo(self.birth_year_combo)
        m = read_int_from_combo(self.birth_month_combo)
        d = read_int_from_combo(self.birth_day_combo)
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
            "gender":         self._get_gender(),
            "nationality":    self.nationality.currentData(),
            "national_id":    self.national_id.text().strip(),

        
            "phone":          full_mobile,      
            "landline":       ("0" + self.landline_digits.text().strip()) if self.landline_digits.text().strip() else "",

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
        for c in (self.birth_year_combo, self.birth_month_combo, self.birth_day_combo):
            c.setCurrentIndex(-1)
            c.clearEditText()
        self._set_gender(None)
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

        self._set_gender(a.get("gender"))

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
        if _land_val.startswith("0"):
            self.landline_digits.setText(_land_val[1:])
        else:
            self.landline_digits.setText(_land_val)
        self.in_person_check.setChecked(a.get("in_person", True))

        import os as _os
        photos = a.get("id_photo_paths", [])
        valid_photos = [p for p in photos if p and _os.path.exists(p)]
        self.uploaded_files = list(valid_photos)
        if valid_photos:
            self._update_upload_thumbnails("id_upload", valid_photos)
        elif photos:
            # Had photos in draft but local temp files are gone — fetch from server
            self._download_id_photos_from_api()

    def _download_id_photos_from_api(self):
        """Download ID photos from server when resuming a draft (local paths gone)."""
        import tempfile
        from services.api_worker import ApiWorker

        applicant = self.context.applicant or {}
        evidences = applicant.get("id_photo_evidences", [])

        person_id = self.context.get_data("contact_person_id")
        survey_id = self.context.get_data("survey_id") or ""
        if not evidences and not person_id and not survey_id:
            return

        self._set_auth_token()

        def _do_fetch():
            from utils.helpers import (
                download_evidence_file,
                download_static_file,
                download_identification_document_file,
            )
            docs = list(evidences)
            if not docs and person_id:
                try:
                    docs = self._api_client.get_person_identification_documents(person_id)
                except Exception as e:
                    logger.warning(f"get_person_identification_documents failed: {e}")
            if not docs and survey_id:
                try:
                    docs = self._api_client.get_survey_evidences(survey_id, evidence_type="identification")
                except Exception as e:
                    logger.warning(f"get_survey_evidences fallback failed: {e}")
            if not docs:
                return []
            downloaded = []
            for doc in docs:
                ev_id = doc.get("id") or doc.get("evidenceId", "")
                doc_person_id = doc.get("personId") or person_id
                file_name = (
                    doc.get("originalFileName")
                    or doc.get("fileName")
                    or f"{ev_id}.jpg"
                )
                file_path_val = doc.get("filePath") or doc.get("file_path") or ""
                try:
                    result_path = None
                    # 1) New dedicated endpoint (preferred when both ids known).
                    if doc_person_id and ev_id:
                        result_path = download_identification_document_file(
                            doc_person_id, ev_id, file_name
                        )
                    # 2) Legacy static-file path fallback.
                    if not result_path and file_path_val:
                        result_path = download_static_file(file_path_val, file_name)
                    # 3) Generic evidence endpoint fallback.
                    if not result_path and ev_id:
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

    # Birth date placeholders
        for combo, key in (
            (self.birth_day_combo,   "wizard.person_dialog.day_placeholder"),
            (self.birth_month_combo, "wizard.person_dialog.month_placeholder"),
            (self.birth_year_combo,  "wizard.person_dialog.year_placeholder"),
        ):
            le = combo.lineEdit()
            if le is not None:
                le.setPlaceholderText(tr(key))

    # Contact section labels
        
        self.lbl_mobile.setText(tr("wizard.person_dialog.mobile"))
        self.lbl_phone.setText(tr("wizard.person_dialog.phone"))

        self.phone.setPlaceholderText("00000000")
        self.landline_digits.setPlaceholderText("xxxxxxxxx")

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
    # Refill gender radio buttons
        self._refill_gender_radios()
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
