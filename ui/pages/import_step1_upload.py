# -*- coding: utf-8 -*-
"""
Import Wizard - Step 1: Upload .uhc File
UC-003: Import Pipeline

Select and upload a .uhc package file for import processing.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QProgressBar, QFileDialog, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal

from ui.design_system import Colors, PageDimensions
from ui.font_utils import create_font, FontManager
from ui.style_manager import StyleManager
from utils.logger import get_logger

logger = get_logger(__name__)


class ImportStep1Upload(QWidget):
    """Step 1: Select and upload .uhc file."""

    file_uploaded = pyqtSignal(str)  # package_id

    def __init__(self, import_controller, parent=None):
        super().__init__(parent)
        self.import_controller = import_controller
        self._selected_file_path = None
        self._setup_ui()

    def _setup_ui(self):
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("background: transparent;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 24, 0, 0)
        main_layout.setSpacing(20)

        # Upload card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(20)

        # Title
        title = QLabel("رفع ملف .uhc")
        title.setFont(create_font(size=14, weight=FontManager.WEIGHT_SEMIBOLD))
        title.setStyleSheet("color: #212B36; background: transparent;")
        card_layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E1E8ED;")
        card_layout.addWidget(sep)

        # Drop zone
        self._drop_zone = QFrame()
        self._drop_zone.setMinimumHeight(180)
        self._drop_zone.setStyleSheet("""
            QFrame {
                background-color: #F8FAFF;
                border: 2px dashed #C4CDD5;
                border-radius: 12px;
            }
        """)
        drop_layout = QVBoxLayout(self._drop_zone)
        drop_layout.setContentsMargins(24, 24, 24, 24)
        drop_layout.setSpacing(12)
        drop_layout.setAlignment(Qt.AlignCenter)

        # Drop zone icon placeholder
        drop_icon = QLabel("📂")
        drop_icon.setFont(create_font(size=24, weight=FontManager.WEIGHT_REGULAR))
        drop_icon.setAlignment(Qt.AlignCenter)
        drop_icon.setStyleSheet("background: transparent; border: none;")
        drop_layout.addWidget(drop_icon)

        drop_label = QLabel("اسحب الملف هنا أو اضغط لاختيار ملف")
        drop_label.setFont(create_font(size=11, weight=FontManager.WEIGHT_REGULAR))
        drop_label.setStyleSheet("color: #637381; background: transparent; border: none;")
        drop_label.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(drop_label)

        drop_hint = QLabel("يُقبل فقط ملفات بصيغة .uhc")
        drop_hint.setFont(create_font(size=9, weight=FontManager.WEIGHT_REGULAR))
        drop_hint.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
        drop_hint.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(drop_hint)

        card_layout.addWidget(self._drop_zone)

        # File path label
        self._file_path_label = QLabel("")
        self._file_path_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._file_path_label.setStyleSheet("color: #212B36; background: transparent;")
        self._file_path_label.setWordWrap(True)
        self._file_path_label.setVisible(False)
        card_layout.addWidget(self._file_path_label)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._choose_btn = QPushButton("اختيار ملف")
        self._choose_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._choose_btn.setFixedSize(160, 44)
        self._choose_btn.setCursor(Qt.PointingHandCursor)
        self._choose_btn.setStyleSheet("""
            QPushButton {
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #2A7BC9;
            }
            QPushButton:disabled {
                background-color: #BDC3C7;
            }
        """)
        self._choose_btn.clicked.connect(self._on_choose_file)
        btn_row.addWidget(self._choose_btn)

        self._upload_btn = QPushButton("رفع الملف")
        self._upload_btn.setFont(create_font(size=10, weight=FontManager.WEIGHT_SEMIBOLD))
        self._upload_btn.setFixedSize(160, 44)
        self._upload_btn.setCursor(Qt.PointingHandCursor)
        self._upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:disabled {
                background-color: #BDC3C7;
            }
        """)
        self._upload_btn.setEnabled(False)
        self._upload_btn.clicked.connect(self._on_upload)
        btn_row.addWidget(self._upload_btn)

        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        # Progress bar (hidden initially)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E5E7EB;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #3890DF;
                border-radius: 4px;
            }
        """)
        card_layout.addWidget(self._progress_bar)

        # Status message
        self._status_label = QLabel("")
        self._status_label.setFont(create_font(size=10, weight=FontManager.WEIGHT_REGULAR))
        self._status_label.setStyleSheet("color: #637381; background: transparent;")
        self._status_label.setVisible(False)
        card_layout.addWidget(self._status_label)

        main_layout.addWidget(card)
        main_layout.addStretch()

    def _on_choose_file(self):
        """Open file dialog to select a .uhc file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "اختيار ملف .uhc",
            "",
            "UHC Files (*.uhc);;All Files (*)"
        )
        if file_path:
            self._selected_file_path = file_path
            self._file_path_label.setText(f"الملف: {file_path}")
            self._file_path_label.setVisible(True)
            self._upload_btn.setEnabled(True)

            # Update drop zone appearance
            self._drop_zone.setStyleSheet("""
                QFrame {
                    background-color: #ECFDF5;
                    border: 2px dashed #A7F3D0;
                    border-radius: 12px;
                }
            """)

            self._status_label.setText("تم اختيار الملف. اضغط 'رفع الملف' للمتابعة.")
            self._status_label.setStyleSheet("color: #059669; background: transparent;")
            self._status_label.setVisible(True)

            logger.info(f"File selected: {file_path}")

    def _on_upload(self):
        """Upload the selected file."""
        if not self._selected_file_path:
            return

        self._set_uploading(True)

        result = self.import_controller.upload_package(self._selected_file_path)

        self._set_uploading(False)

        if result.success:
            pkg_id = ""
            if result.data:
                pkg_id = result.data.get("id") or result.data.get("packageId") or ""

            self._status_label.setText(result.message_ar or "تم رفع الملف بنجاح")
            self._status_label.setStyleSheet("color: #059669; background: transparent;")
            self._status_label.setVisible(True)

            logger.info(f"Upload succeeded, package_id={pkg_id}")
            self.file_uploaded.emit(pkg_id)
        else:
            self._status_label.setText(result.message_ar or "فشل رفع الملف")
            self._status_label.setStyleSheet("color: #EF4444; background: transparent;")
            self._status_label.setVisible(True)

            logger.error(f"Upload failed: {result.message}")

    def _set_uploading(self, uploading: bool):
        """Toggle uploading state."""
        self._progress_bar.setVisible(uploading)
        self._choose_btn.setEnabled(not uploading)
        self._upload_btn.setEnabled(not uploading)

        if uploading:
            self._status_label.setText("جاري رفع الملف...")
            self._status_label.setStyleSheet("color: #3890DF; background: transparent;")
            self._status_label.setVisible(True)

    def reset(self):
        """Reset the step to initial state."""
        self._selected_file_path = None
        self._file_path_label.setText("")
        self._file_path_label.setVisible(False)
        self._upload_btn.setEnabled(False)
        self._progress_bar.setVisible(False)
        self._status_label.setText("")
        self._status_label.setVisible(False)
        self._drop_zone.setStyleSheet("""
            QFrame {
                background-color: #F8FAFF;
                border: 2px dashed #C4CDD5;
                border-radius: 12px;
            }
        """)
