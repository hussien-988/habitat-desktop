# Font Management - Best Practices

## 🎯 Problem (Root Cause)

**المشكلة الجذرية**: Global Stylesheet في `app/styles.py` كان يطبق خصائص الخط على جميع الـ widgets مما يسبب تعارضات مع أي تعديل محلي.

### Why Stylesheets Don't Work for Fonts in PyQt5:

1. **CSS Specificity Issues**: Global stylesheet له أولوية عالية ويتجاوز `setFont()`
2. **Font Constructor Unreliable**: `QFont("Font Name", size, weight)` لا يعمل بشكل موثوق
3. **Font-family in QSS**: خاصية `font-family` في QSS غير موثوقة مع الخطوط المخصصة
4. **Override Conflicts**: عند استخدام stylesheet محلي مع stylesheet عام، تحدث تعارضات

## ✅ Solution (Root Fix)

### 1. Remove Font Properties from Global Stylesheet

❌ **قبل (Wrong):**
```python
# app/styles.py
QWidget {
    font-family: "IBM Plex Sans Arabic", "Calibri", sans-serif;  # تعارض!
    font-size: 10pt;  # تعارض!
}
```

✅ **بعد (Correct):**
```python
# app/styles.py
QWidget {
    color: #1e293b;
    background-color: #ffffff;
    /* NO font properties here! */
}
```

### 2. Centralized Font Management

**Create `ui/font_utils.py`**: Single source of truth for all fonts

```python
from ui.font_utils import create_font, FontManager

# Usage in components
title_font = create_font(
    size=FontManager.SIZE_TITLE,  # 18pt
    weight=FontManager.WEIGHT_BOLD,  # 700
    letter_spacing=0
)
label.setFont(title_font)
```

### 3. Set Application Default Font

**In `main.py`** (before creating any widgets):
```python
from ui.font_utils import set_application_default_font

app = QApplication(sys.argv)
set_application_default_font()  # CRITICAL: Set before creating widgets
```

## 📚 Usage Guidelines

### ✅ DO (Best Practices):

```python
# 1. Use font_utils for ALL fonts
from ui.font_utils import create_font, FontManager

font = create_font(size=18, weight=FontManager.WEIGHT_BOLD)
widget.setFont(font)

# 2. Use standard sizes from FontManager
font = create_font(size=FontManager.SIZE_TITLE)  # 18pt

# 3. Use QFont.setFamilies() for fallback chain
font = create_font(
    families=["IBM Plex Sans Arabic", "Calibri"]
)
```

### ❌ DON'T (Anti-patterns):

```python
# 1. DON'T set fonts in stylesheets
widget.setStyleSheet("""
    QLabel {
        font-family: "IBM Plex Sans Arabic";  # ❌ Conflicts!
        font-size: 18pt;  # ❌ Conflicts!
    }
""")

# 2. DON'T use QFont constructor with font name
font = QFont("IBM Plex Sans Arabic", 18, QFont.Bold)  # ❌ Unreliable!

# 3. DON'T create fonts manually
font = QFont()
font.setFamily("IBM Plex Sans Arabic")  # ❌ Violates DRY!
```

## 🔧 Migration Guide

### Migrating Existing Code:

**Before:**
```python
from PyQt5.QtGui import QFont
from ..design_system import Typography

title_font = QFont(Typography.FONT_FAMILY_PRIMARY, 18, QFont.Bold)
title_font.setLetterSpacing(QFont.AbsoluteSpacing, 0)
label.setFont(title_font)
```

**After:**
```python
from ..font_utils import create_font, FontManager

title_font = create_font(
    size=FontManager.SIZE_TITLE,
    weight=FontManager.WEIGHT_BOLD,
    letter_spacing=0
)
label.setFont(title_font)
```

## 🎨 Standard Sizes

```python
FontManager.SIZE_SMALL = 8        # Captions, footnotes
FontManager.SIZE_BODY = 10        # Body text, buttons
FontManager.SIZE_SUBHEADING = 12  # Subheadings
FontManager.SIZE_HEADING = 14     # Section headings
FontManager.SIZE_TITLE = 18       # Page titles
FontManager.SIZE_LARGE_TITLE = 24 # Large titles
```

## 🎯 Standard Weights

```python
FontManager.WEIGHT_LIGHT = 300      # Light
FontManager.WEIGHT_REGULAR = 400    # Regular
FontManager.WEIGHT_MEDIUM = 500     # Medium
FontManager.WEIGHT_SEMIBOLD = 600   # SemiBold
FontManager.WEIGHT_BOLD = 700       # Bold
```

## 📖 Architecture Benefits

### DRY (Don't Repeat Yourself)
- ✅ Single source of truth for font configuration
- ✅ No duplicate font creation code
- ✅ Centralized font family management

### SOLID Principles
- ✅ **Single Responsibility**: FontManager only handles fonts
- ✅ **Open/Closed**: Easy to extend with new font sizes
- ✅ **Dependency Inversion**: Components depend on FontManager interface

### Clean Code
- ✅ Clear, descriptive function names
- ✅ Self-documenting code
- ✅ Consistent API across entire application

## 🚨 Important Notes

1. **NEVER set font properties in QSS** - Always use `QFont.setFont()`
2. **ALWAYS use `font_utils`** - Don't create fonts manually
3. **Set application font FIRST** - Call `set_application_default_font()` in main.py
4. **Use standard sizes** - Use `FontManager.SIZE_*` constants

## 📝 Examples

### Example 1: Page Title
```python
from ui.font_utils import create_font, FontManager

# Figma: 24px Bold, Letter spacing 0
# PyQt5: 24px × 0.75 = 18pt
title_font = create_font(
    size=FontManager.SIZE_TITLE,  # 18pt
    weight=FontManager.WEIGHT_BOLD,
    letter_spacing=0
)
title_label.setFont(title_font)
```

### Example 2: Button Text
```python
from ui.font_utils import create_font, FontManager

# Figma: 16px SemiBold
# PyQt5: 16px × 0.75 = 12pt (but we use 10pt for buttons)
btn_font = create_font(
    size=FontManager.SIZE_BODY,  # 10pt
    weight=FontManager.WEIGHT_SEMIBOLD,
    letter_spacing=0
)
button.setFont(btn_font)
```

### Example 3: Small Caption
```python
from ui.font_utils import create_font, FontManager

caption_font = create_font(
    size=FontManager.SIZE_SMALL,  # 8pt
    weight=FontManager.WEIGHT_LIGHT,  # 300
    letter_spacing=0
)
caption_label.setFont(caption_font)
```

## 🔄 Testing

After applying this fix:

1. ✅ Fonts apply consistently across all widgets
2. ✅ No stylesheet conflicts
3. ✅ Easy to modify fonts application-wide
4. ✅ No more "font not applying" issues

## 📚 References

- PyQt5 Documentation: [QFont](https://doc.qt.io/qt-5/qfont.html)
- Qt Stylesheets: [CSS Font Properties](https://doc.qt.io/qt-5/stylesheet-reference.html)
- Best Practice: Use `setFont()` instead of QSS for fonts
