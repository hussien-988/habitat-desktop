# -*- coding: utf-8 -*-
"""
Internationalization (i18n) support for Arabic/English.
"""

from typing import Dict, Optional


class I18n:
    """Internationalization manager for Arabic/English translations."""

    def __init__(self, default_language: str = "ar"):
        self._language = default_language
        self._translations = self._load_translations()

    def _load_translations(self) -> Dict[str, Dict[str, str]]:
        """Load translation dictionaries."""
        return {
            # Application
            "app_title": {
                "en": "Tenure Rights Registration & Claims Management System",
                "ar": "نظام تسجيل حقوق الحيازة وإدارة المطالبات"
            },
            "app_name": {
                "en": "UN-Habitat",
                "ar": "موئل الأمم المتحدة"
            },

            # Login
            "login": {"en": "Login", "ar": "تسجيل الدخول"},
            "username": {"en": "Username", "ar": "اسم المستخدم"},
            "password": {"en": "Password", "ar": "كلمة المرور"},
            "login_button": {"en": "Sign In", "ar": "دخول"},
            "login_error": {"en": "Invalid username or password", "ar": "اسم المستخدم أو كلمة المرور غير صحيحة"},
            "welcome": {"en": "Welcome", "ar": "مرحباً"},

            # Navigation
            "dashboard": {"en": "Dashboard", "ar": "لوحة التحكم"},
            "buildings": {"en": "Buildings", "ar": "المباني"},
            "building_details": {"en": "Building Details", "ar": "تفاصيل المبنى"},
            "import": {"en": "Import", "ar": "استيراد"},
            "import_wizard": {"en": "Import Wizard", "ar": "معالج الاستيراد"},
            "map": {"en": "Map", "ar": "الخريطة"},
            "map_view": {"en": "Map View", "ar": "عرض الخريطة"},
            "settings": {"en": "Settings", "ar": "الإعدادات"},
            "logout": {"en": "Logout", "ar": "تسجيل الخروج"},

            # Dashboard
            "overview": {"en": "Overview", "ar": "نظرة عامة"},
            "total_buildings": {"en": "Total Buildings", "ar": "إجمالي المباني"},
            "total_units": {"en": "Total Units", "ar": "إجمالي الوحدات"},
            "total_claims": {"en": "Total Claims", "ar": "إجمالي المطالبات"},
            "total_persons": {"en": "Total Persons", "ar": "إجمالي الأشخاص"},
            "pending_review": {"en": "Pending Review", "ar": "قيد المراجعة"},
            "with_conflicts": {"en": "With Conflicts", "ar": "مع تعارضات"},
            "recent_activity": {"en": "Recent Activity", "ar": "النشاط الأخير"},
            "buildings_by_status": {"en": "Buildings by Status", "ar": "المباني حسب الحالة"},
            "buildings_by_type": {"en": "Buildings by Type", "ar": "المباني حسب النوع"},
            "claims_by_status": {"en": "Claims by Status", "ar": "المطالبات حسب الحالة"},

            # Buildings List
            "building_list": {"en": "Buildings List", "ar": "قائمة المباني"},
            "search": {"en": "Search", "ar": "بحث"},
            "filter": {"en": "Filter", "ar": "تصفية"},
            "export": {"en": "Export", "ar": "تصدير"},
            "export_csv": {"en": "Export CSV", "ar": "تصدير CSV"},
            "export_excel": {"en": "Export Excel", "ar": "تصدير Excel"},
            "neighborhood": {"en": "Neighborhood", "ar": "الحي"},
            "building_type": {"en": "Building Type", "ar": "نوع المبنى"},
            "building_status": {"en": "Building Status", "ar": "حالة المبنى"},
            "all": {"en": "All", "ar": "الكل"},
            "view_details": {"en": "View Details", "ar": "عرض التفاصيل"},

            # Building Details Tabs
            "overview_tab": {"en": "Overview", "ar": "نظرة عامة"},
            "units_tab": {"en": "Units", "ar": "الوحدات"},
            "persons_tab": {"en": "Persons", "ar": "الأشخاص"},
            "evidence_tab": {"en": "Evidence", "ar": "الأدلة"},
            "history_tab": {"en": "History", "ar": "السجل"},
            "back_to_list": {"en": "Back to List", "ar": "العودة للقائمة"},

            # Building Fields
            "building_id": {"en": "Building ID", "ar": "رقم المبنى"},
            "governorate": {"en": "Governorate", "ar": "المحافظة"},
            "district": {"en": "District", "ar": "المنطقة"},
            "subdistrict": {"en": "Sub-district", "ar": "الناحية"},
            "community": {"en": "Community", "ar": "التجمع"},
            "floors": {"en": "Floors", "ar": "الطوابق"},
            "apartments": {"en": "Apartments", "ar": "الشقق"},
            "shops": {"en": "Shops", "ar": "المحلات"},
            "coordinates": {"en": "Coordinates", "ar": "الإحداثيات"},

            # Unit Fields
            "unit_id": {"en": "Unit ID", "ar": "رقم الوحدة"},
            "unit_type": {"en": "Unit Type", "ar": "نوع الوحدة"},
            "floor": {"en": "Floor", "ar": "الطابق"},
            "area": {"en": "Area", "ar": "المساحة"},
            "status": {"en": "Status", "ar": "الحالة"},

            # Person Fields
            "person_name": {"en": "Name", "ar": "الاسم"},
            "first_name": {"en": "First Name", "ar": "الاسم الأول"},
            "father_name": {"en": "Father's Name", "ar": "اسم الأب"},
            "last_name": {"en": "Last Name", "ar": "الكنية"},
            "national_id": {"en": "National ID", "ar": "الرقم الوطني"},
            "gender": {"en": "Gender", "ar": "الجنس"},
            "phone": {"en": "Phone", "ar": "الهاتف"},
            "relation_type": {"en": "Relation Type", "ar": "نوع العلاقة"},

            # Relations
            "relations": {"en": "Relations", "ar": "العلاقات"},
            "add_relation": {"en": "Add Relation", "ar": "إضافة علاقة"},
            "edit_relation": {"en": "Edit Relation", "ar": "تعديل علاقة"},
            "ownership_share": {"en": "Ownership Share", "ar": "حصة الملكية"},

            # Import Wizard
            "step": {"en": "Step", "ar": "الخطوة"},
            "select_file": {"en": "Select File", "ar": "اختيار الملف"},
            "validate": {"en": "Validate", "ar": "التحقق"},
            "resolve": {"en": "Resolve", "ar": "الحل"},
            "commit": {"en": "Commit", "ar": "الحفظ"},
            "browse": {"en": "Browse", "ar": "استعراض"},
            "next": {"en": "Next", "ar": "التالي"},
            "previous": {"en": "Previous", "ar": "السابق"},
            "cancel": {"en": "Cancel", "ar": "إلغاء"},
            "finish": {"en": "Finish", "ar": "إنهاء"},
            "validating": {"en": "Validating...", "ar": "جارٍ التحقق..."},
            "committing": {"en": "Committing...", "ar": "جارٍ الحفظ..."},
            "valid_records": {"en": "Valid Records", "ar": "السجلات الصحيحة"},
            "warnings": {"en": "Warnings", "ar": "تحذيرات"},
            "errors": {"en": "Errors", "ar": "أخطاء"},
            "duplicates": {"en": "Duplicates", "ar": "مكررات"},
            "import_success": {"en": "Successfully imported {count} records", "ar": "تم استيراد {count} سجل بنجاح"},
            "import_failed": {"en": "Import failed", "ar": "فشل الاستيراد"},

            # Actions
            "save": {"en": "Save", "ar": "حفظ"},
            "edit": {"en": "Edit", "ar": "تعديل"},
            "delete": {"en": "Delete", "ar": "حذف"},
            "add": {"en": "Add", "ar": "إضافة"},
            "close": {"en": "Close", "ar": "إغلاق"},
            "confirm": {"en": "Confirm", "ar": "تأكيد"},
            "refresh": {"en": "Refresh", "ar": "تحديث"},

            # Status values
            "intact": {"en": "Intact", "ar": "سليم"},
            "minor_damage": {"en": "Minor Damage", "ar": "ضرر طفيف"},
            "major_damage": {"en": "Major Damage", "ar": "ضرر كبير"},
            "destroyed": {"en": "Destroyed", "ar": "مدمر"},
            "residential": {"en": "Residential", "ar": "سكني"},
            "commercial": {"en": "Commercial", "ar": "تجاري"},
            "mixed_use": {"en": "Mixed Use", "ar": "متعدد الاستخدامات"},
            "owner": {"en": "Owner", "ar": "مالك"},
            "tenant": {"en": "Tenant", "ar": "مستأجر"},
            "heir": {"en": "Heir", "ar": "وريث"},
            "occupant": {"en": "Occupant", "ar": "شاغل"},

            # Dialogs
            "confirm_delete": {"en": "Confirm Delete", "ar": "تأكيد الحذف"},
            "delete_message": {"en": "Are you sure you want to delete this item?", "ar": "هل أنت متأكد من حذف هذا العنصر؟"},
            "logout_confirm_title": {"en": "Confirm Logout", "ar": "تأكيد الخروج"},
            "logout_confirm_message": {"en": "Are you sure you want to logout?", "ar": "هل أنت متأكد من تسجيل الخروج؟"},
            "exit_confirm_title": {"en": "Confirm Exit", "ar": "تأكيد الخروج"},
            "exit_confirm_message": {"en": "Are you sure you want to exit?", "ar": "هل أنت متأكد من الخروج من التطبيق؟"},
            "yes": {"en": "Yes", "ar": "نعم"},
            "no": {"en": "No", "ar": "لا"},

            # Messages
            "loading": {"en": "Loading...", "ar": "جارٍ التحميل..."},
            "no_data": {"en": "No data available", "ar": "لا توجد بيانات"},
            "error_occurred": {"en": "An error occurred", "ar": "حدث خطأ"},
            "success": {"en": "Success", "ar": "نجاح"},
            "failed": {"en": "Failed", "ar": "فشل"},

            # Map
            "map_placeholder": {"en": "Map view placeholder - GIS integration pending", "ar": "عنصر نائب للخريطة - في انتظار تكامل GIS"},
            "zoom_in": {"en": "Zoom In", "ar": "تكبير"},
            "zoom_out": {"en": "Zoom Out", "ar": "تصغير"},

            # Language
            "language": {"en": "Language", "ar": "اللغة"},
            "english": {"en": "English", "ar": "الإنجليزية"},
            "arabic": {"en": "Arabic", "ar": "العربية"},
            "toggle_language": {"en": "Toggle Language", "ar": "تبديل اللغة"},

            # Roles
            "admin": {"en": "Administrator", "ar": "مدير النظام"},
            "data_manager": {"en": "Data Manager", "ar": "مدير البيانات"},
            "office_clerk": {"en": "Office Clerk", "ar": "موظف المكتب"},
            "analyst": {"en": "Analyst", "ar": "محلل"},

            # Evidence
            "evidence": {"en": "Evidence", "ar": "الأدلة"},
            "evidence_list": {"en": "Evidence List", "ar": "قائمة الأدلة"},
            "add_evidence": {"en": "Add Evidence", "ar": "إضافة دليل"},
            "edit_evidence": {"en": "Edit Evidence", "ar": "تعديل الدليل"},
            "delete_evidence": {"en": "Delete Evidence", "ar": "حذف الدليل"},
            "evidence_type": {"en": "Evidence Type", "ar": "نوع الدليل"},
            "evidence_description": {"en": "Description", "ar": "الوصف"},
            "reference_number": {"en": "Reference Number", "ar": "رقم المرجع"},
            "reference_date": {"en": "Reference Date", "ar": "تاريخ المرجع"},
            "issuer": {"en": "Issuer", "ar": "الجهة المصدرة"},
            "verification_status": {"en": "Verification Status", "ar": "حالة التحقق"},
            "verification_notes": {"en": "Verification Notes", "ar": "ملاحظات التحقق"},
            "verified_by": {"en": "Verified By", "ar": "تم التحقق بواسطة"},
            "verification_date": {"en": "Verification Date", "ar": "تاريخ التحقق"},
            "pending": {"en": "Pending", "ar": "معلق"},
            "verified": {"en": "Verified", "ar": "تم التحقق"},
            "rejected": {"en": "Rejected", "ar": "مرفوض"},
            "document": {"en": "Document", "ar": "وثيقة"},
            "witness": {"en": "Witness Statement", "ar": "إفادة شاهد"},
            "community": {"en": "Community Affirmation", "ar": "تأكيد مجتمعي"},
            "other": {"en": "Other", "ar": "آخر"},
            "no_evidence": {"en": "No evidence attached", "ar": "لا توجد أدلة مرفقة"},
            "evidence_added": {"en": "Evidence added successfully", "ar": "تمت إضافة الدليل بنجاح"},
            "evidence_updated": {"en": "Evidence updated successfully", "ar": "تم تحديث الدليل بنجاح"},
            "evidence_deleted": {"en": "Evidence deleted successfully", "ar": "تم حذف الدليل بنجاح"},
            "select_relation_first": {"en": "Please select a relation first", "ar": "يرجى اختيار علاقة أولاً"},
            "file_attachment": {"en": "File Attachment", "ar": "مرفق"},
            "select_file": {"en": "Select File", "ar": "اختيار ملف"},
            "clear_file": {"en": "Clear", "ar": "مسح"},
            "view_file": {"en": "View File", "ar": "عرض الملف"},

            # Households
            "households": {"en": "Households", "ar": "الأسر"},
            "household": {"en": "Household", "ar": "الأسرة"},
            "add_household": {"en": "Add Household", "ar": "إضافة أسرة"},
            "edit_household": {"en": "Edit Household", "ar": "تعديل الأسرة"},
            "delete_household": {"en": "Delete Household", "ar": "حذف الأسرة"},
            "household_size": {"en": "Household Size", "ar": "حجم الأسرة"},
            "occupancy_size": {"en": "Occupancy Size", "ar": "عدد الشاغلين"},
            "male_count": {"en": "Male Count", "ar": "عدد الذكور"},
            "female_count": {"en": "Female Count", "ar": "عدد الإناث"},
            "minors_count": {"en": "Minors (Under 18)", "ar": "القاصرين (أقل من 18)"},
            "adults_count": {"en": "Adults (18-59)", "ar": "البالغين (18-59)"},
            "elderly_count": {"en": "Elderly (60+)", "ar": "كبار السن (60+)"},
            "with_disability_count": {"en": "With Disability", "ar": "ذوي الإعاقة"},
            "main_occupant": {"en": "Main Occupant", "ar": "الشاغل الرئيسي"},
            "occupancy_type": {"en": "Occupancy Type", "ar": "نوع الإشغال"},
            "occupancy_nature": {"en": "Occupancy Nature", "ar": "طبيعة الإشغال"},
            "occupancy_start_date": {"en": "Occupancy Start Date", "ar": "تاريخ بدء الإشغال"},
            "monthly_rent": {"en": "Monthly Rent", "ar": "الإيجار الشهري"},
            "household_added": {"en": "Household added successfully", "ar": "تمت إضافة الأسرة بنجاح"},
            "household_updated": {"en": "Household updated successfully", "ar": "تم تحديث الأسرة بنجاح"},
            "household_deleted": {"en": "Household deleted successfully", "ar": "تم حذف الأسرة بنجاح"},
            "select_unit_first": {"en": "Please select a unit first", "ar": "يرجى اختيار وحدة أولاً"},
            "permanent": {"en": "Permanent", "ar": "دائم"},
            "temporary": {"en": "Temporary", "ar": "مؤقت"},
            "seasonal": {"en": "Seasonal", "ar": "موسمي"},
            "caretaker": {"en": "Caretaker", "ar": "حارس"},
            "relative": {"en": "Relative", "ar": "قريب"},
            "gender_distribution": {"en": "Gender Distribution", "ar": "التوزيع حسب الجنس"},
            "age_distribution": {"en": "Age Distribution", "ar": "التوزيع حسب العمر"},
            "validation_error": {"en": "Validation Error", "ar": "خطأ في التحقق"},
        }

    def set_language(self, language: str):
        """Set current language (en or ar)."""
        if language in ["en", "ar"]:
            self._language = language

    def get_language(self) -> str:
        """Get current language."""
        return self._language

    def is_arabic(self) -> bool:
        """Check if current language is Arabic."""
        return self._language == "ar"

    def t(self, key: str, **kwargs) -> str:
        """
        Translate a key to the current language.

        Args:
            key: Translation key
            **kwargs: Format arguments

        Returns:
            Translated string
        """
        translation = self._translations.get(key, {})
        text = translation.get(self._language, key)

        # Apply format arguments if provided
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass

        return text

    def translate(self, key: str, language: Optional[str] = None, **kwargs) -> str:
        """
        Translate a key to a specific language.

        Args:
            key: Translation key
            language: Target language (defaults to current)
            **kwargs: Format arguments

        Returns:
            Translated string
        """
        lang = language or self._language
        translation = self._translations.get(key, {})
        text = translation.get(lang, key)

        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass

        return text

    def add_translation(self, key: str, en: str, ar: str):
        """Add a new translation."""
        self._translations[key] = {"en": en, "ar": ar}
