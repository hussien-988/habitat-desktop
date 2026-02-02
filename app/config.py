# -*- coding: utf-8 -*-
"""
Application configuration and constants.

Server Configuration Quick Guide:
----------------------------------
1. Map Tiles: Set TILE_SERVER_URL (line 44)
2. REST API: Set API_BASE_URL (line 35) + DATA_PROVIDER="http" (line 26)
3. Database: Set DB_TYPE (line 55) for SQLite or PostgreSQL

Example for Production:
    TILE_SERVER_URL = "https://tiles.yourserver.com/{z}/{x}/{y}.png"
    API_BASE_URL = "https://api.yourserver.com"
    DATA_PROVIDER = "http"
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class Config:
    """Application configuration."""

    # Application Info
    APP_NAME: str = "UN-Habitat Syria"
    APP_TITLE: str = "Tenure Rights Registration & Claims Management System"
    APP_TITLE_AR: str = "نظام تسجيل حقوق الحيازة وإدارة المطالبات"
    VERSION: str = "1.0.0"
    ORGANIZATION: str = "UN-Habitat"

    # Development Mode
    # WARNING: Set to False in production! Only use True during development/testing
    DEV_MODE: bool = True
    DEV_AUTO_LOGIN: bool = True  # Auto-fill login credentials in dev mode
    DEV_USERNAME: str = "admin"
    DEV_PASSWORD: str = "admin123"

    # Data Provider Configuration
    # Options: "mock", "http", "local_db"
    # - mock: Uses in-memory mock data for development (no backend required)
    # - http: Connects to a REST API backend (uses /api/Buildings endpoint)
    # - local_db: Uses local SQLite/PostgreSQL database
    DATA_PROVIDER: str = "http"  # Changed to use API backend

    # Mock Data Provider Settings
    MOCK_SIMULATE_DELAY: bool = True
    MOCK_DELAY_MS: int = 200
    MOCK_PERSIST_TO_FILE: bool = False

    # HTTP API Backend Settings
    #
    API_BASE_URL: str = "http://localhost:8081/api"
    #API_BASE_URL: str = "https://localhost:7204/api"
    API_VERSION: str = "v1"
    API_TIMEOUT: int = 30
    API_MAX_RETRIES: int = 3

    # Map Tile Server Configuration
    # None = use local tile server (development)
    # For production: set to external tile server URL
    # Example: "https://tiles.yourserver.com/{z}/{x}/{y}.png"
    TILE_SERVER_URL: Optional[str] = None

    # Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    LOGS_DIR: Path = PROJECT_ROOT / "logs"
    ASSETS_DIR: Path = PROJECT_ROOT / "assets"
    ICONS_DIR: Path = ASSETS_DIR / "icons"
    FONTS_DIR: Path = ASSETS_DIR / "fonts"
    IMAGES_DIR: Path = ASSETS_DIR / "images"

    # Database Configuration
    # SQLite (development/fallback)
    DB_NAME: str = "trrcms.db"
    DB_PATH: Path = DATA_DIR / DB_NAME

    # PostgreSQL (production) - FSD 5.2
    # Set TRRCMS_DB_TYPE=postgresql to use PostgreSQL
    DB_TYPE: str = "sqlite"  # "sqlite" or "postgresql"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "trrcms"
    POSTGRES_USER: str = "trrcms_user"
    POSTGRES_PASSWORD: str = "trrcms_password"
    POSTGRES_MIN_CONN: int = 1
    POSTGRES_MAX_CONN: int = 10

    # Logging
    LOG_FILE: str = "app.log"
    LOG_PATH: Path = LOGS_DIR / LOG_FILE
    LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5MB
    LOG_BACKUP_COUNT: int = 3

    # UI Settings
    WINDOW_MIN_WIDTH: int = 1200
    WINDOW_MIN_HEIGHT: int = 800
    SIDEBAR_WIDTH: int = 280
    SIDEBAR_COLLAPSED_WIDTH: int = 60
    TOPBAR_HEIGHT: int = 50

    # UN-Habitat Branding Colors
    PRIMARY_COLOR: str = "#0072BC"  # UN Blue
    PRIMARY_DARK: str = "#005A9C"
    PRIMARY_LIGHT: str = "#4DA6E8"
    SECONDARY_COLOR: str = "#FFFFFF"
    ACCENT_COLOR: str = "#FDB714"  # UN Gold/Yellow
    TEXT_COLOR: str = "#2C3E50"
    TEXT_LIGHT: str = "#5D6D7E"
    BACKGROUND_COLOR: str = "#F0F7FF"  # Soft blue-gray background
    CARD_BACKGROUND: str = "#FFFFFF"
    BORDER_COLOR: str = "#D5DCE6"
    SUCCESS_COLOR: str = "#27AE60"
    WARNING_COLOR: str = "#F39C12"
    ERROR_COLOR: str = "#E74C3C"
    INFO_COLOR: str = "#3498DB"

    # Additional Professional Colors
    SIDEBAR_BG: str = "#1A365D"  # Deep navy blue
    SIDEBAR_HOVER: str = "#2C5282"
    SIDEBAR_ACTIVE: str = "#2B6CB0"
    HEADER_BG: str = "#FFFFFF"
    TABLE_HEADER_BG: str = "#F8FAFC"
    TABLE_ROW_ALT: str = "#FAFBFC"
    INPUT_BG: str = "#FFFFFF"
    INPUT_BORDER: str = "#CBD5E0"
    INPUT_FOCUS: str = "#0072BC"

    # Fonts - Updated to match ui/design_system.py
    # Primary Arabic Font: IBM Plex Sans Arabic (main font for the application)
    # Fallback: Calibri (system fallback only)
    FONT_FAMILY: str = "IBM Plex Sans Arabic"  # Primary font for Arabic
    ARABIC_FONT_FAMILY: str = "IBM Plex Sans Arabic"  # Updated from Noto Kufi Arabic
    LATIN_FONT_FAMILY: str = "Roboto"  # For English text if needed
    FONT_SIZE: int = 9  # Body/UI: 12-13px
    FONT_SIZE_SMALL: int = 8  # Labels: 11-12px
    FONT_SIZE_LARGE: int = 10  # Slightly larger
    FONT_SIZE_TITLE: int = 13  # H1: 18-20px
    FONT_SIZE_HEADING: int = 11  # H2: 14-16px
    FONT_SIZE_H1: int = 14  # 18-20px
    FONT_SIZE_H2: int = 11  # 14-16px
    FONT_SIZE_BODY: int = 9  # 12-13px
    FONT_SIZE_LABEL: int = 8  # 11-12px

    # GIS Mode
    GIS_MODE: str = "fallback"  # "qgis" | "fallback"
    QGIS_PREFIX_PATH: str = "C:/Program Files/QGIS 3.34"  # Update for your QGIS install

    # Logo
    LOGO_PATH: Path = ASSETS_DIR / "images" / "un-logo.jpg"
    LOGO_PLACEHOLDER: bool = False  # False = use actual logo file

    # Import Wizard
    UHC_EXTENSION: str = ".uhc"
    MAX_IMPORT_RECORDS: int = 10000
    VALIDATION_DELAY_MS: int = 50  # Simulated delay per record

    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    PAGE_SIZE_OPTIONS: tuple = (25, 50, 100, 200)

    # Date/Time Formats
    DATE_FORMAT: str = "%Y-%m-%d"
    DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    DATE_FORMAT_DISPLAY: str = "%d/%m/%Y"

    # Administrative Codes (Aleppo)
    DEFAULT_GOVERNORATE_CODE: str = "01"
    DEFAULT_GOVERNORATE_NAME: str = "Aleppo"
    DEFAULT_GOVERNORATE_NAME_AR: str = "حلب"


# Page identifiers
class Pages:
    LOGIN = "login"
    DASHBOARD = "dashboard"
    BUILDINGS = "buildings"
    BUILDING_DETAILS = "building_details"
    UNITS = "units"
    UNIT_DETAILS = "unit_details"
    PERSONS = "persons"
    PERSON_DETAILS = "person_details"
    CLAIMS = "claims"
    DRAFT_CLAIMS = "draft_claims"  # Draft claims page
    CLAIM_DETAILS = "claim_details"
    DOCUMENTS = "documents"
    HOUSEHOLDS = "households"
    RELATIONS = "relations"
    IMPORT_WIZARD = "import_wizard"
    CONFLICTS = "conflicts"
    DUPLICATES = "duplicates"  # UC-007, UC-008: Property & Person duplicates
    FIELD_ASSIGNMENT = "field_assignment"  # UC-012: Assign buildings to field teams
    DRAFT_OFFICE_SURVEYS = "draft_office_surveys"  # UC-005: Draft office surveys list
    SEARCH = "search"
    REPORTS = "reports"
    MAP_VIEW = "map_view"
    ADMIN = "admin"
    AUDIT = "audit"


# User roles
class Roles:
    ADMIN = "admin"
    DATA_MANAGER = "data_manager"
    OFFICE_CLERK = "office_clerk"
    FIELD_SUPERVISOR = "field_supervisor"
    ANALYST = "analyst"

    @classmethod
    def get_display_name(cls, role: str, arabic: bool = False) -> str:
        names = {
            cls.ADMIN: ("Administrator", "مدير النظام"),
            cls.DATA_MANAGER: ("Data Manager", "مدير البيانات"),
            cls.OFFICE_CLERK: ("Office Clerk", "موظف المكتب"),
            cls.FIELD_SUPERVISOR: ("Field Supervisor", "مشرف ميداني"),
            cls.ANALYST: ("Analyst", "محلل"),
        }
        name = names.get(role, (role, role))
        return name[1] if arabic else name[0]


# Controlled vocabularies
class Vocabularies:
    # Building types matching API values (integer codes)
    # Value (code), Name (English), Name (Arabic)
    # API: 1 = Residential, 2 = Commercial, 3 = MixedUse, 4 = Industrial
    BUILDING_TYPES = [
        (1, "Residential", "سكني"),
        (2, "Commercial", "تجاري"),
        (3, "MixedUse", "مختلط (سكني وتجاري)"),
        (4, "Industrial", "صناعي"),
    ]

    # Building status matching API values (integer codes)
    # Value (code), Name (English), Name (Arabic)
    # API: 1=Intact, 2=MinorDamage, 3=ModerateDamage, 4=MajorDamage, 5=SeverelyDamaged,
    #      6=Destroyed, 7=UnderConstruction, 8=Abandoned, 99=Unknown
    BUILDING_STATUS = [
        (1, "Intact", "سليم"),
        (2, "MinorDamage", "أضرار طفيفة"),
        (3, "ModerateDamage", "أضرار متوسطة"),
        (4, "MajorDamage", "أضرار كبيرة"),
        (5, "SeverelyDamaged", "أضرار شديدة"),
        (6, "Destroyed", "مدمر"),
        (7, "UnderConstruction", "قيد الإنشاء"),
        (8, "Abandoned", "مهجور"),
        (99, "Unknown", "غير معروف"),
    ]

    UNIT_TYPES = [
        ("apartment", "Apartment", "شقة"),
        ("shop", "Shop", "محل"),
        ("office", "Office", "مكتب"),
        ("warehouse", "Warehouse", "مستودع"),
        ("garage", "Garage", "كراج"),
        ("other", "Other", "آخر"),
    ]

    RELATION_TYPES = [
        ("owner", "Owner", "مالك"),
        ("tenant", "Tenant", "مستأجر"),
        ("heir", "Heir", "وريث"),
        ("guest", "Guest", "ضيف"),
        ("occupant", "Occupant", "شاغل"),
        ("other", "Other", "آخر"),
    ]

    DOCUMENT_TYPES = [
        ("TAPU_GREEN", "Property Deed (Green Tapu)", "صك ملكية (طابو أخضر)"),
        ("PROPERTY_REG", "Property Registration", "بيان قيد عقاري"),
        ("COURT_RULING", "Court Ruling", "حكم قضائي"),
        ("SALE_NOTARIZED", "Notarized Sale Contract", "عقد بيع موثق"),
        ("SALE_INFORMAL", "Informal Sale Contract", "عقد بيع غير موثق"),
        ("RENT_REGISTERED", "Registered Rental", "عقد إيجار مثبت"),
        ("RENT_INFORMAL", "Informal Rental", "عقد إيجار غير مثبت"),
        ("UTILITY_BILL", "Utility Bill", "فاتورة مرافق"),
        ("MUKHTAR_CERT", "Mukhtar Certificate", "شهادة المختار"),
        ("INHERITANCE", "Inheritance Certificate", "حصر إرث"),
        ("WITNESS_STATEMENT", "Witness Statement", "إفادة شاهد"),
    ]

    CASE_STATUS = [
        ("draft", "Draft", "مسودة"),
        ("submitted", "Submitted", "مقدم"),
        ("screening", "Initial Screening", "التدقيق الأولي"),
        ("under_review", "Under Review", "قيد المراجعة"),
        ("awaiting_docs", "Awaiting Documents", "في انتظار الوثائق"),
        ("conflict", "Conflict Detected", "تعارض مكتشف"),
        ("approved", "Approved", "موافق عليه"),
        ("rejected", "Rejected", "مرفوض"),
    ]

    VERIFICATION_STATUS = [
        ("pending", "Pending", "معلق"),
        ("verified", "Verified", "تم التحقق"),
        ("rejected", "Rejected", "مرفوض"),
    ]

    GENDERS = [
        ("male", "Male", "ذكر"),
        ("female", "Female", "أنثى"),
    ]


# Aleppo administrative divisions (sample data)
class AleppoDivisions:
    DISTRICTS = [
        ("01", "Aleppo City", "مدينة حلب"),
        ("02", "Jebel Saman", "جبل سمعان"),
        ("03", "Al-Bab", "الباب"),
        ("04", "Manbij", "منبج"),
        ("05", "Ain al-Arab", "عين العرب"),
        ("06", "Jarabulus", "جرابلس"),
        ("07", "Azaz", "أعزاز"),
        ("08", "Afrin", "عفرين"),
        ("09", "As-Safira", "السفيرة"),
    ]

    NEIGHBORHOODS_ALEPPO = [
        ("001", "Al-Jamiliyah", "الجميلية"),
        ("002", "Al-Aziziyah", "العزيزية"),
        ("003", "Al-Shahba", "الشهباء"),
        ("004", "Al-Hamdaniyah", "الحمدانية"),
        ("005", "Al-Midan", "الميدان"),
        ("006", "Salah al-Din", "صلاح الدين"),
        ("007", "Al-Firdaws", "الفردوس"),
        ("008", "Al-Sabil", "السبيل"),
        ("009", "Hanano", "هنانو"),
        ("010", "Al-Sha'ar", "الشعار"),
    ]
