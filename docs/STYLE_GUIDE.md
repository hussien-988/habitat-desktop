# Style Guide - دليل الأنماط

## 🎯 Purpose - الهدف

هذا الدليل يحدد كيفية استخدام نظام التصميم الموحد (Unified Design System) في تطبيق UN-Habitat TRRCMS.

**الهدف الأساسي:** مصدر واحد للحقيقة (Single Source of Truth) لجميع الأنماط في التطبيق.

---

## 📐 Architecture - الهيكل المعماري

### **البنية التحتية:**

```
ui/
├── design_system.py       # Constants (Colors, Dimensions, Typography)
├── font_utils.py          # Font management (centralized)
├── style_manager.py       # Stylesheet generation (centralized)
└── components/            # Reusable UI components
```

### **المبادئ الأساسية:**

1. **DRY (Don't Repeat Yourself)**
   - كل قيمة/style تُعرّف مرة واحدة فقط
   - لا تكرار في الكود

2. **SOLID Principles**
   - Single Responsibility: كل component/function مسؤول عن شيء واحد
   - Open/Closed: سهولة التوسع بدون تعديل الكود الموجود

3. **Clean Code**
   - أسماء واضحة ومفهومة
   - توثيق شامل (docstrings)
   - Type hints واضحة

---

## 🎨 Design System Components

### **1. design_system.py**

**الدور:** تخزين جميع القيم الثابتة (Constants)

**المحتويات:**
- `Colors` - جميع الألوان المستخدمة في التطبيق
- `Typography` - Font families, weights, sizes
- `Spacing` - Margins, padding, gaps
- `NavbarDimensions` - أبعاد الـ Navbar
- `PageDimensions` - أبعاد الصفحات
- `ButtonDimensions` - أبعاد الأزرار
- `BorderRadius` - نصف أقطار الحواف

**الاستخدام:**
```python
from ui.design_system import Colors, PageDimensions

# استخدام الألوان
label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")

# استخدام الأبعاد
card.setFixedHeight(PageDimensions.CARD_HEIGHT)
```

**⚠️ ممنوع:**
```python
# ❌ لا تستخدم قيم مباشرة (Hard-coded values)
label.setStyleSheet("color: #2C3E50;")  # WRONG

# ✅ استخدم design_system
label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")  # CORRECT
```

---

### **2. font_utils.py**

**الدور:** إدارة جميع الخطوط في التطبيق (Centralized Font Management)

**المحتويات:**
- `FontManager` - Singleton class لإدارة الخطوط
- `create_font()` - إنشاء خط بمواصفات محددة
- `set_application_default_font()` - تطبيق الخط الافتراضي

**الاستخدام:**
```python
from ui.font_utils import create_font, FontManager
from PyQt5.QtGui import QFont

# إنشاء خط
title_font = create_font(
    size=FontManager.SIZE_TITLE,  # 18pt
    weight=QFont.Bold,             # 700
    letter_spacing=0
)
label.setFont(title_font)
```

**⚠️ ممنوع:**
```python
# ❌ لا تستخدم QFont constructor مباشرة
font = QFont("IBM Plex Sans Arabic", 18, QFont.Bold)  # WRONG

# ❌ لا تحدد الخطوط في QSS
widget.setStyleSheet("""
    QLabel {
        font-family: "IBM Plex Sans Arabic";  /* WRONG */
        font-size: 18pt;                      /* WRONG */
    }
""")

# ✅ استخدم font_utils
font = create_font(size=18, weight=QFont.Bold)  # CORRECT
label.setFont(font)
```

---

### **3. style_manager.py** ⭐ **الأساس**

**الدور:** توليد جميع الـ QSS Stylesheets (Single Source of Truth)

**المحتويات:**
- `StyleManager` - Class مركزي لتوليد الـ styles
- جميع الـ styles للـ components (buttons, inputs, cards, etc.)

**الاستخدام:**
```python
from ui.style_manager import StyleManager

# Apply button style
button.setStyleSheet(StyleManager.button_primary())

# Apply input style
input_field.setStyleSheet(StyleManager.input_field())

# Apply navbar style
navbar.setStyleSheet(StyleManager.navbar())
```

**⚠️ ممنوع:**
```python
# ❌ لا تكتب inline QSS في components
button.setStyleSheet("""
    QPushButton {
        background-color: #3890DF;  /* WRONG */
        color: white;
    }
""")

# ✅ استخدم StyleManager
button.setStyleSheet(StyleManager.button_primary())  # CORRECT
```

---

## 🧩 Reusable Components

### **Available Components:**

| Component | File | Usage |
|-----------|------|-------|
| PrimaryButton | `primary_button.py` | أزرار رئيسية (Add, Save, Submit) |
| SecondaryButton | `secondary_button.py` | أزرار ثانوية (Cancel, Back) |
| TextButton | `text_button.py` | أزرار نصية (Skip, Close) |
| DangerButton | `danger_button.py` | أزرار خطر (Delete, Remove) |
| InputField | `input_field.py` | حقول إدخال موحدة |
| PageHeader | `page_header.py` | رأس الصفحة (Title + Button) |
| Icon | `icon.py` | إدارة الأيقونات |
| ClaimListCard | `claim_list_card.py` | كرت المطالبة |
| EmptyState | `empty_state.py` | حالة فارغة |

### **Usage Examples:**

#### **1. Buttons**

```python
from ui.components import PrimaryButton, SecondaryButton, TextButton, DangerButton

# Primary button (main action)
add_btn = PrimaryButton("إضافة حالة جديدة", icon_name="icon")
add_btn.clicked.connect(self.on_add)

# Secondary button (cancel, back)
cancel_btn = SecondaryButton("إلغاء")
cancel_btn.clicked.connect(self.on_cancel)

# Text button (skip, close)
skip_btn = TextButton("تخطي")
skip_btn.clicked.connect(self.on_skip)

# Danger button (delete, remove)
delete_btn = DangerButton("حذف")
delete_btn.clicked.connect(self.on_delete)
```

#### **2. Input Fields**

```python
from ui.components import InputField

# Default input
name_field = InputField(placeholder="أدخل الاسم...")

# Error state
email_field = InputField(placeholder="البريد الإلكتروني...", variant="error")

# Success state
password_field = InputField(placeholder="كلمة المرور...", variant="success")

# Change state dynamically
name_field.set_error()  # Change to error state
name_field.set_success()  # Change to success state
name_field.set_default()  # Reset to default
```

#### **3. Page Header**

```python
from ui.components import PageHeader

# With add button
header = PageHeader(
    title="المطالبات المكتملة",
    show_add_button=True,
    button_text="إضافة حالة جديدة",
    button_icon="icon"
)
header.add_clicked.connect(self.on_add_claim)

# Without add button
header = PageHeader(title="المباني")

# Update title dynamically
header.set_title("المطالبات المسودة")
```

#### **4. Icons**

```python
from ui.components import Icon, IconSize

# Load icon
icon = Icon("blue", size=IconSize.MEDIUM.value)

# Load icon with fallback
icon = Icon("user", size=32, fallback_text="👤")

# Load QIcon for buttons
from ui.components.icon import Icon
q_icon = Icon.load_qicon("icon")
if q_icon:
    button.setIcon(q_icon)
    button.setIconSize(QSize(20, 20))
```

---

## 📋 Best Practices

### **✅ DO (افعل):**

1. **استخدم المكونات الموحدة دائماً:**
   ```python
   # Use reusable components
   btn = PrimaryButton("حفظ")
   ```

2. **استخدم StyleManager للـ styles:**
   ```python
   widget.setStyleSheet(StyleManager.button_primary())
   ```

3. **استخدم font_utils للخطوط:**
   ```python
   font = create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold)
   ```

4. **استخدم design_system للقيم:**
   ```python
   color = Colors.PRIMARY_BLUE
   height = PageDimensions.CARD_HEIGHT
   ```

### **❌ DON'T (لا تفعل):**

1. **لا تكتب inline QSS:**
   ```python
   # ❌ WRONG
   widget.setStyleSheet("background-color: #3890DF;")
   ```

2. **لا تستخدم hard-coded values:**
   ```python
   # ❌ WRONG
   widget.setFixedHeight(112)  # Magic number!
   ```

3. **لا تنسخ/تلصق styles:**
   ```python
   # ❌ WRONG - Duplicate code
   button1.setStyleSheet("QPushButton { ... }")
   button2.setStyleSheet("QPushButton { ... }")  # Same style!
   ```

4. **لا تحدد الخطوط في QSS:**
   ```python
   # ❌ WRONG
   widget.setStyleSheet("font-family: 'IBM Plex Sans Arabic';")
   ```

---

## 🔄 Migration Guide - دليل الترحيل

### **How to Update Old Pages:**

#### **Step 1: Replace Fonts**

**قبل:**
```python
font = QFont("IBM Plex Sans Arabic", 18, QFont.Bold)
label.setFont(font)
```

**بعد:**
```python
from ui.font_utils import create_font, FontManager
from PyQt5.QtGui import QFont

font = create_font(size=FontManager.SIZE_TITLE, weight=QFont.Bold)
label.setFont(font)
```

---

#### **Step 2: Replace Inline QSS**

**قبل:**
```python
button.setStyleSheet("""
    QPushButton {
        background-color: #3890DF;
        color: white;
        border: none;
        border-radius: 8px;
    }
""")
```

**بعد:**
```python
from ui.style_manager import StyleManager

button.setStyleSheet(StyleManager.button_primary())
```

---

#### **Step 3: Use Reusable Components**

**قبل:**
```python
# Create button manually
button = QPushButton("إضافة")
button.setFixedSize(199, 48)
button.setStyleSheet("""...""")  # Long QSS
```

**بعد:**
```python
from ui.components import PrimaryButton

button = PrimaryButton("إضافة", icon_name="icon")
```

---

#### **Step 4: Replace Hard-coded Values**

**قبل:**
```python
card.setFixedHeight(112)  # Magic number!
layout.setSpacing(16)     # Magic number!
```

**بعد:**
```python
from ui.design_system import PageDimensions

card.setFixedHeight(PageDimensions.CARD_HEIGHT)
layout.setSpacing(PageDimensions.CARD_GAP_VERTICAL)
```

---

## 📊 Complete Example - مثال كامل

### **Before (Old Code):**

```python
class OldPage(QWidget):
    def __init__(self):
        super().__init__()

        # ❌ Hard-coded background
        self.setStyleSheet("background-color: #F0F7FF;")

        layout = QVBoxLayout(self)

        # ❌ Manual font creation
        title_font = QFont("IBM Plex Sans Arabic", 18, QFont.Bold)
        title = QLabel("العنوان")
        title.setFont(title_font)
        title.setStyleSheet("color: #2C3E50;")  # ❌ Hard-coded color

        # ❌ Inline QSS for button
        btn = QPushButton("إضافة")
        btn.setFixedSize(199, 48)  # ❌ Magic numbers
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3890DF;
                color: white;
                border: none;
                border-radius: 8px;
            }
        """)

        layout.addWidget(title)
        layout.addWidget(btn)
```

### **After (New Code with Design System):**

```python
from ui.components import PageHeader, PrimaryButton
from ui.style_manager import StyleManager

class NewPage(QWidget):
    def __init__(self):
        super().__init__()

        # ✅ Use StyleManager
        self.setStyleSheet(StyleManager.page_background())

        layout = QVBoxLayout(self)

        # ✅ Use reusable PageHeader component
        header = PageHeader(
            title="العنوان",
            show_add_button=True,
            button_text="إضافة حالة جديدة",
            button_icon="icon"
        )
        header.add_clicked.connect(self.on_add)

        layout.addWidget(header)
```

**النتيجة:**
- ✅ أقل كود بـ 60%
- ✅ لا hard-coded values
- ✅ استخدام components موحدة
- ✅ سهولة الصيانة

---

## 🎯 Summary - الخلاصة

### **القواعد الذهبية:**

1. **📝 NEVER write inline QSS** - استخدم StyleManager
2. **🔤 NEVER create fonts manually** - استخدم font_utils
3. **🎨 NEVER use hard-coded values** - استخدم design_system
4. **🧩 ALWAYS use reusable components** - لا تعيد اختراع العجلة

### **Workflow:**

```
1. Need a button?
   → Use PrimaryButton/SecondaryButton/TextButton/DangerButton

2. Need styling?
   → Use StyleManager.xxx()

3. Need a font?
   → Use create_font()

4. Need a color/dimension?
   → Use design_system (Colors, PageDimensions, etc.)
```

---

## 📚 References

- [FONT_MANAGEMENT.md](./FONT_MANAGEMENT.md) - دليل إدارة الخطوط
- `ui/design_system.py` - جميع Constants
- `ui/style_manager.py` - جميع Styles
- `ui/font_utils.py` - إدارة الخطوط

---

**Created:** 2025-01-20
**Author:** UN-Habitat TRRCMS Team
**Version:** 1.0
