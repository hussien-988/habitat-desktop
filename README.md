# TRRCMS - Tenure Rights Registration & Claims Management System

نظام تسجيل حقوق الحيازة وإدارة المطالبات

A Windows desktop application built with PyQt5 for UN-Habitat's tenure rights registration and claims management in Syria.

## Features

- **Dashboard**: System statistics, KPIs, and recent activities
- **Buildings Management**: CRUD operations, filtering, and export
- **Property Units Management**: Manage units within buildings
- **Persons Management**: Register and manage persons/beneficiaries
- **Person-Unit Relations**: Link persons to units with relation types
- **Evidence & Documents**: Attach and manage supporting documents
- **Claims/Cases**: Create and manage tenure claims with workflow lifecycle
- **Import Wizard**: 4-step .uhc file import with validation
- **Conflict Resolution**: Detect and resolve duplicate claims
- **Global Search**: Search across all entities
- **Reports**: Generate and export reports (CSV, Excel, GeoJSON)
- **Map View**: Interactive GIS visualization
- **Administration**: User/role/vocabulary management
- **Arabic Support**: Full RTL layout and Arabic translations
- **Audit Logging**: Track all changes

## Prerequisites

- Windows 10/11
- Python 3.10 or higher
- pip (Python package manager)

## Installation

1. **Clone or download the repository**

2. **Navigate to the project folder**:
   ```cmd
   cd path\to\trrcms
   ```

3. **Create a virtual environment** (recommended):
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```

## Running the Application

```cmd
python main.py
```

The application will:
1. Initialize the SQLite database (first run)
2. Seed demo data (100 buildings, 400+ units, 150 persons, 50 claims)
3. Open the login screen

## Default Login Credentials

| Username | Password    | Role             |
|----------|-------------|------------------|
| admin    | admin123    | Administrator    |
| manager  | manager123  | Data Manager     |
| clerk    | clerk123    | Office Clerk     |
| analyst  | analyst123  | Analyst          |

## Project Structure

```
trrcms/
├── main.py                    # Application entry point
├── config.yaml                # Configuration file
├── requirements.txt           # Python dependencies
│
├── app/                       # Main application
│   ├── config.py              # Configuration
│   ├── main_window_v2.py      # Main window
│   └── navbar.py              # Navigation bar
│
├── models/                    # Data models
│   ├── building.py
│   ├── unit.py
│   ├── person.py
│   ├── claim.py
│   └── user.py
│
├── repositories/              # Data access layer
│   ├── database.py
│   ├── building_repository.py
│   ├── unit_repository.py
│   ├── person_repository.py
│   └── claim_repository.py
│
├── services/                  # Business logic
│   ├── auth_service.py
│   ├── validation_service.py
│   ├── workflow_service.py
│   ├── import_service.py
│   └── export_service.py
│
├── ui/
│   ├── components/            # Reusable widgets
│   │   ├── navbar.py
│   │   ├── toast.py
│   │   ├── claim_list_card.py
│   │   └── empty_state.py
│   │
│   └── pages/                 # Main screens
│       ├── login_page.py
│       ├── dashboard_page.py
│       ├── buildings_page.py
│       ├── units_page.py
│       ├── persons_page.py
│       ├── completed_claims_page.py
│       ├── draft_claims_page.py
│       ├── import_wizard_page.py
│       └── duplicates_page.py
│
├── utils/                     # Utilities
│   ├── logger.py
│   ├── i18n.py
│   └── helpers.py
│
├── data/                      # Data files
│   ├── trrcms.db              # SQLite database
│   └── attachments/           # File attachments
│
└── logs/                      # Log files
    └── app.log
```

## Configuration

Edit `config.yaml` to customize:

```yaml
# Database
db_path: ./data/trrcms.db

# GIS Mode
gis_mode: fallback  # "qgis" or "fallback"

# Language
default_language: ar  # "ar" or "en"

# Logging
log_level: INFO
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+L   | Toggle language (Arabic/English) |
| Ctrl+Q   | Logout |

## Building for Distribution

Using PyInstaller:

```cmd
pip install pyinstaller

pyinstaller --name TRRCMS ^
  --onefile ^
  --windowed ^
  --icon=assets/icons/app.ico ^
  --add-data "assets;assets" ^
  --add-data "data;data" ^
  main.py
```

The executable will be created at: `dist/TRRCMS.exe`

## License

Developed for UN-Habitat Syria Office.

## Version

v1.0.0 - Desktop Application (Windows / PyQt5)
