# -*- coding: utf-8 -*-
"""
Reference Data Management Page — صفحة إدارة البيانات المرجعية
Vocabulary management, glossary, and support info.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QTextEdit, QLineEdit,
    QInputDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QTextCharFormat, QColor

from ui.components.icon import Icon
from ui.design_system import Colors, PageDimensions
from ui.style_manager import StyleManager
from ui.font_utils import create_font, FontManager
from ui.components.dialogs.password_dialog import _INPUT_STYLE
from services import vocab_service
from utils.logger import get_logger

logger = get_logger(__name__)

# All vocabulary sections (flat list — accordion pills)
VOCAB_SECTIONS = [
    ("building_type", "نوع المبنى"),
    ("building_status", "حالة المبنى"),
    ("unit_type", "نوع الوحدة"),
    ("relation_type", "نوع العلاقة"),
    ("case_status", "حالة القضية"),
    ("contract_type", "نوع العقد"),
    ("evidence_type", "نوع الوثيقة"),
    ("occupancy_type", "نوع الإشغال"),
    ("occupancy_nature", "طبيعة الإشغال"),
    ("nationality", "الجنسية"),
    ("claim_type", "نوع المطالبة"),
    ("claim_status", "حالة المطالبة"),
    ("case_priority", "أولوية القضية"),
    ("claim_source", "مصدر المطالبة"),
    ("business_nature", "طبيعة النشاط"),
]


class DataManagementPage(QWidget):
    """Page for managing reference data, vocabularies, and support info."""

    def __init__(self, db=None, i18n=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self._vocab_add_btns = {}
        self._vocab_terms_widgets = {}
        self._accordion_contents = {}
        self._accordion_arrows = {}
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(StyleManager.page_background())
        self.setLayoutDirection(Qt.RightToLeft)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_TOP,
            PageDimensions.CONTENT_PADDING_H,
            PageDimensions.CONTENT_PADDING_V_BOTTOM
        )
        main_layout.setSpacing(PageDimensions.HEADER_GAP)

        header = self._create_header()
        main_layout.addWidget(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setLayoutDirection(Qt.RightToLeft)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            + StyleManager.scrollbar()
        )

        scroll_content = QWidget()
        scroll_content.setLayoutDirection(Qt.RightToLeft)
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(20, 0, 0, 0)  # left margin for scrollbar in RTL
        scroll_layout.setSpacing(16)

        # Section 1: Vocabulary management
        self._vocab_card = self._create_vocabulary_card()
        scroll_layout.addWidget(self._vocab_card)

        # Section 2: Glossary - المفردات (claim definition)
        glossary_card = self._create_glossary_card()
        scroll_layout.addWidget(glossary_card)

        # Section 3: About - حول التطبيق
        about_card = self._create_about_card()
        scroll_layout.addWidget(about_card)

        # Section 4: Help & Support
        support_card = self._create_support_card()
        scroll_layout.addWidget(support_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    # --- Header ---

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Title row with button
        title_row = QHBoxLayout()
        title_row.setSpacing(16)

        title = QLabel("إدارة البيانات المرجعية")
        title.setFont(create_font(
            size=FontManager.SIZE_TITLE,
            weight=QFont.Bold,
            letter_spacing=0
        ))
        title.setStyleSheet(StyleManager.label_title())
        title_row.addWidget(title)

        title_row.addStretch()

        # "Ready for sync" button
        sync_btn = QPushButton("  جاهزة للمزامنة")
        sync_btn.setFixedHeight(36)
        sync_btn.setCursor(Qt.PointingHandCursor)
        sync_btn.setFont(create_font(size=FontManager.SIZE_SMALL, weight=QFont.Medium))
        pixmap = Icon.load_pixmap("save", size=14)
        if pixmap and not pixmap.isNull():
            from PyQt5.QtGui import QIcon
            sync_btn.setIcon(QIcon(pixmap))
        sync_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.PRIMARY_BLUE};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: #2D7BC9; }}
            QPushButton:pressed {{ background-color: #2468B0; }}
        """)
        title_row.addWidget(sync_btn)

        layout.addLayout(title_row)

        # Breadcrumb
        breadcrumb_layout = QHBoxLayout()
        breadcrumb_layout.setSpacing(8)
        breadcrumb_layout.setContentsMargins(0, 0, 0, 0)

        subtitle_font = create_font(
            size=FontManager.SIZE_BODY,
            weight=QFont.Normal,
            letter_spacing=0
        )
        style = f"color: {Colors.TEXT_SECONDARY}; border: none; background: transparent;"

        part1 = QLabel("إدارة المستخدمين")
        part1.setFont(subtitle_font)
        part1.setStyleSheet(style)
        breadcrumb_layout.addWidget(part1)

        dot = QLabel("•")
        dot.setFont(subtitle_font)
        dot.setStyleSheet(style)
        breadcrumb_layout.addWidget(dot)

        part2 = QLabel("إدارة البيانات المرجعية")
        part2.setFont(subtitle_font)
        part2.setStyleSheet(style)
        breadcrumb_layout.addWidget(part2)

        breadcrumb_layout.addStretch()
        layout.addLayout(breadcrumb_layout)

        return header

    # --- Section 1: Vocabulary Management ---

    def _create_vocabulary_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("vocabCard")
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet("""
            QFrame#vocabCard {
                background-color: white;
                border-radius: 16px;
                border: none;
            }
        """)
        card.setMaximumWidth(1249)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        # Section title
        section_title = QLabel("إدارة المفردات")
        section_title.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold))
        section_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        section_title.setAlignment(Qt.AlignLeft)
        layout.addWidget(section_title)

        # Accordion sections for each vocabulary
        for i, (key, title) in enumerate(VOCAB_SECTIONS):
            expanded = (i == 0)
            section = self._create_vocab_section(key, title, expanded)
            layout.addWidget(section)

        return card

    def _create_vocab_section(self, key: str, title: str, expanded: bool = False) -> QFrame:
        """Create a collapsible vocabulary section (pill header + chips content)."""
        section = QFrame()
        section.setObjectName(f"vocabSection_{key}")
        section.setStyleSheet(f"QFrame#vocabSection_{key} {{ background: transparent; border: none; }}")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        # Pill header (clickable)
        header = QFrame()
        header.setObjectName(f"vocabHeader_{key}")
        header.setCursor(Qt.PointingHandCursor)
        header.setFixedHeight(48)
        header.setStyleSheet(f"""
            QFrame#vocabHeader_{key} {{
                background-color: #f0f7ff;
                border: 1px solid #E1E8ED;
                border-radius: 20px;
            }}
            QFrame#vocabHeader_{key}:hover {{
                background-color: #E3EEF9;
            }}
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel(title)
        title_label.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Bold))
        title_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        arrow = QLabel("∨" if expanded else "‹")
        arrow.setFont(create_font(size=FontManager.SIZE_SMALL, weight=QFont.Bold))
        arrow.setStyleSheet("color: #637381; background: transparent; border: none;")
        arrow.setFixedWidth(20)
        arrow.setAlignment(Qt.AlignCenter)
        self._accordion_arrows[key] = arrow
        header_layout.addWidget(arrow)

        header.mousePressEvent = lambda e, k=key: self._toggle_accordion(k)
        section_layout.addWidget(header)

        # Content (chips + add button, wrapped in rows)
        content = QWidget()
        content.setObjectName(f"vocabContent_{key}")
        content.setStyleSheet(f"""
            QWidget#vocabContent_{key} {{
                background-color: white;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
            }}
        """)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 8, 16, 12)
        content_layout.setSpacing(6)

        add_btn = QPushButton("اضافة")
        add_btn.setFixedSize(106, 45)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Medium))
        add_btn.setLayoutDirection(Qt.RightToLeft)
        pixmap = Icon.load_pixmap("icon", size=16)
        if pixmap and not pixmap.isNull():
            from PyQt5.QtGui import QIcon
            add_btn.setIcon(QIcon(pixmap))
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #F0F7FF;
                color: {Colors.PRIMARY_BLUE};
                border: 1px solid {Colors.PRIMARY_BLUE};
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #E0EAFF;
                border-color: #2870BF;
            }}
        """)
        add_btn.clicked.connect(lambda _, vn=key: self._on_add_term(vn))

        self._vocab_add_btns[key] = add_btn
        self._accordion_contents[key] = content

        self._populate_vocab_group(key)

        content.setVisible(expanded)
        section_layout.addWidget(content)

        return section

    def _create_term_chip(self, term_label: str, code: int, vocab_name: str) -> QFrame:
        chip = QFrame()
        chip.setLayoutDirection(Qt.RightToLeft)
        chip.setFixedSize(150, 45)
        chip.setStyleSheet("""
            QFrame {
                background-color: #f0f7ff;
                border-radius: 8px;
            }
            QFrame QLabel { border: none; background: transparent; }
        """)

        layout = QHBoxLayout(chip)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # Delete icon (left side in RTL)
        delete_btn = QPushButton()
        delete_btn.setFixedSize(20, 20)
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; }
            QPushButton:hover { background-color: #E5E7EB; border-radius: 4px; }
        """)
        pixmap_del = Icon.load_pixmap("delete", size=14)
        if pixmap_del and not pixmap_del.isNull():
            from PyQt5.QtGui import QIcon
            delete_btn.setIcon(QIcon(pixmap_del))
        delete_btn.clicked.connect(lambda _, c=code, vn=vocab_name: self._on_delete_term(c, vn))
        layout.addWidget(delete_btn)

        # Edit icon
        edit_btn = QPushButton()
        edit_btn.setFixedSize(20, 20)
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; }
            QPushButton:hover { background-color: #E5E7EB; border-radius: 4px; }
        """)
        pixmap_edit = Icon.load_pixmap("edit-01", size=14)
        if pixmap_edit and not pixmap_edit.isNull():
            from PyQt5.QtGui import QIcon
            edit_btn.setIcon(QIcon(pixmap_edit))
        edit_btn.clicked.connect(lambda _, c=code, tl=term_label, vn=vocab_name: self._on_edit_term(c, tl, vn))
        layout.addWidget(edit_btn)

        # Term text (right side in RTL)
        text = QLabel(term_label)
        text.setFont(create_font(size=FontManager.SIZE_SMALL, weight=QFont.Normal))
        text.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
        text.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(text)

        return chip

    def _on_delete_term(self, code: int, vocab_name: str):
        """Delete a vocabulary term after confirmation."""
        from ui.components.dialogs.confirmation_dialog import ConfirmationDialog, DialogResult
        result = ConfirmationDialog.confirm(
            parent=self,
            title="تأكيد الحذف",
            message="هل أنت متأكد من حذف هذا المصطلح؟"
        )
        if result != DialogResult.YES:
            return
        vocab_service.remove_term(vocab_name, code)
        self._delete_term_from_db(vocab_name, code)
        self._populate_vocab_group(vocab_name)

    def _on_edit_term(self, code: int, current_label: str, vocab_name: str):
        """Edit a vocabulary term label."""
        text, ok = QInputDialog.getText(
            self, "تعديل مصطلح", "عدّل المصطلح:",
            QLineEdit.Normal, current_label
        )
        if not ok or not text.strip() or text.strip() == current_label:
            return
        new_label = text.strip()
        vocab_service.update_term(vocab_name, code, new_label, new_label)
        self._update_term_in_db(vocab_name, code, new_label)
        self._populate_vocab_group(vocab_name)

    def _toggle_accordion(self, cat_name: str):
        content = self._accordion_contents.get(cat_name)
        arrow = self._accordion_arrows.get(cat_name)
        if not content or not arrow:
            return
        is_visible = content.isVisible()
        content.setVisible(not is_visible)
        arrow.setText("‹" if is_visible else "∨")

    # --- Section 2: Glossary (Rich Text) ---

    def _create_glossary_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("glossaryCard")
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet("""
            QFrame#glossaryCard {
                background-color: white;
                border-radius: 8px;
            }
        """)
        card.setMaximumWidth(1249)
        card.setFixedHeight(242)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Section title
        section_title = QLabel("المفردات")
        section_title.setFont(create_font(size=12, weight=QFont.Bold))
        section_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(section_title)

        # Rich text toolbar
        toolbar = self._create_rich_text_toolbar()
        layout.addWidget(toolbar)

        # Text editor
        self._glossary_editor = QTextEdit()
        self._glossary_editor.setLayoutDirection(Qt.RightToLeft)
        self._glossary_editor.setAcceptRichText(True)
        self._glossary_editor.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Normal))
        self._glossary_editor.setStyleSheet("""
            QTextEdit {
                background-color: #FAFBFC;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 12px;
                color: #2C3E50;
            }
            QTextEdit:focus { border: 2px solid #3890DF; }
        """)

        self._glossary_editor.setHtml("""
        <div style="text-align: right; direction: rtl;">
            <p style="color: #3B86FF; font-weight: bold;">&#9670; المطالبة (Claim)</p>
            <p>المطالبة هي سجل يتم إنشاؤه داخل النظام لتمثيل علاقة قانونية أو واقعية بين شخص ووحدة عقارية، مثل الملكية أو الإشغال.</p>
            <p>تُستخدم المطالبة لتوثيق الحالة، وربطها بالأشخاص والعقار والوثائق ذات الصلة.</p>
            <br/>
            <p style="color: #666;">A claim is a record created in the system to represent a legal or factual relationship between a person and a property unit, such as ownership or occupancy.</p>
        </div>
        """)

        layout.addWidget(self._glossary_editor)
        return card

    def _create_about_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("aboutCard")
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet("""
            QFrame#aboutCard {
                background-color: white;
                border-radius: 8px;
            }
        """)
        card.setMaximumWidth(1249)
        card.setFixedHeight(242)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Section title
        section_title = QLabel("حول التطبيق")
        section_title.setFont(create_font(size=12, weight=QFont.Bold))
        section_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(section_title)

        # Rich text toolbar
        toolbar = self._create_rich_text_toolbar(editor_attr="_about_editor")
        layout.addWidget(toolbar)

        # Text editor
        self._about_editor = QTextEdit()
        self._about_editor.setLayoutDirection(Qt.RightToLeft)
        self._about_editor.setAcceptRichText(True)
        self._about_editor.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Normal))
        self._about_editor.setStyleSheet("""
            QTextEdit {
                background-color: #FAFBFC;
                border: 1px solid #E1E8ED;
                border-radius: 8px;
                padding: 12px;
                color: #2C3E50;
            }
            QTextEdit:focus { border: 2px solid #3890DF; }
        """)

        self._about_editor.setHtml("""
        <div style="text-align: right; direction: rtl;">
            <p>هو تطبيق مخصص لجمع وإدارة البيانات المتعلقة بالأشخاص والعقارات والمطالبات المرتبطة بها، ويُستخدم من قبل الموظفين الميدانيين أثناء تنفيذ الزيارات وجمع المعلومات على أرض الواقع.</p>
            <p>يتيح التطبيق إدخال البيانات بشكل منظم وسلس، مع ربط الأشخاص بالوحدات العقارية وتوثيق حالات الملكية أو الإشغال، ومرفق الوثائق الداعمة مثل الصور والمستندات. كما يدعم التطبيق حفظ البيانات محلياً والعمل دون اتصال بالإنترنت، مع إمكانية استكمال الإدخال لاحقاً أو مزامنة البيانات مع النظام المركزي عند توفر الاتصال.</p>
        </div>
        """)

        layout.addWidget(self._about_editor)
        return card

    def _create_rich_text_toolbar(self, editor_attr: str = "_glossary_editor") -> QWidget:
        # Wrap in a QWidget with LTR so Font/B/I/U order is correct
        toolbar_widget = QWidget()
        toolbar_widget.setLayoutDirection(Qt.LeftToRight)
        toolbar_widget.setStyleSheet("background: transparent;")
        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setSpacing(4)
        toolbar.setContentsMargins(0, 0, 0, 0)

        # Font label
        font_label = QLabel("Font")
        font_label.setFont(create_font(size=FontManager.SIZE_SMALL, weight=QFont.Normal))
        font_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
        toolbar.addWidget(font_label)

        # Separator
        sep = QFrame()
        sep.setFixedSize(1, 20)
        sep.setStyleSheet("background-color: #E5E7EB;")
        toolbar.addWidget(sep)

        # Format buttons
        format_buttons = [
            ("B", "bold"), ("I", "italic"), ("U", "underline"), ("S", "strikethrough"),
        ]

        for label, action in format_buttons:
            btn = QPushButton(label)
            btn.setFixedSize(28, 28)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(create_font(size=FontManager.SIZE_SMALL, weight=QFont.Bold if label == "B" else QFont.Normal))
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                    color: #374151;
                }
                QPushButton:hover { background-color: #F3F4F6; }
                QPushButton:checked { background-color: #DBEAFE; color: #3B86FF; }
            """)
            btn.clicked.connect(lambda checked, a=action, ea=editor_attr: self._apply_format(a, ea))
            toolbar.addWidget(btn)

        # Separator
        sep2 = QFrame()
        sep2.setFixedSize(1, 20)
        sep2.setStyleSheet("background-color: #E5E7EB;")
        toolbar.addWidget(sep2)

        # Alignment and list buttons
        extra_buttons = ["≡", "≡", "≡", "≡", "⇐", "⇒", "🔗", "🖼", "▪", "Tx"]
        for symbol in extra_buttons:
            btn = QPushButton(symbol)
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                    color: #374151;
                    font-size: 10px;
                }
                QPushButton:hover { background-color: #F3F4F6; }
            """)
            toolbar.addWidget(btn)

        toolbar.addStretch()
        return toolbar_widget

    def _apply_format(self, action: str, editor_attr: str = "_glossary_editor"):
        editor = getattr(self, editor_attr, None)
        if not editor:
            return
        cursor = editor.textCursor()
        fmt = cursor.charFormat()

        if action == "bold":
            fmt.setFontWeight(QFont.Bold if fmt.fontWeight() != QFont.Bold else QFont.Normal)
        elif action == "italic":
            fmt.setFontItalic(not fmt.fontItalic())
        elif action == "underline":
            fmt.setFontUnderline(not fmt.fontUnderline())
        elif action == "strikethrough":
            fmt.setFontStrikeOut(not fmt.fontStrikeOut())

        cursor.mergeCharFormat(fmt)
        editor.setTextCursor(cursor)

    # --- Section 3: Help & Support ---

    def _create_support_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("supportCard")
        card.setLayoutDirection(Qt.RightToLeft)
        card.setStyleSheet("""
            QFrame#supportCard {
                background-color: white;
                border-radius: 8px;
            }
        """)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Title
        section_title = QLabel("المساعدة و الدعم")
        section_title.setFont(create_font(size=12, weight=QFont.Bold))
        section_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(section_title)

        # Fields row
        fields_row = QHBoxLayout()
        fields_row.setSpacing(16)

        fields = [
            ("الهاتف الثابت", "09-----------"),
            ("الايميل", "-----@gmail.com"),
            ("رقم هاتف اخر", "09-----------"),
        ]

        for label_text, placeholder in fields:
            field_layout = QVBoxLayout()
            field_layout.setSpacing(4)

            label = QLabel(label_text)
            label.setFont(create_font(size=FontManager.SIZE_SMALL, weight=QFont.Normal))
            label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; background: transparent;")
            label.setAlignment(Qt.AlignRight)
            field_layout.addWidget(label)

            input_field = QLineEdit()
            input_field.setPlaceholderText(placeholder)
            input_field.setFixedHeight(36)
            input_field.setFont(create_font(size=FontManager.SIZE_BODY, weight=QFont.Normal))
            input_field.setStyleSheet(_INPUT_STYLE)
            field_layout.addWidget(input_field)

            fields_row.addLayout(field_layout)

        layout.addLayout(fields_row)

        return card

    # --- Data Loading ---

    def _load_vocabulary_terms(self, vocab_name: str) -> list:
        """Load terms from vocab_service (same source as dropdowns)."""
        options = vocab_service.get_options(vocab_name, lang="ar")
        return [(code, label) for code, label in options if code != 0]

    def _populate_vocab_group(self, vocab_name: str):
        content_widget = self._accordion_contents.get(vocab_name)
        add_btn = self._vocab_add_btns.get(vocab_name)
        if content_widget is None:
            return
        container = content_widget.layout()
        if container is None:
            return

        # Remove old terms widget if it exists
        old_widget = self._vocab_terms_widgets.get(vocab_name)
        if old_widget:
            container.removeWidget(old_widget)
            old_widget.deleteLater()

        # Build a new widget with all chips arranged in rows
        terms_widget = QWidget()
        terms_widget.setStyleSheet("background: transparent;")
        terms_layout = QVBoxLayout(terms_widget)
        terms_layout.setContentsMargins(0, 0, 0, 0)
        terms_layout.setSpacing(6)

        terms = self._load_vocabulary_terms(vocab_name)
        CHIPS_PER_ROW = 5

        current_row = QHBoxLayout()
        current_row.setSpacing(6)
        current_row.setContentsMargins(0, 0, 0, 0)
        chips_in_row = 0

        for code, label in terms:
            if chips_in_row >= CHIPS_PER_ROW:
                current_row.addStretch()
                terms_layout.addLayout(current_row)
                current_row = QHBoxLayout()
                current_row.setSpacing(6)
                current_row.setContentsMargins(0, 0, 0, 0)
                chips_in_row = 0

            chip = self._create_term_chip(label, code, vocab_name)
            current_row.addWidget(chip)
            chips_in_row += 1

        # Add button at the end of the last row
        if add_btn:
            add_btn.setParent(None)
            current_row.addWidget(add_btn)
        current_row.addStretch()
        terms_layout.addLayout(current_row)

        container.addWidget(terms_widget)
        self._vocab_terms_widgets[vocab_name] = terms_widget

    def _on_add_term(self, vocab_name: str):
        text, ok = QInputDialog.getText(
            self, "إضافة مصطلح", "أدخل المصطلح الجديد:",
            QLineEdit.Normal, ""
        )
        if ok and text.strip():
            label_ar = text.strip()
            code = vocab_service.get_next_code(vocab_name)
            vocab_service.add_term(vocab_name, code, label_ar, label_ar, order=code)
            self._persist_term_to_db(vocab_name, code, label_ar)
            self._populate_vocab_group(vocab_name)

    def _persist_term_to_db(self, vocab_name: str, code: int, label_ar: str):
        if not self.db:
            return
        try:
            import uuid
            from datetime import datetime
            self.db.execute(
                "INSERT OR REPLACE INTO vocabulary_terms "
                "(term_id, vocabulary_name, term_code, term_label, term_label_ar, source, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'manual', 'active', ?)",
                (str(uuid.uuid4()), vocab_name, str(code), label_ar, label_ar, datetime.now().isoformat())
            )
        except Exception as e:
            logger.warning(f"Failed to persist term to DB: {e}")

    def _update_term_in_db(self, vocab_name: str, code: int, label_ar: str):
        if not self.db:
            return
        try:
            from datetime import datetime
            self.db.execute(
                "UPDATE vocabulary_terms SET term_label = ?, term_label_ar = ?, source = 'manual', updated_at = ? "
                "WHERE vocabulary_name = ? AND term_code = ?",
                (label_ar, label_ar, datetime.now().isoformat(), vocab_name, str(code))
            )
        except Exception as e:
            logger.warning(f"Failed to update term in DB: {e}")

    def _delete_term_from_db(self, vocab_name: str, code: int):
        if not self.db:
            return
        try:
            self.db.execute(
                "DELETE FROM vocabulary_terms WHERE vocabulary_name = ? AND term_code = ?",
                (vocab_name, str(code))
            )
        except Exception as e:
            logger.warning(f"Failed to delete term from DB: {e}")

    def refresh(self, data=None):
        for vocab_name in self._accordion_contents:
            self._populate_vocab_group(vocab_name)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
