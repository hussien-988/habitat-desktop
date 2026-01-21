# خطة تقسيم Office Survey Wizard
# Office Survey Wizard Refactoring Plan

**التاريخ:** 2026-01-22
**الملف الأصلي:** `ui/pages/office_survey_wizard.py` (4531 سطر)
**الهدف:** تقسيم إلى 7 خطوات modular + coordinator

---

## 📊 التحليل الحالي

### حجم الملف:
- **4531 سطر** - ضخم جداً (يجب < 500 سطر لكل ملف)
- **~84 method** - كثير جداً لـ class واحد
- **Monolithic structure** - جميع الخطوات في ملف واحد

### البنية الحالية:

```
office_survey_wizard.py (4531 lines)
├── class SurveyContext (lines 84-157)
├── class Evidence (lines 159-191)
└── class OfficeSurveyWizard (lines 193-4531)
    ├── Step 1: Building Selection (lines 439-1241)
    ├── Step 2: Unit Management (lines 1243-1956)
    ├── Step 3: Household Profile (lines 1958-2457)
    ├── Step 4: Person Registration (lines 2459-2758)
    ├── Step 5: Relations (lines 2760-3248)
    ├── Step 6: Claim Evaluation (lines 3250-3527)
    └── Step 7: Review & Submit (lines 3529-4104)
```

### المشاكل:
1. ❌ **Violation of SRP** - One class doing too much
2. ❌ **Business Logic in UI** - Validation, data transformation
3. ❌ **Hard to maintain** - Changes in one step affect others
4. ❌ **Difficult to test** - Cannot test steps independently
5. ❌ **Code duplication** - Similar patterns repeated
6. ❌ **Poor reusability** - Cannot reuse steps elsewhere

---

## 🎯 الهيكل المستهدف

### الهيكل الجديد:

```
ui/wizards/office_survey/
├── __init__.py                          # Public API
├── wizard_main.py                       # Main coordinator (~300 lines)
├── wizard_context.py                    # Shared state (~150 lines)
│
├── steps/
│   ├── __init__.py
│   ├── base_step.py                     # Base class for steps (~100 lines)
│   ├── step_1_building_selection.py     # Building selection (~400 lines)
│   ├── step_2_unit_management.py        # Unit CRUD (~400 lines)
│   ├── step_3_household_profile.py      # Household info (~350 lines)
│   ├── step_4_person_registration.py    # Person CRUD (~450 lines)
│   ├── step_5_relations.py              # Relations & evidence (~400 lines)
│   ├── step_6_claim_evaluation.py       # Claim creation (~350 lines)
│   └── step_7_review_submit.py          # Final review (~350 lines)
│
└── components/
    ├── __init__.py
    ├── building_search.py               # Reusable building search (~200 lines)
    ├── unit_card.py                     # Reusable unit card (~150 lines)
    └── person_card.py                   # Reusable person card (~150 lines)
```

**الإجمالي:**
- 7 step files (~2800 lines)
- 3 reusable components (~500 lines)
- 1 coordinator (~300 lines)
- 2 supporting files (~250 lines)
- **Total: ~3850 lines** (تقليل بنسبة 15% + تحسين تنظيم)

---

## 📝 تفصيل الخطوات

### Step 1: Building Selection (~400 lines)
**الموقع الحالي:** Lines 439-1241 (802 lines)
**الوظائف:**
- Building code input with auto-generation
- Map-based building search
- Building list with filters
- Building selection confirmation

**Methods to extract:**
```python
- _create_building_step()           # Main UI
- _on_building_code_changed()       # Validation
- _open_map_search_dialog()         # Map integration
- _load_buildings_map()              # Map data
- _on_building_selected_from_map()  # Map callback
- _load_buildings()                  # Data loading
- _filter_buildings()                # Filtering
- _search_buildings()                # Search
- _on_building_selected()            # Selection
- _on_building_confirmed()           # Confirmation
```

**المخرج:**
```python
# step_1_building_selection.py
class BuildingSelectionStep(BaseStep):
    def __init__(self, context: SurveyContext, parent=None):
        self.context = context
        # ...

    def validate(self) -> bool:
        """Validate building is selected."""
        return self.context.selected_building is not None

    def save(self) -> bool:
        """Save building to context."""
        # ...
```

---

### Step 2: Unit Management (~400 lines)
**الموقع الحالي:** Lines 1243-1956 (713 lines)
**الوظائف:**
- Select existing unit or create new
- Unit form with all fields
- Unit list display
- Unit selection

**Methods to extract:**
```python
- _create_unit_step()               # Main UI
- _check_unit_uniqueness()          # Validation
- _on_unit_option_changed()         # Toggle create/select
- _load_units_for_building()        # Data loading
- _create_unit_card()               # Unit display
- _create_detail_label()            # UI helper
- _on_unit_card_clicked()           # Selection
- _show_add_unit_dialog()           # Dialog
- _on_unit_selected()               # Selection
- _save_new_unit_data()             # Save
```

---

### Step 3: Household Profile (~350 lines)
**الموقع الحالي:** Lines 1958-2457 (499 lines)
**الوظائف:**
- Household information form
- Household list
- Add/edit/delete household

**Methods to extract:**
```python
- _create_household_step()          # Main UI
- _on_household_selected()          # Selection
- _save_household()                 # Save
- _clear_household_form()           # Reset
- _delete_household()               # Delete
- _refresh_households_list()        # Refresh
```

---

### Step 4: Person Registration (~450 lines)
**الموقع الحالي:** Lines 2459-2758 (299 lines)
**الوظائف:**
- Person form (opens PersonDialog)
- Person list display
- Person CRUD operations

**Methods to extract:**
```python
- _create_persons_step()            # Main UI
- _add_person()                     # Add
- _create_person_row_card()         # Display
- _refresh_persons_list()           # Refresh
- _view_person()                    # View
- _delete_person_by_id()            # Delete
```

---

### Step 5: Relations & Evidence (~400 lines)
**الموقع الحالي:** Lines 2760-3248 (488 lines)
**الوظائف:**
- Define relations between persons
- Attach evidence to relations
- Relation list management

**Methods to extract:**
```python
- _create_relations_step()          # Main UI
- _pick_evidence_files()            # File picker
- _populate_relations_persons()     # Data loading
- _on_relation_person_changed()     # Selection
- _add_relation()                   # Add
- _on_relation_selected()           # Selection
- _add_evidence_to_relation()       # Evidence
- _remove_evidence_from_relation()  # Evidence
- _refresh_relation_evidence_list() # Refresh
- _save_relation()                  # Save
- _delete_relation()                # Delete
- _refresh_relations_list()         # Refresh
```

---

### Step 6: Claim Evaluation (~350 lines)
**الموقع الحالي:** Lines 3250-3527 (277 lines)
**الوظائف:**
- Evaluate household for claim
- Create claim if eligible
- Claim form

**Methods to extract:**
```python
- _create_claim_step()              # Main UI
- _evaluate_for_claim()             # Evaluation
- _save_claim_data()                # Save
- _create_claim()                   # Create
```

---

### Step 7: Review & Submit (~350 lines)
**الموقع الحالي:** Lines 3529-4104 (575 lines)
**الوظائف:**
- Summary of all data
- Final validation
- Submit survey

**Methods to extract:**
```python
- _create_review_step()             # Main UI
- _create_review_card()             # Card UI
- _create_review_field()            # Field UI
- _create_review_section()          # Section UI
- _run_final_validation()           # Validation
- _populate_review()                # Data population
- _populate_unit_review_card()      # Unit summary
- _populate_household_review_card() # Household summary
- _populate_persons_review_card()   # Persons summary
- _populate_relations_review_card() # Relations summary
- _populate_claim_review_card()     # Claim summary
- _finalize_survey()                # Final submit
- _commit_survey()                  # Database commit
```

---

## 🔧 Supporting Files

### wizard_context.py (~150 lines)
**Purpose:** Shared state across all steps

```python
# wizard_context.py
from dataclasses import dataclass
from typing import Optional, List, Dict
from models.building import Building
from models.unit import PropertyUnit
from models.person import Person

@dataclass
class SurveyContext:
    """Shared state for Office Survey Wizard."""

    # Step 1
    selected_building: Optional[Building] = None

    # Step 2
    selected_unit: Optional[PropertyUnit] = None
    unit_option: str = "existing"  # "existing" or "new"
    new_unit_data: Optional[Dict] = None

    # Step 3
    households: List[Dict] = None

    # Step 4
    persons: List[Person] = None

    # Step 5
    relations: List[Dict] = None

    # Step 6
    claim_data: Optional[Dict] = None

    # Metadata
    reference_number: str = None
    created_at: datetime = None
    survey_status: str = "draft"

    def __post_init__(self):
        if self.households is None:
            self.households = []
        if self.persons is None:
            self.persons = []
        if self.relations is None:
            self.relations = []

    def reset(self) -> None:
        """Reset context."""
        self.__init__()

    def to_dict(self) -> Dict:
        """Export context as dict."""
        # ...

    @classmethod
    def from_dict(cls, data: Dict) -> 'SurveyContext':
        """Load context from dict."""
        # ...
```

---

### wizard_main.py (~300 lines)
**Purpose:** Main coordinator - orchestrates steps

```python
# wizard_main.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from .wizard_context import SurveyContext
from .steps import *

class OfficeSurveyWizard(QWidget):
    """
    Office Survey Wizard - Main Coordinator.

    Orchestrates 7 steps without business logic.
    All logic delegated to step classes.
    """

    saved = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.context = SurveyContext()

        self.steps = []
        self._setup_steps()
        self._setup_ui()

    def _setup_steps(self):
        """Initialize all step instances."""
        self.steps = [
            BuildingSelectionStep(self.context, self.db, self.i18n, self),
            UnitManagementStep(self.context, self.db, self.i18n, self),
            HouseholdProfileStep(self.context, self.db, self.i18n, self),
            PersonRegistrationStep(self.context, self.db, self.i18n, self),
            RelationsStep(self.context, self.db, self.i18n, self),
            ClaimEvaluationStep(self.context, self.db, self.i18n, self),
            ReviewSubmitStep(self.context, self.db, self.i18n, self)
        ]

    def _setup_ui(self):
        """Setup wizard UI."""
        layout = QVBoxLayout(self)

        # Stacked widget for steps
        self.stacked = QStackedWidget()
        for step in self.steps:
            self.stacked.addWidget(step)

        layout.addWidget(self.stacked)

        # Navigation buttons
        # Progress bar
        # ...

    def _on_next(self):
        """Go to next step."""
        current_step = self.steps[self.stacked.currentIndex()]

        # Validate current step
        if not current_step.validate():
            return

        # Save current step
        if not current_step.save():
            return

        # Move to next
        if self.stacked.currentIndex() < len(self.steps) - 1:
            self.stacked.setCurrentIndex(self.stacked.currentIndex() + 1)
            self._prepare_step()

    def _on_previous(self):
        """Go to previous step."""
        if self.stacked.currentIndex() > 0:
            self.stacked.setCurrentIndex(self.stacked.currentIndex() - 1)
            self._prepare_step()

    def _prepare_step(self):
        """Prepare current step for display."""
        current_step = self.steps[self.stacked.currentIndex()]
        current_step.load()  # Load data into UI

    def _on_finish(self):
        """Finish wizard - commit survey."""
        # Final validation
        for step in self.steps:
            if not step.validate():
                return

        # Commit to database
        try:
            self._commit_survey()
            self.saved.emit()
        except Exception as e:
            logger.error(f"Failed to commit survey: {e}")
            # Show error
```

---

### base_step.py (~100 lines)
**Purpose:** Base class for all steps

```python
# steps/base_step.py
from abc import ABC, abstractmethod
from PyQt5.QtWidgets import QWidget
from ..wizard_context import SurveyContext

class BaseStep(QWidget, ABC):
    """Base class for wizard steps."""

    def __init__(self, context: SurveyContext, db, i18n, parent=None):
        super().__init__(parent)
        self.context = context
        self.db = db
        self.i18n = i18n
        self._setup_ui()

    @abstractmethod
    def _setup_ui(self):
        """Setup step UI. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """
        Validate step data.

        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod
    def save(self) -> bool:
        """
        Save step data to context.

        Returns:
            True if saved successfully, False otherwise
        """
        pass

    def load(self):
        """
        Load data from context into UI.

        Called when step becomes active.
        Override if needed.
        """
        pass

    def _show_error(self, message: str):
        """Show error message."""
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(self, "خطأ", message)

    def _show_success(self, message: str):
        """Show success message."""
        from ui.components.toast import Toast
        Toast.show(self, message, Toast.SUCCESS)
```

---

## ✅ فوائد التقسيم

### 1. **Maintainability** (قابلية الصيانة)
- ✅ كل step في ملف منفصل (< 450 lines)
- ✅ سهولة العثور على الكود
- ✅ تغييرات معزولة (لا تؤثر على steps أخرى)

### 2. **Testability** (قابلية الاختبار)
- ✅ يمكن اختبار كل step بشكل مستقل
- ✅ Mock context سهل
- ✅ Unit tests أبسط

### 3. **Reusability** (إعادة الاستخدام)
- ✅ يمكن إعادة استخدام steps في wizards أخرى
- ✅ Components قابلة لإعادة الاستخدام

### 4. **Clean Code**
- ✅ SRP - Single Responsibility Principle
- ✅ OCP - Open/Closed Principle
- ✅ DRY - Don't Repeat Yourself

### 5. **Performance**
- ✅ Lazy loading - تحميل steps عند الحاجة فقط
- ✅ Memory efficient

---

## 🚀 خطة التنفيذ

### Phase 1: Setup (يوم 1)
1. ✅ إنشاء structure الجديد
2. ✅ نقل SurveyContext إلى wizard_context.py
3. ✅ إنشاء base_step.py
4. ✅ إنشاء wizard_main.py (skeleton)

### Phase 2: Extract Steps (أيام 2-8)
**كل step = 1 يوم عمل:**
- **Day 2:** Extract Step 1 - Building Selection
- **Day 3:** Extract Step 2 - Unit Management
- **Day 4:** Extract Step 3 - Household Profile
- **Day 5:** Extract Step 4 - Person Registration
- **Day 6:** Extract Step 5 - Relations
- **Day 7:** Extract Step 6 - Claim Evaluation
- **Day 8:** Extract Step 7 - Review & Submit

**بعد كل step:**
- ✅ Test step independently
- ✅ Test في context الـ wizard
- ✅ Verify application runs
- ✅ نقطة توقف للمراجعة

### Phase 3: Integration (يوم 9)
1. ✅ Complete wizard_main.py
2. ✅ Connect all steps
3. ✅ Navigation logic
4. ✅ Progress tracking

### Phase 4: Testing & Cleanup (يوم 10)
1. ✅ Integration tests
2. ✅ Manual testing
3. ✅ حذف old wizard file
4. ✅ Update imports

---

## 📊 Metrics

### Before:
- **1 file:** 4531 lines
- **1 class:** 84 methods
- **Complexity:** Very High
- **Maintainability:** Poor
- **Testability:** Difficult

### After:
- **14 files:** ~3850 lines total
- **10 classes:** avg 8 methods each
- **Complexity:** Low-Medium
- **Maintainability:** Excellent
- **Testability:** Easy

### Improvements:
- ✅ **15% code reduction** (4531 → 3850 lines)
- ✅ **84% smaller files** (4531 → max 450 lines)
- ✅ **90% fewer methods per class** (84 → 8 avg)
- ✅ **100% testable** (0% → 100%)

---

## ⚠️ Risks & Mitigation

### Risk 1: Breaking existing functionality
**Mitigation:**
- Extract incrementally (1 step at a time)
- Test after each extraction
- Keep old wizard until all steps working

### Risk 2: Context synchronization issues
**Mitigation:**
- Clear context ownership model
- Steps only read/write their own section
- Validation at each step

### Risk 3: Import circular dependencies
**Mitigation:**
- Clear import hierarchy
- Base classes in separate files
- Late imports if needed

---

## 🎯 Success Criteria

### Must Have:
- ✅ All 7 steps extracted and working
- ✅ Wizard completes end-to-end
- ✅ All data saved correctly
- ✅ No breaking changes
- ✅ Tests pass

### Nice to Have:
- ✅ Improved performance
- ✅ Better error messages
- ✅ Enhanced validation

---

## 📝 Next Steps

1. **Get approval** for this plan
2. **Create directory structure**
3. **Start with STEP 6** - Extract Building Selection
4. **Iterate** through all steps
5. **Test & validate**
6. **Deploy & monitor**

---

**Estimated Time:** 10 working days
**Impact:** High - Major architectural improvement
**Risk:** Medium - Can be done incrementally

✅ **Ready to begin!**
