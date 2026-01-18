# دليل إعادة الهيكلة - TRRCMS Refactoring Guide

## نظرة عامة

تم إعادة هيكلة تطبيق TRRCMS Desktop باستخدام معمارية موحدة تعتمد على:
- **Wizard Framework**: إطار عمل موحد للمعالجات (Wizards)
- **Step-based Architecture**: تقسيم المعالجات إلى خطوات منفصلة
- **Centralized Validation**: خدمة موحدة للتحقق من البيانات
- **Context Management**: إدارة موحدة لحالة البيانات

---

## الهيكل الجديد

### 1. Wizard Framework (`ui/wizards/framework/`)

الإطار الموحد لجميع المعالجات:

```
ui/wizards/framework/
├── __init__.py
├── base_wizard.py          # BaseWizard: الفئة الأساسية لجميع المعالجات
├── base_step.py            # BaseStep: الفئة الأساسية لجميع الخطوات
├── wizard_context.py       # WizardContext: إدارة حالة المعالج
└── step_navigator.py       # StepNavigator: التنقل بين الخطوات
```

#### BaseWizard - الميزات الرئيسية:

- **واجهة موحدة**: Header, Progress Bar, Navigation Buttons
- **إدارة الخطوات**: التنقل التلقائي بين الخطوات
- **التحقق التلقائي**: Validation قبل الانتقال للخطوة التالية
- **حفظ المسودات**: إمكانية حفظ واستعادة المسودات
- **Signals**: إشارات للأحداث المهمة (completed, cancelled, etc.)

#### BaseStep - الميزات الرئيسية:

- **Lifecycle Methods**: `setup_ui()`, `validate()`, `collect_data()`, `populate_data()`
- **Context Integration**: الوصول المباشر للـContext
- **Validation**: نظام موحد للتحقق من البيانات
- **Signals**: إشارات لتحديثات الـUI

#### WizardContext - إدارة الحالة:

- **Serialization**: تحويل البيانات من وإلى Dictionary
- **State Tracking**: تتبع الخطوات المكتملة
- **Reference Numbers**: توليد أرقام مرجعية فريدة
- **Generic Data Storage**: تخزين بيانات مخصصة

---

### 2. Office Survey Wizard المُعاد هيكلته

#### الهيكل الجديد:

```
ui/wizards/office_survey/
├── __init__.py
├── survey_context.py                    # السياق المخصص لمسح المكاتب
├── office_survey_wizard_refactored.py   # المعالج الرئيسي (جديد)
├── steps/
│   ├── __init__.py
│   ├── building_selection_step.py       # الخطوة 1: اختيار المبنى ✅
│   ├── unit_selection_step.py           # الخطوة 2: اختيار/إنشاء الوحدة
│   ├── household_step.py                # الخطوة 3: معلومات الأسرة
│   ├── person_step.py                   # الخطوة 4: تسجيل الأشخاص
│   ├── relation_step.py                 # الخطوة 5: العلاقات والأدلة
│   ├── claim_step.py                    # الخطوة 6: إنشاء المطالبة
│   └── review_step.py                   # الخطوة 7: المراجعة والإرسال
└── dialogs/
    ├── person_dialog.py                 # حوار إضافة/تعديل شخص
    ├── evidence_dialog.py               # حوار إضافة دليل
    └── unit_dialog.py                   # حوار إنشاء وحدة جديدة
```

#### الحالة الحالية:

- ✅ **Framework**: مكتمل بالكامل
- ✅ **Context**: مكتمل بالكامل
- ✅ **Wizard**: مكتمل بالكامل
- ✅ **Step 1** (Building Selection): مكتمل كمثال
- ⏳ **Steps 2-7**: يجب إنشاؤها باستخدام نفس النمط
- ⏳ **Dialogs**: يجب نقلها من الكود القديم

---

## خطوات إعادة الهيكلة التدريجية

### المرحلة 1: الأساسيات ✅ (مكتمل)

- [x] إنشاء Wizard Framework
- [x] إنشاء Base Classes
- [x] إنشاء SurveyContext
- [x] إنشاء OfficeSurveyWizard
- [x] إنشاء مثال على Step واحد (BuildingSelectionStep)

### المرحلة 2: نقل باقي الخطوات (التالي)

#### الخطوة 2.1: Unit Selection Step

```python
# ui/wizards/office_survey/steps/unit_selection_step.py

class UnitSelectionStep(BaseStep):
    """
    الخطوة 2: اختيار أو إنشاء الوحدة.

    يمكن للمستخدم:
    - عرض الوحدات الموجودة في المبنى المختار
    - اختيار وحدة موجودة
    - إنشاء وحدة جديدة
    """

    def setup_ui(self):
        # 1. عرض معلومات المبنى المختار من context.building
        # 2. جدول بالوحدات الموجودة
        # 3. زر "إنشاء وحدة جديدة"
        pass

    def validate(self) -> StepValidationResult:
        # التحقق من اختيار وحدة أو إنشاء وحدة جديدة
        pass

    def collect_data(self) -> Dict[str, Any]:
        # جمع بيانات الوحدة المختارة
        pass
```

#### الخطوة 2.2: Household Step

```python
# ui/wizards/office_survey/steps/household_step.py

class HouseholdStep(BaseStep):
    """
    الخطوة 3: معلومات الأسرة.

    تسجيل:
    - عدد أفراد الأسرة
    - معلومات ديموغرافية
    - حالة السكن
    """
```

#### الخطوة 2.3: Person Step

```python
# ui/wizards/office_survey/steps/person_step.py

class PersonStep(BaseStep):
    """
    الخطوة 4: تسجيل الأشخاص.

    إضافة وتعديل:
    - معلومات الأشخاص
    - الهوية الوطنية
    - معلومات الاتصال
    """

    # يستخدم PersonDialog من dialogs/
```

#### الخطوة 2.4: Relation Step

```python
# ui/wizards/office_survey/steps/relation_step.py

class RelationStep(BaseStep):
    """
    الخطوة 5: العلاقات والأدلة.

    ربط الأشخاص بالوحدة:
    - نوع العلاقة (مالك، مستأجر، وارث، إلخ)
    - إضافة الأدلة
    - رفع الوثائق
    """

    # يستخدم EvidenceDialog من dialogs/
```

#### الخطوة 2.5: Claim Step

```python
# ui/wizards/office_survey/steps/claim_step.py

class ClaimStep(BaseStep):
    """
    الخطوة 6: إنشاء المطالبة.

    تسجيل:
    - نوع الحيازة
    - معلومات المطالبة
    - الحالة
    """
```

#### الخطوة 2.6: Review Step

```python
# ui/wizards/office_survey/steps/review_step.py

class ReviewStep(BaseStep):
    """
    الخطوة 7: المراجعة والإرسال.

    عرض ملخص شامل:
    - معلومات المبنى
    - معلومات الوحدة
    - الأشخاص والعلاقات
    - المطالبة
    - الأدلة
    """

    def setup_ui(self):
        # استخدام context.get_summary()
        # عرض جميع البيانات في UI للمراجعة
        pass
```

### المرحلة 3: نقل الـDialogs المشتركة

```
ui/wizards/office_survey/dialogs/
├── __init__.py
├── person_dialog.py      # نقل من office_survey_wizard.py
├── evidence_dialog.py    # نقل من office_survey_wizard.py
└── unit_dialog.py        # نقل من office_survey_wizard.py
```

**الفكرة:**
- نقل الـDialogs من الملف الكبير إلى ملفات منفصلة
- إزالة التكرار
- استخدام ValidationService للتحقق
- جعل الـDialogs قابلة لإعادة الاستخدام

---

## نمط الكود الموحد

### مثال على Step كامل:

```python
from typing import Dict, Any
from PyQt5.QtWidgets import *
from ui.wizards.framework import BaseStep, StepValidationResult
from services.validation_service import ValidationService

class ExampleStep(BaseStep):
    """مثال على خطوة."""

    def __init__(self, context, parent=None):
        super().__init__(context, parent)
        self.validation_service = ValidationService()
        # إضافة متغيرات أخرى

    def setup_ui(self):
        """إعداد واجهة المستخدم."""
        # Header
        header = QLabel("عنوان الخطوة")
        self.main_layout.addWidget(header)

        # Content
        # ... إضافة الحقول والعناصر

    def validate(self) -> StepValidationResult:
        """التحقق من البيانات."""
        result = self.create_validation_result()

        # استخدام ValidationService
        data = self.collect_data()
        validation = self.validation_service.validate_xyz(data)

        if not validation.is_valid:
            for error in validation.errors:
                result.add_error(error)

        return result

    def collect_data(self) -> Dict[str, Any]:
        """جمع البيانات من UI."""
        return {
            "field1": self.field1_input.text(),
            "field2": self.field2_input.text()
        }

    def populate_data(self):
        """ملء UI بالبيانات من Context."""
        data = self.get_from_context("step_data")
        if data:
            self.field1_input.setText(data.get("field1", ""))
            self.field2_input.setText(data.get("field2", ""))

    def get_step_title(self) -> str:
        return "عنوان الخطوة"

    def get_step_description(self) -> str:
        return "وصف الخطوة"
```

---

## الفوائد المحققة

### 1. فصل المسؤوليات (Separation of Concerns)
- ✅ كل Step في ملف منفصل
- ✅ UI منفصلة عن Business Logic
- ✅ Validation في خدمة مركزية

### 2. قابلية إعادة الاستخدام (Reusability)
- ✅ Framework قابل للاستخدام في أي Wizard جديد
- ✅ Steps قابلة لإعادة الاستخدام
- ✅ Validation قابلة لإعادة الاستخدام

### 3. قابلية الصيانة (Maintainability)
- ✅ ملفات صغيرة وواضحة بدلاً من 5000 سطر
- ✅ سهولة إيجاد الكود
- ✅ سهولة التعديل والتحديث

### 4. قابلية الاختبار (Testability)
- ✅ كل Step قابل للاختبار بشكل منفصل
- ✅ Context قابل للـMocking
- ✅ Validation منفصلة عن UI

### 5. قابلية التوسع (Scalability)
- ✅ إضافة Steps جديدة سهلة
- ✅ تعديل ترتيب الخطوات سهل
- ✅ إضافة Wizards جديدة سهلة

---

## التعليمات

### كيفية إنشاء Step جديدة:

1. **إنشاء الملف**:
   ```bash
   touch ui/wizards/office_survey/steps/my_new_step.py
   ```

2. **كتابة الكود**:
   ```python
   from ui.wizards.framework import BaseStep, StepValidationResult

   class MyNewStep(BaseStep):
       def setup_ui(self): ...
       def validate(self) -> StepValidationResult: ...
       def collect_data(self) -> Dict[str, Any]: ...
   ```

3. **إضافة إلى `__init__.py`**:
   ```python
   from .my_new_step import MyNewStep
   __all__.append('MyNewStep')
   ```

4. **إضافة إلى Wizard**:
   ```python
   def create_steps(self) -> List[BaseStep]:
       return [
           # ...
           MyNewStep(self.context, self),
       ]
   ```

### كيفية استخدام Wizard:

```python
from ui.wizards.office_survey import OfficeSurveyWizard

# إنشاء wizard جديد
wizard = OfficeSurveyWizard(parent=self)

# Connect signals
wizard.wizard_completed.connect(self.on_survey_completed)
wizard.wizard_cancelled.connect(self.on_survey_cancelled)

# Show wizard
wizard.show()
```

### كيفية تحميل مسودة:

```python
wizard = OfficeSurveyWizard.load_from_draft("DRAFT-ID-123", parent=self)
if wizard:
    wizard.show()
```

---

## المقارنة: قبل وبعد

### قبل إعادة الهيكلة:

```
office_survey_wizard.py (5005 lines)
├── Class OfficeSurveyWizard
├── Class SurveyContext
├── Class PersonDialog
├── Class EvidenceDialog
├── Step 1 logic (inline)
├── Step 2 logic (inline)
├── Step 3 logic (inline)
├── Step 4 logic (inline)
├── Step 5 logic (inline)
├── Step 6 logic (inline)
└── Step 7 logic (inline)

❌ كل شيء في ملف واحد ضخم
❌ صعوبة الصيانة
❌ صعوبة الاختبار
❌ تكرار الكود
❌ UI و Logic مختلطة
```

### بعد إعادة الهيكلة:

```
ui/wizards/office_survey/
├── office_survey_wizard_refactored.py (150 lines)
├── survey_context.py (140 lines)
├── steps/
│   ├── building_selection_step.py (200 lines)
│   ├── unit_selection_step.py (200 lines)
│   ├── household_step.py (150 lines)
│   ├── person_step.py (180 lines)
│   ├── relation_step.py (180 lines)
│   ├── claim_step.py (150 lines)
│   └── review_step.py (120 lines)
└── dialogs/
    ├── person_dialog.py (150 lines)
    ├── evidence_dialog.py (120 lines)
    └── unit_dialog.py (100 lines)

✅ كل جزء في ملف منفصل
✅ سهولة الصيانة
✅ سهولة الاختبار
✅ لا تكرار
✅ فصل واضح بين UI و Logic
```

---

## الخطوات التالية

### أولوية عالية:
1. ✅ إنشاء Wizard Framework
2. ✅ إنشاء مثال على Step واحد
3. ⏳ **إنشاء باقي الـSteps (2-7)**
4. ⏳ نقل الـDialogs المشتركة
5. ⏳ اختبار الـWorkflow كاملاً

### أولوية متوسطة:
6. إنشاء Form Builder System لتوحيد الـForms
7. إنشاء Base Repository لتوحيد Data Access
8. إضافة Unit Tests للـFramework
9. إضافة Integration Tests للـWizard

### أولوية منخفضة:
10. توثيق API كامل
11. إنشاء أمثلة إضافية
12. Migration Script لنقل البيانات القديمة

---

## الأسئلة الشائعة

### س: هل يجب حذف office_survey_wizard.py القديم؟
**ج**: لا، احتفظ به حتى تكتمل إعادة الهيكلة بالكامل واختباره. ثم يمكن حذفه أو الاحتفاظ به كمرجع.

### س: كيف أنقل الـlogic من الكود القديم؟
**ج**:
1. اقرأ الكود القديم لفهم الـlogic
2. استخرج الأجزاء المهمة
3. أعد كتابتها في الـStep الجديدة
4. استخدم ValidationService بدلاً من validation مضمّنة
5. اختبر الـStep بشكل منفصل

### س: ما هي الخطوة التي يجب البدء بها؟
**ج**: ابدأ بـ UnitSelectionStep (الخطوة 2) لأنها تعتمد على BuildingSelectionStep المكتملة.

### س: هل يمكن استخدام نفس الـFramework لـWizards أخرى؟
**ج**: نعم! الـFramework عام ويمكن استخدامه لأي Wizard (Import Wizard, Field Survey, etc.)

---

## الخلاصة

تم إنشاء:
- ✅ **Wizard Framework** موحد وقابل لإعادة الاستخدام
- ✅ **SurveyContext** لإدارة حالة المسح
- ✅ **OfficeSurveyWizard** الرئيسي
- ✅ **BuildingSelectionStep** كمثال

المطلوب:
- ⏳ إنشاء باقي الـSteps (2-7)
- ⏳ نقل الـDialogs المشتركة
- ⏳ اختبار شامل

**النتيجة**: كود أنظف، أسهل للصيانة، وأكثر قابلية للتوسع! 🚀
