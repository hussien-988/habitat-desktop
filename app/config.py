# -*- coding: utf-8 -*-


from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional
import os

# ============================================================================
# Load .env file for local environment configuration
# ============================================================================
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load from .env file in project root
except ImportError:
    pass  # dotenv not installed - will use defaults

# ============================================================================
# Read settings from environment variables (from .env or system)
# ============================================================================
# API Settings
_API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080/api")
_API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
_API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
_API_USERNAME = os.getenv("API_USERNAME", "admin")
_API_PASSWORD = os.getenv("API_PASSWORD", "Admin@123")

# Tile Server Settings
_TILE_SERVER_URL = os.getenv("TILE_SERVER_URL", None)
_USE_DOCKER_TILES = os.getenv("USE_DOCKER_TILES", "false").lower() in ("true", "1", "yes")
_MBTILES_PATH = os.getenv("MBTILES_PATH", None)

# Map Geographic Settings (defaults: Aleppo, Syria)
_MAP_CENTER_LAT = float(os.getenv("MAP_CENTER_LAT", "36.2021"))
_MAP_CENTER_LNG = float(os.getenv("MAP_CENTER_LNG", "37.1343"))
_MAP_DEFAULT_ZOOM = int(os.getenv("MAP_DEFAULT_ZOOM", "14"))
_MAP_MIN_ZOOM = int(os.getenv("MAP_MIN_ZOOM", "10"))
_MAP_MAX_ZOOM = int(os.getenv("MAP_MAX_ZOOM", "18"))
_MAP_BOUNDS_MIN_LAT = float(os.getenv("MAP_BOUNDS_MIN_LAT", "35.5"))
_MAP_BOUNDS_MAX_LAT = float(os.getenv("MAP_BOUNDS_MAX_LAT", "37.0"))
_MAP_BOUNDS_MIN_LNG = float(os.getenv("MAP_BOUNDS_MIN_LNG", "36.5"))
_MAP_BOUNDS_MAX_LNG = float(os.getenv("MAP_BOUNDS_MAX_LNG", "38.0"))

# Data Mode: always "api" (Docker backend)
_DATA_MODE = os.getenv("DATA_MODE", "api")

# GeoServer Settings (optional)
_GEOSERVER_URL = os.getenv("GEOSERVER_URL", None)
_GEOSERVER_WORKSPACE = os.getenv("GEOSERVER_WORKSPACE", "trrcms")
_GEOSERVER_ENABLED = os.getenv("GEOSERVER_ENABLED", "false").lower() in ("true", "1", "yes")


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
    DEV_AUTO_LOGIN: bool = True
    DEV_USERNAME: str = "admin"
    DEV_PASSWORD: str = "Admin@123"

    # Data Mode: always API (Docker backend)
    DATA_MODE: str = "api"
    DATA_PROVIDER: str = "http"

    # HTTP API Backend Settings
    # ✅ DYNAMIC: Reads from .env file (API_BASE_URL, API_TIMEOUT, API_MAX_RETRIES, etc.)
    # If .env not found, uses default (http://localhost:8080/api)
    API_BASE_URL: str = _API_BASE_URL  # From .env or default
    API_VERSION: str = "v1"
    API_TIMEOUT: int = _API_TIMEOUT  # From .env or default (30)
    API_MAX_RETRIES: int = _API_MAX_RETRIES  # From .env or default (3)
    API_USERNAME: str = _API_USERNAME  # From .env or default (admin)
    API_PASSWORD: str = _API_PASSWORD  # From .env or default (Admin@123)

    # Map Tile Server Configuration
    TILE_SERVER_URL: Optional[str] = _TILE_SERVER_URL
    USE_DOCKER_TILES: bool = _USE_DOCKER_TILES
    USE_EMBEDDED_TILES_FALLBACK: bool = True
    TILE_SERVER_HEALTH_TIMEOUT: int = 2
    MBTILES_PATH: Optional[str] = _MBTILES_PATH

    # Map Geographic Configuration
    MAP_CENTER_LAT: float = _MAP_CENTER_LAT
    MAP_CENTER_LNG: float = _MAP_CENTER_LNG
    MAP_DEFAULT_ZOOM: int = _MAP_DEFAULT_ZOOM
    MAP_MIN_ZOOM: int = _MAP_MIN_ZOOM
    MAP_MAX_ZOOM: int = _MAP_MAX_ZOOM
    MAP_BOUNDS_MIN_LAT: float = _MAP_BOUNDS_MIN_LAT
    MAP_BOUNDS_MAX_LAT: float = _MAP_BOUNDS_MAX_LAT
    MAP_BOUNDS_MIN_LNG: float = _MAP_BOUNDS_MIN_LNG
    MAP_BOUNDS_MAX_LNG: float = _MAP_BOUNDS_MAX_LNG

    # GeoServer Configuration (optional)
    GEOSERVER_URL: Optional[str] = _GEOSERVER_URL
    GEOSERVER_WORKSPACE: str = _GEOSERVER_WORKSPACE
    GEOSERVER_ENABLED: bool = _GEOSERVER_ENABLED

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
    LOGO_PATH: Path = ASSETS_DIR / "images" / "Layer_1.png"
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
    CASE_DETAILS = "case_details"
    DOCUMENTS = "documents"
    HOUSEHOLDS = "households"
    RELATIONS = "relations"
    CONFLICTS = "conflicts"
    DUPLICATES = "duplicates"  # UC-007, UC-008: Property & Person duplicates
    CLAIM_COMPARISON = "claim_comparison"  # UC-007: Claim comparison for merge
    FIELD_ASSIGNMENT = "field_assignment"  # UC-012: Assign buildings to field teams
    USER_MANAGEMENT = "user_management"
    ADD_USER = "add_user"
    SEARCH = "search"
    REPORTS = "reports"
    MAP_VIEW = "map_view"
    ADMIN = "admin"
    AUDIT = "audit"
    SYNC_DATA = "sync_data"
    DATA_MANAGEMENT = "data_management"


# User roles
class Roles:
    ADMIN = "admin"
    DATA_MANAGER = "data_manager"
    OFFICE_CLERK = "office_clerk"
    FIELD_SUPERVISOR = "field_supervisor"
    FIELD_RESEARCHER = "field_researcher"
    DATA_COLLECTOR = "data_collector"
    ANALYST = "analyst"

    # Roles that cannot log in to the desktop application
    NON_LOGIN_ROLES = ("data_collector",)

    @classmethod
    def get_display_name(cls, role: str, arabic: bool = False) -> str:
        names = {
            cls.ADMIN: ("Administrator", "مدير النظام"),
            cls.DATA_MANAGER: ("Data Manager", "مدير البيانات"),
            cls.OFFICE_CLERK: ("Office Clerk", "موظف المكتب"),
            cls.FIELD_SUPERVISOR: ("Field Supervisor", "مشرف ميداني"),
            cls.FIELD_RESEARCHER: ("Field Researcher", "باحث ميداني"),
            cls.DATA_COLLECTOR: ("Data Collector", "جامع بيانات"),
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

    # Property Unit Type matching API values (integer codes)
    # API: 1=Apartment, 2=Shop, 3=Office, 4=Warehouse, 5=Other
    UNIT_TYPES = [
        (1, "Apartment", "شقة سكنية"),
        (2, "Shop", "محل تجاري"),
        (3, "Office", "مكتب"),
        (4, "Warehouse", "مستودع"),
        (5, "Other", "أخرى"),
    ]

    # Property Unit Status matching API values (integer codes)
    # API: 1=Occupied, 2=Vacant, 3=Damaged, 4=UnderRenovation, 5=Uninhabitable, 6=Locked, 99=Unknown
    UNIT_STATUS = [
        (1, "Occupied", "مشغول"),
        (2, "Vacant", "شاغر"),
        (3, "Damaged", "متضرر"),
        (4, "UnderRenovation", "قيد الترميم"),
        (5, "Uninhabitable", "غير صالح للسكن"),
        (6, "Locked", "مغلق"),
        (99, "Unknown", "غير معروف"),
    ]

    RELATION_TYPES = [
        (1, "Owner", "مالك"),
        (2, "Occupant", "شاغل"),
        (3, "Tenant", "مستأجر"),
        (4, "Guest", "ضيف"),
        (5, "Heir", "وريث"),
        (99, "Other", "آخر"),
    ]

    DOCUMENT_TYPES = [
        (1, "Tabu Green", "طابو أخضر"),
        (2, "Tabu Red", "طابو أحمر"),
        (3, "Agricultural Deed", "سجل زراعي"),
        (4, "Real Estate Registry Extract", "كشف عقاري"),
        (5, "Ownership Certificate", "شهادة ملكية"),
        (10, "Rental Contract", "عقد إيجار"),
        (11, "Tenancy Agreement", "اتفاقية إيجار"),
        (20, "National Id Card", "بطاقة هوية وطنية"),
        (21, "Passport", "جواز سفر"),
        (22, "Family Registry", "قيد عائلي"),
        (30, "Electricity Bill", "فاتورة كهرباء"),
        (31, "Water Bill", "فاتورة مياه"),
        (40, "Court Order", "حكم محكمة"),
        (43, "Inheritance Document", "وثيقة ميراث"),
        (63, "Witness Statement", "شهادة شهود"),
        (70, "Sale Contract", "عقد بيع"),
        (999, "Other", "أخرى"),
    ]

    CASE_STATUS = [
        (1, "Draft", "مسودة"),
        (2, "Finalized", "نهائي"),
        (3, "Under Review", "قيد المراجعة"),
        (4, "Approved", "موافق عليه"),
        (5, "Rejected", "مرفوض"),
        (6, "Pending Evidence", "بانتظار مستندات إضافية"),
        (7, "Disputed", "متنازع عليه"),
        (99, "Archived", "مؤرشف"),
    ]

    VERIFICATION_STATUS = [
        (1, "Pending", "قيد الانتظار"),
        (2, "Under Review", "قيد المراجعة"),
        (3, "Verified", "موثق"),
        (4, "Rejected", "مرفوض"),
        (5, "Requires Additional Info", "يتطلب معلومات إضافية"),
        (6, "Expired", "منتهي الصلاحية"),
    ]

    GENDERS = [
        (1, "Male", "ذكر"),
        (2, "Female", "أنثى"),
    ]


# Aleppo administrative divisions (sample data)
# NOTE: Districts/subdistricts/communities now come from DivisionsService (data/administrative_divisions.json)
class AleppoDivisions:
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
        ("011", "Al-Masri", "المصري"),
        ("012", "Bab al-Nairab", "باب النيرب"),
        ("013", "Al-Kalaseh", "الكلاسة"),
        ("014", "Al-Farafra", "الفرافرة"),
        ("015", "Al-Sukkari", "السكري"),
        ("016", "Sheikh Maqsoud", "الشيخ مقصود"),
        ("017", "Ashrafiyeh", "الأشرفية"),
        ("018", "Al-Ansari", "الأنصاري"),
        ("019", "Al-Shaar", "الشعار"),
        ("020", "Bustan al-Qasr", "بستان القصر"),
    ]


