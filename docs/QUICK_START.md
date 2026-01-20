# Quick Start - البداية السريعة

## 🚀 للمطورين الجدد

هذا الدليل السريع يوضح كيفية استخدام النظام الموحد للتصميم (Unified Design System).

---

## 📦 ما الذي تم بناءه؟

### **البنية الأساسية:**

| File | Purpose |
|------|---------|
| `ui/design_system.py` | جميع القيم الثابتة (Colors, Dimensions) |
| `ui/font_utils.py` | إدارة الخطوط |
| `ui/style_manager.py` | توليد الـ QSS Stylesheets |
| `ui/components/` | المكونات القابلة لإعادة الاستخدام |

### **المكونات المتاحة:**

| Component | File |
|-----------|------|
| PrimaryButton | `primary_button.py` |
| SecondaryButton | `secondary_button.py` |
| TextButton | `text_button.py` |
| DangerButton | `danger_button.py` |
| InputField | `input_field.py` |
| PageHeader | `page_header.py` |
| Icon | `icon.py` |
| ClaimListCard | `claim_list_card.py` |
| EmptyState | `empty_state.py` |

---

## 🎯 الاستخدام الأساسي

### **1. Colors - الألوان**

```python
from ui.design_system import Colors

# Use predefined colors
label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
widget.setStyleSheet(f"background-color: {Colors.BACKGROUND};")
```

### **2. Fonts - الخطوط**

```python
from ui.font_utils import create_font, FontManager
from PyQt5.QtGui import QFont

# Create a font
title_font = create_font(
    size=FontManager.SIZE_TITLE,  # 18pt
    weight=QFont.Bold,             # 700
    letter_spacing=0
)
label.setFont(title_font)
```

### **3. Styles - الأنماط**

```python
from ui.style_manager import StyleManager

# Apply button style
button.setStyleSheet(StyleManager.button_primary())

# Apply input style
input_field.setStyleSheet(StyleManager.input_field())

# Apply page background
page.setStyleSheet(StyleManager.page_background())
```

### **4. Components - المكونات**

```python
from ui.components import PrimaryButton, PageHeader, InputField

# Use reusable button
btn = PrimaryButton("حفظ", icon_name="icon")
btn.clicked.connect(self.on_save)

# Use page header
header = PageHeader(title="المطالبات", show_add_button=True)
header.add_clicked.connect(self.on_add)

# Use input field
field = InputField(placeholder="أدخل الاسم...")
```

---

## ⚠️ القواعد الأساسية

### **❌ لا تفعل:**

```python
# ❌ Hard-coded colors
widget.setStyleSheet("color: #2C3E50;")

# ❌ Hard-coded dimensions
widget.setFixedHeight(112)

# ❌ Manual font creation
font = QFont("IBM Plex Sans Arabic", 18, QFont.Bold)

# ❌ Inline QSS
button.setStyleSheet("""
    QPushButton {
        background-color: #3890DF;
        ...
    }
""")
```

### **✅ افعل:**

```python
# ✅ Use design_system
widget.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")

# ✅ Use design_system dimensions
widget.setFixedHeight(PageDimensions.CARD_HEIGHT)

# ✅ Use font_utils
font = create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold)

# ✅ Use StyleManager
button.setStyleSheet(StyleManager.button_primary())
```

---

## 📝 مثال كامل

```python
# ui/pages/example_page.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import pyqtSignal

from ..components import PageHeader, PrimaryButton, InputField
from ..style_manager import StyleManager


class ExamplePage(QWidget):
    """Example page using unified design system."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI using reusable components and StyleManager."""
        # Apply page background
        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)

        # Use PageHeader component
        header = PageHeader(
            title="مثال الصفحة",
            show_add_button=True,
            button_text="إضافة",
            button_icon="icon"
        )
        header.add_clicked.connect(self.on_add)
        layout.addWidget(header)

        # Use InputField component
        name_field = InputField(placeholder="أدخل الاسم...")
        layout.addWidget(name_field)

        # Use PrimaryButton component
        save_btn = PrimaryButton("حفظ")
        save_btn.clicked.connect(self.on_save)
        layout.addWidget(save_btn)

    def on_add(self):
        """Handle add button click."""
        print("Add clicked")

    def on_save(self):
        """Handle save button click."""
        print("Save clicked")
```

---

## 📚 للمزيد

- **دليل الأنماط الشامل:** [STYLE_GUIDE.md](./STYLE_GUIDE.md)
- **خطة التنفيذ:** [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)
- **إدارة الخطوط:** [FONT_MANAGEMENT.md](./FONT_MANAGEMENT.md)

---

**Created:** 2025-01-20
**Version:** 1.0
