# خطة التنفيذ التفصيلية - UN-Habitat TRRCMS Desktop Frontend
# Detailed Implementation Roadmap

**تاريخ الإعداد:** 2026-01-21
**الحالة الحالية:** 65-70% مطابقة للمتطلبات
**الهدف:** 95%+ مطابقة مع FSD v5 و Use Cases

---

## منهجية العمل | Work Methodology

### القواعد الأساسية:
1. ✅ **كل خطوة = 3-4 ملفات فقط** - التوقف بعدها للمراجعة
2. ✅ **التحقق من عمل التطبيق** - بعد كل خطوة قبل الانتقال
3. ✅ **عدم إنشاء ملف جديد** - إلا بعد التأكد من عدم وجوده
4. ✅ **ممنوع Git commits** - هذه مهمة المطور
5. ✅ **فقط Tests للتحقق** - pytest بعد كل خطوة
6. ✅ **DRY, SOLID, Clean Code** - في كل تعديل
7. ✅ **لا تغيير في شكل UI** - فقط فصل Logic
8. ✅ **Professional approach** - Single Source of Truth

---

## 🎯 Sprint 1: Architecture Foundation (الأسبوع الأول)

### المرحلة الأولى: فصل Business Logic من UI
**الهدف:** إزالة 100% من Business Logic من UI Pages

---

## 📋 STEP 1: تحضير Services المركزية
**المدة:** 2-3 ساعات
**الملفات:** 4 ملفات

### الملفات المطلوبة:

#### 1.1 ✅ التحقق من وجود PersonService
```bash
# التحقق
ls -la services/person_service.py
```

**إذا لم يكن موجوداً، إنشاء:**
```python
# services/person_service.py
"""
Person Service - centralized business logic for Person operations.
"""
from typing import Optional, List, Dict, Any
from models.person import Person
from repositories.person_repository import PersonRepository
from services.validation.validation_factory import ValidationFactory

class PersonService:
    """Service layer for Person operations."""

    def __init__(self, repository: PersonRepository):
        self.repository = repository
        self.validator = ValidationFactory.get_validator('person')

    def create_person(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create person with validation.
        Returns: {'success': bool, 'person': Person, 'error': str}
        """
        # Validate
        validation_result = self.validator.validate(data)
        if not validation_result.is_valid:
            return {
                'success': False,
                'error': ', '.join(validation_result.errors),
                'person': None
            }

        # Create Person model
        person = Person(
            first_name=data.get('first_name'),
            father_name=data.get('father_name'),
            grandfather_name=data.get('grandfather_name'),
            family_name=data.get('family_name'),
            national_id=data.get('national_id'),
            gender=data.get('gender'),
            birth_year=data.get('birth_year'),
            nationality=data.get('nationality')
        )

        # Save
        created_person = self.repository.create(person)

        return {
            'success': True,
            'person': created_person,
            'error': None
        }

    def update_person(self, person_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update person with validation."""
        # Similar pattern
        pass

    def get_person(self, person_id: str) -> Optional[Person]:
        """Get person by ID."""
        return self.repository.get(person_id)

    def search_persons(self, criteria: Dict[str, Any]) -> List[Person]:
        """Search persons with criteria."""
        return self.repository.search(criteria)
```

#### 1.2 ✅ التحقق من وجود BuildingService
```bash
# التحقق
ls -la services/building_service.py
```

**إذا لم يكن موجوداً، إنشاء مماثل لـ PersonService**

#### 1.3 ✅ التحقق من وجود ClaimService
```bash
# التحقق
ls -la services/claim_service.py
```

#### 1.4 ✅ تحديث ValidationService
```python
# services/validation_service.py - التأكد من وجود جميع validators
```

### ✅ نقطة توقف 1: Testing
```bash
# Run tests
cd c:\Users\Laptop-PC\.javacpp\Desktop\un\Habitat-Desktop
python -m pytest tests/ -v

# إذا نجحت جميع الاختبارات → Continue
# إذا فشلت → إصلاح ثم إعادة الاختبار
```

**✋ انتظار الموافقة قبل الانتقال للخطوة 2**

---

## 📋 STEP 2: Refactor PersonsPage (إزالة Repository calls)
**المدة:** 2-3 ساعات
**الملفات:** 2 ملفات

### 2.1 ملف: `ui/pages/persons_page.py`

#### التحقق من الحالة الحالية:
```bash
# Count repository calls
grep -n "person_repo\." ui/pages/persons_page.py | wc -l
grep -n "PersonRepository" ui/pages/persons_page.py
```

#### التعديلات المطلوبة:

**قبل:**
```python
# ❌ Direct repository access
self.person_repo = PersonRepository(db)

def _on_add_person(self):
    person = Person(...)
    self.person_repo.create(person)
```

**بعد:**
```python
# ✅ Use Controller
from controllers.person_controller import PersonController

self.person_controller = PersonController()

def _on_add_person(self):
    data = self._get_form_data()
    result = self.person_controller.create_person(data)

    if result['success']:
        self._refresh_table()
        self._show_success("Person created successfully")
    else:
        self._show_error(result['error'])

def _get_form_data(self) -> Dict[str, Any]:
    """Extract form data."""
    return {
        'first_name': self.first_name_input.text(),
        'father_name': self.father_name_input.text(),
        # ...
    }
```

### 2.2 ملف: `controllers/person_controller.py`

**التأكد من وجود جميع Methods المطلوبة:**
```python
# Verify methods exist:
# - create_person(data)
# - update_person(person_id, data)
# - delete_person(person_id)
# - search_persons(criteria)
# - get_person(person_id)
```

### ✅ نقطة توقف 2: Testing
```bash
# Test PersonsPage
python -m pytest tests/ui/ -k "person" -v

# Manual test
python main.py
# Navigate to Persons page
# Try: Add, Edit, Search, Delete person

# ✅ If works → Continue
# ❌ If fails → Fix and retest
```

**✋ انتظار الموافقة قبل الانتقال للخطوة 3**

---

## 📋 STEP 3: Refactor BuildingsPage (إزالة Repository calls)
**المدة:** 3-4 ساعات
**الملفات:** 3 ملفات

### 3.1 ملف: `ui/pages/buildings_page.py` (1778 سطر)

#### Phase 3.1a: Remove Direct Repository Access

**التحقق:**
```bash
grep -n "building_repo\." ui/pages/buildings_page.py | head -20
```

**التعديلات:**
```python
# Before: ❌
self.building_repo = BuildingRepository(db)
self.building_repo.create(building)

# After: ✅
self.building_controller = BuildingController()
self.building_controller.create_building(data)
```

#### Phase 3.1b: Extract Validation Logic

**Before (في UI):**
```python
def _validate_building_data(self):
    # 50 lines of validation code
    if not self.building_number.text():
        QMessageBox.warning(...)
        return False
    # ...
```

**After (استخدام Service):**
```python
def _validate_building_data(self) -> bool:
    data = self._get_form_data()
    result = self.validation_service.validate_building(data)

    if not result.is_valid:
        self._show_validation_errors(result.errors)
        return False
    return True
```

### 3.2 ملف: `ui/pages/add_building_page.py`

**نفس النمط - Remove repository access**

### 3.3 ملف: `controllers/building_controller.py`

**التحقق من Methods:**
```python
# Verify:
# - create_building(data)
# - update_building(building_id, data)
# - delete_building(building_id)
# - search_buildings(criteria)
# - assign_to_field_team(building_id, team_id)
```

### ✅ نقطة توقف 3: Testing
```bash
# Test BuildingsPage
python -m pytest tests/ -k "building" -v

# Manual test
python main.py
# Test: Add building, Edit, Search, Map selection

# Verify:
# ✅ Building ID generation (17 digits)
# ✅ Map picker works
# ✅ Admin hierarchy dropdowns
# ✅ Save to database
```

**✋ انتظار الموافقة قبل الانتقال للخطوة 4**

---

## 📋 STEP 4: Refactor ClaimsPage
**المدة:** 2-3 ساعات
**الملفات:** 3 ملفات

### 4.1 ملف: `ui/pages/claims_page.py`

#### Remove Repository Access + Use WorkflowService

**Before:**
```python
# ❌ في UI
def transition_claim(self, claim_id, new_status):
    # 30 lines validation
    # 20 lines business rules
    claim.status = new_status
    self.claim_repo.update(claim)
```

**After:**
```python
# ✅ Use WorkflowService
def transition_claim(self, claim_id, new_status):
    result = self.workflow_service.transition_claim(
        claim_id=claim_id,
        to_status=new_status,
        user_id=self.current_user.user_id
    )

    if result['success']:
        self._refresh_claim_view()
    else:
        self._show_error(result['error'])
```

### 4.2 ملف: `services/workflow_service.py`

**التأكد من Methods:**
```python
# Verify:
# - transition_claim(claim_id, to_status, user_id)
# - can_transition(claim_id, to_status)
# - get_available_transitions(claim_id)
```

### 4.3 ملف: `controllers/claim_controller.py`

**التحقق والتحديث إذا لزم**

### ✅ نقطة توقف 4: Testing
```bash
python -m pytest tests/ -k "claim" -v

# Manual test workflow
python main.py
# Test claim status transitions
```

**✋ انتظار الموافقة قبل الانتقال للمرحلة الثانية**

---

## 🎯 Sprint 2: Wizard Refactoring (الأسبوع الثاني)

### المرحلة الثانية: تقسيم Wizard إلى Modules

---

## 📋 STEP 5: تحليل وتخطيط office_survey_wizard.py
**المدة:** 1-2 ساعات
**الملفات:** 1 ملف (قراءة فقط)

### 5.1 فهم البنية الحالية

```bash
# Count lines
wc -l ui/wizards/office_survey_wizard.py
# Expected: 4531 lines

# Analyze structure
grep -n "class.*Step" ui/wizards/office_survey_wizard.py
grep -n "def.*setup" ui/wizards/office_survey_wizard.py
```

### 5.2 التخطيط للتقسيم

**الهيكل المطلوب:**
```
ui/wizards/office_survey/
├── __init__.py
├── wizard_main.py               # Main coordinator (< 300 lines)
├── steps/
│   ├── __init__.py
│   ├── step_building_selection.py    # Step 1 (< 400 lines)
│   ├── step_unit_management.py       # Step 2 (< 400 lines)
│   ├── step_household_profile.py     # Step 3 (< 400 lines)
│   ├── step_person_registration.py   # Step 4 (< 500 lines)
│   ├── step_relations.py             # Step 5 (< 400 lines)
│   ├── step_evidence.py              # Step 6 (< 400 lines)
│   └── step_review.py                # Step 7 (< 300 lines)
└── wizard_context.py            # Shared state (< 200 lines)
```

**إجمالي:** 7 ملفات صغيرة بدلاً من 1 ملف ضخم

### 5.3 إنشاء الهيكل الأساسي

```bash
# Create directory
mkdir -p ui/wizards/office_survey/steps

# Verify doesn't exist first
ls -la ui/wizards/office_survey/
```

### ✅ نقطة توقف 5: مراجعة الخطة
```
# No code changes yet - just planning
# Review directory structure
```

**✋ انتظار الموافقة قبل البدء بالتقسيم**

---

## 📋 STEP 6: Extract Step 1 - Building Selection
**المدة:** 2-3 ساعات
**الملفات:** 3 ملفات

### 6.1 ملف جديد: `ui/wizards/office_survey/steps/step_building_selection.py`

**التحقق أولاً:**
```python
# Check if file exists
import os
path = "ui/wizards/office_survey/steps/step_building_selection.py"
if os.path.exists(path):
    print("❌ File exists - review before overwriting")
else:
    print("✅ OK to create")
```

**إنشاء:**
```python
# -*- coding: utf-8 -*-
"""
Office Survey Wizard - Step 1: Building Selection
Extracted from office_survey_wizard.py for modularity.
"""
from typing import Optional
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from controllers.building_controller import BuildingController
from ..wizard_context import WizardContext

class BuildingSelectionStep(QWidget):
    """Step 1: Select building for office survey."""

    def __init__(self, context: WizardContext, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.context = context
        self.building_controller = BuildingController()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup UI for building selection."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Select Building")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(title)

        # Building search widget
        # Map widget
        # Building list
        # ... (extract from wizard)

    def validate(self) -> bool:
        """Validate step data."""
        if not self.context.selected_building:
            self._show_error("Please select a building")
            return False
        return True

    def save(self) -> bool:
        """Save step data to context."""
        self.context.selected_building = self.get_selected_building()
        return True
```

### 6.2 ملف: `ui/wizards/office_survey/wizard_context.py`

**إنشاء Shared State:**
```python
# -*- coding: utf-8 -*-
"""
Wizard Context - Shared state across wizard steps.
"""
from typing import Optional, Dict, Any, List
from models.building import Building
from models.person import Person
from models.unit import PropertyUnit

class WizardContext:
    """Shared state for Office Survey Wizard."""

    def __init__(self):
        # Step 1
        self.selected_building: Optional[Building] = None

        # Step 2
        self.units: List[PropertyUnit] = []

        # Step 3
        self.household_head: Optional[Person] = None

        # Step 4
        self.persons: List[Person] = []

        # Step 5
        self.relations: List[Dict[str, Any]] = []

        # Step 6
        self.evidence: List[Dict[str, Any]] = []

    def reset(self) -> None:
        """Reset context."""
        self.__init__()

    def to_dict(self) -> Dict[str, Any]:
        """Export context as dict."""
        return {
            'building_id': self.selected_building.building_id if self.selected_building else None,
            'units': [u.to_dict() for u in self.units],
            'persons': [p.to_dict() for p in self.persons],
            # ...
        }
```

### 6.3 ملف: `ui/wizards/office_survey/__init__.py`

```python
# -*- coding: utf-8 -*-
"""Office Survey Wizard module."""

from .wizard_main import OfficeSurveyWizard

__all__ = ['OfficeSurveyWizard']
```

### ✅ نقطة توقف 6: Testing
```bash
# Test imports
python -c "from ui.wizards.office_survey.steps.step_building_selection import BuildingSelectionStep"

# Run app - verify no breakage
python main.py
```

**✋ انتظار الموافقة قبل المتابعة**

---

## 📋 STEP 7-12: Extract Remaining Steps (نفس النمط)
**المدة:** يومين (2-3 ساعات لكل step)**

### الخطوات المتبقية:
- **STEP 7:** Extract Step 2 - Unit Management (3 files)
- **STEP 8:** Extract Step 3 - Household Profile (3 files)
- **STEP 9:** Extract Step 4 - Person Registration (4 files) - الأكبر
- **STEP 10:** Extract Step 5 - Relations (3 files)
- **STEP 11:** Extract Step 6 - Evidence (3 files)
- **STEP 12:** Extract Step 7 - Review (2 files)

**بعد كل STEP:**
✅ نقطة توقف + Testing + انتظار موافقة

---

## 📋 STEP 13: Create Wizard Main Coordinator
**المدة:** 2-3 ساعات
**الملفات:** 2 ملفات

### 13.1 ملف: `ui/wizards/office_survey/wizard_main.py`

```python
# -*- coding: utf-8 -*-
"""
Office Survey Wizard - Main Coordinator
Orchestrates wizard steps without business logic.
"""
from typing import List, Optional
from PyQt5.QtWidgets import QWizard, QWidget
from .wizard_context import WizardContext
from .steps.step_building_selection import BuildingSelectionStep
# ... import all steps

class OfficeSurveyWizard(QWizard):
    """Main wizard coordinator - delegates to steps."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.context = WizardContext()
        self._setup_wizard()

    def _setup_wizard(self) -> None:
        """Setup wizard pages."""
        self.setWindowTitle("Office Survey")

        # Add steps
        self.addPage(BuildingSelectionStep(self.context, self))
        self.addPage(UnitManagementStep(self.context, self))
        # ... add all 7 steps

    def accept(self) -> None:
        """On finish - save survey."""
        # Delegate to SurveyService
        result = self.survey_service.save_office_survey(
            self.context.to_dict()
        )

        if result['success']:
            super().accept()
        else:
            self._show_error(result['error'])
```

### 13.2 Update: `ui/pages/dashboard_page.py` (or wherever wizard is called)

```python
# Before:
from ui.wizards.office_survey_wizard import OfficeSurveyWizard

# After:
from ui.wizards.office_survey import OfficeSurveyWizard  # Same import!
```

### ✅ نقطة توقف 13: Integration Testing
```bash
# Full wizard test
python main.py
# Navigate to Office Survey
# Go through all 7 steps
# Verify:
# ✅ Navigation works
# ✅ Context shared between steps
# ✅ Validation works
# ✅ Final submission works
```

**✋ انتظار الموافقة قبل الانتقال للمرحلة الثالثة**

---

## 🎯 Sprint 3: Map & GIS Integration (الأسبوع الثالث)

### المرحلة الثالثة: إكمال وظائف الخريطة والـ Polygons

---

## 📋 STEP 14: تحليل Map Components الحالية
**المدة:** 1 ساعة
**الملفات:** قراءة فقط

### 14.1 فحص الملفات الموجودة:

```bash
# List map-related files
find ui/components -name "*map*"
# Expected:
# - map_page.py
# - map_picker_dialog.py
# - map_viewer_dialog.py
# - building_map_widget.py
# - map_coordinate_picker.py

# Check Leaflet integration
grep -n "leaflet" ui/components/map_picker_dialog.py | head -10
```

### 14.2 التحقق من PostGIS Services:

```bash
ls -la services/*gis*.py services/*map*.py
# Expected:
# - services/postgis_service.py
# - services/map_service.py
# - services/geo_api_service.py
```

### ✅ نقطة توقف 14: مراجعة الوضع الحالي
```
# Document findings:
# - Which polygon features exist?
# - Which are missing?
# - Is Leaflet.Draw included?
```

**✋ انتظار الموافقة قبل البدء**

---

## 📋 STEP 15: تحديث MapPickerDialog - إضافة Polygon Editing
**المدة:** 3-4 ساعات
**الملفات:** 3 ملفات

### 15.1 ملف: `ui/components/map_picker_dialog.py`

#### التحقق من الحالة الحالية:
```python
# Read file
with open('ui/components/map_picker_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Check for Leaflet.Draw
if 'L.Draw' in content:
    print("✅ Leaflet.Draw already included")
else:
    print("❌ Need to add Leaflet.Draw")
```

#### إضافة Polygon Editing:

**في HTML Template (داخل الملف):**
```javascript
// Add Leaflet.Draw
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>

// Add drawing controls
var drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

var drawControl = new L.Control.Draw({
    draw: {
        polygon: {
            allowIntersection: false,
            showArea: true,
            metric: true,
            shapeOptions: {
                color: '#3388ff',
                weight: 2
            }
        },
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: true,
        rectangle: {
            shapeOptions: {
                color: '#3388ff'
            }
        }
    },
    edit: {
        featureGroup: drawnItems,
        remove: true
    }
});
map.addControl(drawControl);

// Handle polygon created
map.on(L.Draw.Event.CREATED, function(event) {
    var layer = event.layer;
    drawnItems.addLayer(layer);

    // Get polygon coordinates
    var coords = layer.getLatLngs()[0];
    var wkt = coordsToWKT(coords);

    // Send to Python
    window.polygonCreated(wkt);
});

// Handle polygon edited
map.on(L.Draw.Event.EDITED, function(event) {
    var layers = event.layers;
    layers.eachLayer(function(layer) {
        var coords = layer.getLatLngs()[0];
        var wkt = coordsToWKT(coords);
        window.polygonEdited(wkt);
    });
});

// WKT conversion
function coordsToWKT(coords) {
    var wkt = 'POLYGON((';
    coords.forEach(function(coord, i) {
        wkt += coord.lng + ' ' + coord.lat;
        if (i < coords.length - 1) wkt += ', ';
    });
    wkt += ', ' + coords[0].lng + ' ' + coords[0].lat; // Close polygon
    wkt += '))';
    return wkt;
}
```

**في Python Side:**
```python
class MapPickerDialog(QDialog):
    polygon_selected = pyqtSignal(str)  # WKT string

    def __init__(self, ...):
        # ...
        self.selected_polygon_wkt = None

        # Connect JS → Python
        self.web_view.page().runJavaScript("""
            window.polygonCreated = function(wkt) {
                // Send to Python
            }
        """)

    def get_polygon_wkt(self) -> Optional[str]:
        """Get selected polygon as WKT."""
        return self.selected_polygon_wkt
```

### 15.2 ملف: `services/postgis_service.py`

**إضافة Polygon Validation:**
```python
def validate_polygon(self, wkt: str) -> Dict[str, Any]:
    """
    Validate polygon geometry.
    Returns: {'valid': bool, 'error': str, 'area_sqm': float}
    """
    cursor = self.db.execute_query("""
        SELECT
            ST_IsValid(ST_GeomFromText(%s, 4326)) as is_valid,
            ST_IsValidReason(ST_GeomFromText(%s, 4326)) as reason,
            ST_Area(ST_GeomFromText(%s, 4326)::geography) as area_sqm
    """, (wkt, wkt, wkt))

    result = cursor.fetchone()

    return {
        'valid': result[0],
        'error': None if result[0] else result[1],
        'area_sqm': result[2] if result[0] else 0
    }
```

### 15.3 ملف: `ui/pages/add_building_page.py`

**استخدام Polygon Picker:**
```python
def _on_select_location_on_map(self):
    """Open map to select building polygon."""
    dialog = MapPickerDialog(
        mode='polygon',  # NEW: support polygon mode
        parent=self
    )

    if dialog.exec_() == QDialog.Accepted:
        polygon_wkt = dialog.get_polygon_wkt()

        # Validate polygon
        validation = self.postgis_service.validate_polygon(polygon_wkt)

        if validation['valid']:
            self.building_geometry = polygon_wkt
            self.area_sqm_label.setText(f"{validation['area_sqm']:.2f} m²")
        else:
            QMessageBox.warning(self, "Invalid Polygon", validation['error'])
```

### ✅ نقطة توقف 15: Testing Polygons
```bash
# Test polygon drawing
python main.py
# Navigate to Add Building
# Click "Select on Map"
# Test:
# ✅ Draw polygon
# ✅ Edit polygon (drag vertices)
# ✅ Delete polygon
# ✅ Area calculation displays
# ✅ WKT saved to database
```

**✋ انتظار الموافقة قبل المتابعة**

---

## 📋 STEP 16: عرض Building Footprints على الخريطة
**المدة:** 2-3 ساعات
**الملفات:** 2 ملفات

### 16.1 ملف: `ui/pages/map_page.py`

**إضافة Building Polygons Layer:**

```python
def _load_buildings_on_map(self):
    """Load building footprints from database."""
    # Get buildings with geometry
    buildings = self.building_controller.get_buildings_with_geometry()

    # Convert to GeoJSON
    geojson_features = []
    for building in buildings:
        if building.building_geometry:
            feature = {
                'type': 'Feature',
                'geometry': self._wkt_to_geojson(building.building_geometry),
                'properties': {
                    'building_id': building.building_id,
                    'building_number': building.building_number,
                    'status': building.status,
                    'color': self._get_status_color(building.status)
                }
            }
            geojson_features.append(feature)

    geojson = {
        'type': 'FeatureCollection',
        'features': geojson_features
    }

    # Send to map
    self._add_geojson_layer(geojson)

def _add_geojson_layer(self, geojson: Dict):
    """Add GeoJSON layer to map."""
    js_code = f"""
        var buildingsLayer = L.geoJSON({json.dumps(geojson)}, {{
            style: function(feature) {{
                return {{
                    color: feature.properties.color,
                    weight: 2,
                    fillOpacity: 0.4
                }};
            }},
            onEachFeature: function(feature, layer) {{
                layer.bindPopup(
                    '<b>Building ID:</b> ' + feature.properties.building_id + '<br>' +
                    '<b>Number:</b> ' + feature.properties.building_number + '<br>' +
                    '<b>Status:</b> ' + feature.properties.status
                );
            }}
        }}).addTo(map);
    """
    self.web_view.page().runJavaScript(js_code)

def _get_status_color(self, status: str) -> str:
    """Get color for building status."""
    colors = {
        'surveyed': '#28a745',    # Green
        'pending': '#ffc107',     # Yellow
        'verified': '#007bff',    # Blue
        'rejected': '#dc3545'     # Red
    }
    return colors.get(status, '#6c757d')  # Gray default
```

### 16.2 ملف: `controllers/building_controller.py`

**إضافة Method:**
```python
def get_buildings_with_geometry(self) -> List[Building]:
    """Get all buildings that have geometry defined."""
    return self.repository.get_buildings_with_geometry()
```

**و في Repository:**
```python
# repositories/building_repository.py
def get_buildings_with_geometry(self) -> List[Building]:
    """Get buildings with non-null geometry."""
    query = """
        SELECT * FROM buildings
        WHERE building_geometry IS NOT NULL
    """
    cursor = self.db.execute_query(query)
    return [self._map_to_building(row) for row in cursor.fetchall()]
```

### ✅ نقطة توقف 16: Testing Building Display
```bash
python main.py
# Navigate to Map page
# Verify:
# ✅ Building polygons displayed
# ✅ Color-coded by status
# ✅ Popup shows building info
# ✅ Click polygon → opens building details
```

**✋ انتظار الموافقة قبل المتابعة**

---

## 📋 STEP 17: إضافة Spatial Queries UI
**المدة:** 2-3 ساعات
**الملفات:** 3 ملفات

### 17.1 ملف: `ui/pages/map_page.py` (إضافة Spatial Filter Widget)

```python
def _setup_spatial_filter_ui(self):
    """Add spatial filtering controls."""
    filter_widget = QGroupBox("Spatial Filters")
    layout = QVBoxLayout(filter_widget)

    # Buffer search
    buffer_layout = QHBoxLayout()
    buffer_layout.addWidget(QLabel("Find buildings within:"))
    self.buffer_distance_input = QSpinBox()
    self.buffer_distance_input.setRange(10, 1000)
    self.buffer_distance_input.setValue(100)
    self.buffer_distance_input.setSuffix(" meters")
    buffer_layout.addWidget(self.buffer_distance_input)

    self.buffer_search_btn = QPushButton("Search")
    self.buffer_search_btn.clicked.connect(self._on_buffer_search)
    buffer_layout.addWidget(self.buffer_search_btn)
    layout.addLayout(buffer_layout)

    # Polygon selection
    polygon_search_btn = QPushButton("Draw Polygon to Select Buildings")
    polygon_search_btn.clicked.connect(self._on_polygon_selection)
    layout.addWidget(polygon_search_btn)

    return filter_widget

def _on_buffer_search(self):
    """Search buildings within buffer of selected point."""
    if not self.selected_point:
        QMessageBox.warning(self, "No Point", "Please select a point on map first")
        return

    distance = self.buffer_distance_input.value()

    # Call PostGIS service
    buildings = self.postgis_service.find_buildings_within_buffer(
        lat=self.selected_point['lat'],
        lng=self.selected_point['lng'],
        distance_meters=distance
    )

    self._display_search_results(buildings)
    self._highlight_buildings_on_map(buildings)
```

### 17.2 ملف: `services/postgis_service.py`

```python
def find_buildings_within_buffer(
    self,
    lat: float,
    lng: float,
    distance_meters: int
) -> List[Building]:
    """Find buildings within buffer distance of point."""
    query = """
        SELECT b.*
        FROM buildings b
        WHERE ST_DWithin(
            b.building_geometry::geography,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
            %s
        )
    """

    cursor = self.db.execute_query(query, (lng, lat, distance_meters))
    return [self._map_to_building(row) for row in cursor.fetchall()]

def find_buildings_within_polygon(self, polygon_wkt: str) -> List[Building]:
    """Find buildings whose centroids are within polygon."""
    query = """
        SELECT b.*
        FROM buildings b
        WHERE ST_Within(
            ST_Centroid(b.building_geometry),
            ST_GeomFromText(%s, 4326)
        )
    """

    cursor = self.db.execute_query(query, (polygon_wkt,))
    return [self._map_to_building(row) for row in cursor.fetchall()]
```

### 17.3 ملف: `ui/pages/buildings_page.py`

**إضافة Spatial Search Tab:**
```python
def _setup_search_tabs(self):
    """Setup search tabs."""
    tabs = QTabWidget()

    # Existing attribute search
    tabs.addTab(self._create_attribute_search_tab(), "Attribute Search")

    # NEW: Spatial search
    tabs.addTab(self._create_spatial_search_tab(), "Spatial Search")

    return tabs

def _create_spatial_search_tab(self):
    """Create spatial search tab."""
    widget = QWidget()
    layout = QVBoxLayout(widget)

    # Map-based search button
    map_search_btn = QPushButton("Search on Map")
    map_search_btn.clicked.connect(self._open_map_spatial_search)
    layout.addWidget(map_search_btn)

    return widget
```

### ✅ نقطة توقف 17: Testing Spatial Queries
```bash
python main.py
# Test:
# ✅ Buffer search (select point, search within 100m)
# ✅ Polygon search (draw polygon, find buildings inside)
# ✅ Results highlight on map
# ✅ PostgreSQL spatial queries execute correctly
```

**✋ انتظار الموافقة قبل المتابعة**

---

## 🎯 Sprint 4: Final Polish & Testing (الأسبوع الرابع)

---

## 📋 STEP 18: التحقق من PostgreSQL Integration
**المدة:** 2 ساعات
**الملفات:** 3 ملفات (config)

### 18.1 ملف: `app/config.py`

```python
# Verify PostgreSQL is properly configured
DATABASE_TYPE = os.getenv('DB_TYPE', 'postgresql')  # Default to PostgreSQL
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'trrcms')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
```

### 18.2 ملف: `.env.example`

```bash
# Database Configuration
DB_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trrcms
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here

# PostGIS
POSTGIS_VERSION=3.1
```

### 18.3 Test Connection:

```bash
python -c "
from repositories.postgres_database import PostgresDatabase
db = PostgresDatabase()
print('✅ PostgreSQL connection successful')
print(f'PostGIS version: {db.get_postgis_version()}')
"
```

### ✅ نقطة توقف 18: Database Testing
```bash
# Verify:
# ✅ PostgreSQL connects
# ✅ PostGIS extension loaded
# ✅ Spatial queries work
# ✅ All tables created
```

**✋ انتظار الموافقة**

---

## 📋 STEP 19-20: Code Quality & Validation

### STEP 19: Type Hints (2-3 ساعات)
```bash
# Run script from earlier
python scripts/add_type_hints_batch.py

# Verify with mypy
python -m mypy ui/ --ignore-missing-imports
```

### STEP 20: Black Formatting (1 ساعة)
```bash
# Format all Python files
python -m black ui/ controllers/ services/ models/ --line-length 100

# Verify
python -m black ui/ controllers/ services/ --check
```

---

## 📋 STEP 21: Comprehensive Testing
**المدة:** يوم كامل

### 21.1 Unit Tests
```bash
python -m pytest tests/ -v --cov=. --cov-report=html
# Target: 75%+ coverage
```

### 21.2 Integration Tests
```bash
python -m pytest tests/integration/ -v
```

### 21.3 Manual Testing Checklist:

**✅ Building Management:**
- [ ] Create building with polygon
- [ ] Edit building polygon
- [ ] Search buildings (attribute + spatial)
- [ ] View building on map
- [ ] Assign building to field team

**✅ Office Survey Wizard:**
- [ ] Complete all 7 steps
- [ ] Validate each step
- [ ] Save survey
- [ ] Review submitted survey

**✅ Map Features:**
- [ ] View building footprints
- [ ] Draw polygon
- [ ] Edit polygon vertices
- [ ] Buffer search
- [ ] Polygon selection
- [ ] Layer toggling

**✅ PostgreSQL/PostGIS:**
- [ ] Spatial queries execute
- [ ] Geometry validation works
- [ ] WKT/GeoJSON conversion
- [ ] Area calculation

**✅ Person Management:**
- [ ] Add person (via controller)
- [ ] Edit person
- [ ] Search person
- [ ] Duplicate detection

**✅ Claims:**
- [ ] View claims
- [ ] Workflow transitions
- [ ] Status updates

---

## 📋 STEP 22: Documentation Update
**المدة:** 2-3 ساعات

### Update:
1. `README.md` - Installation & setup
2. `docs/ARCHITECTURE.md` - Updated architecture
3. `docs/API.md` - Controller APIs
4. Inline code comments (where needed)

---

## 📊 Success Criteria - معايير النجاح

### ✅ النجاح الكامل يتطلب:

**1. Architecture (100%)**
- ✅ Zero business logic في UI Pages
- ✅ All UI calls go through Controllers
- ✅ Services handle business logic
- ✅ Repositories handle data access only

**2. Code Quality (95%+)**
- ✅ Type hints في 100% من UI files
- ✅ Black formatted (line-length 100)
- ✅ No files > 500 lines (except generated)
- ✅ DRY - no duplicate code
- ✅ SOLID principles followed

**3. Functionality (100%)**
- ✅ Office Survey Wizard works (all 7 steps)
- ✅ Building management complete
- ✅ Map with polygons works
- ✅ Spatial queries work
- ✅ PostgreSQL/PostGIS integrated
- ✅ All UC scenarios pass

**4. Testing (75%+)**
- ✅ Test coverage ≥ 75%
- ✅ All critical paths tested
- ✅ Integration tests pass
- ✅ Manual test checklist complete

**5. No Breaking Changes**
- ✅ Application runs without errors
- ✅ All existing features work
- ✅ Database migrations successful
- ✅ No performance degradation

---

## 🚫 ممنوعات - Prohibited Actions

1. ❌ **ممنوع Git commits** - هذه مهمة المطور
2. ❌ **ممنوع إنشاء ملف** إلا بعد التحقق من عدم وجوده
3. ❌ **ممنوع تغيير شكل UI** - فقط فصل logic
4. ❌ **ممنوع المتابعة** بدون اختبار الخطوة السابقة
5. ❌ **ممنوع الاستعجال** - quality over speed
6. ❌ **ممنوع duplicate code** - always DRY
7. ❌ **ممنوع breaking changes** - backward compatibility

---

## 📅 الجدول الزمني المقدر

| Sprint | المرحلة | الوقت المقدر | الخطوات |
|--------|---------|--------------|---------|
| 1 | Architecture Refactoring | 5-7 أيام | STEP 1-4 |
| 2 | Wizard Modularization | 5-7 أيام | STEP 5-13 |
| 3 | Map & GIS Integration | 4-5 أيام | STEP 14-17 |
| 4 | Quality & Testing | 3-4 أيام | STEP 18-22 |
| **Total** | | **17-23 يوم** | **22 Steps** |

---

## 🎯 Current Status: Ready to Begin

**Next Action:** انتظار موافقتك للبدء بـ STEP 1

**عند الموافقة، قل:**
- "ابدأ STEP 1" → سأبدأ بتحضير Services
- "راجع الخطة" → إذا أردت مراجعة/تعديل
- "تخطي إلى STEP X" → إذا أردت البدء من خطوة محددة

---

**ملاحظة هامة:**
هذه خطة مرنة. يمكن تعديلها بناءً على ما نكتشفه أثناء التنفيذ.
الهدف: **Quality, Maintainability, Best Practices** ✅
