# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**TRRCMS** — Tenure Rights Registration & Claims Management System for UN-Habitat Syria. A Windows desktop application built with **PyQt5** that connects to a Docker-hosted REST API backend. It manages buildings, property units, persons, tenure claims, and GIS data in Arabic/English with full RTL support.

## Running the Application

```cmd
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

Configuration is loaded from `.env` (copy `.env.example` to `.env`). Key variables:

| Variable | Purpose | Default |
|---|---|---|
| `API_BASE_URL` | Backend REST API | `http://localhost:8080` |
| `API_USERNAME` / `API_PASSWORD` | API auth credentials | — |
| `TILE_SERVER_URL` | Map tile server | `http://localhost:5000` |
| `DEV_MODE` / `DEV_AUTO_LOGIN` | Skip login on startup | `false` |
| `DATA_MODE` | Always `api` (Docker backend) | `api` |

Local per-device overrides (tile server URL, language) are persisted in `data/settings.json` and take priority over `.env`.

## Building for Distribution

```cmd
pip install pyinstaller
pyinstaller TRRCMS.spec
# Output: dist/TRRCMS.exe
```

## Architecture

The app follows a layered architecture:

```
UI (PyQt5 pages/components)
    ↓ calls
Controllers (QObject subclasses, emit signals)
    ↓ calls
Services (business logic, API calls)
    ↓ calls
Repositories (data access, wraps DatabaseAdapter)
    ↓
API backend (HTTP) or SQLite (fallback)
```

### Key Layers

**`app/config.py`** — Central `Config` dataclass (all constants, colors, fonts, paths). Also defines `Pages`, `Roles`, `Vocabularies`, and `AleppoDivisions` constants used throughout the app. Local settings are read/written via `load_local_settings()` / `save_local_settings()`.

**`main.py`** — Entry point. Initializes `QApplication`, shows an animated splash screen, spins up a `Database` instance in a background `QThread`, then creates and shows `MainWindow`.

**`app/main_window_v2.py`** — `MainWindow` (frameless `QMainWindow`). Owns the `QStackedWidget` that holds all pages. Navigation is handled by the `Navbar` sidebar; pages are lazily loaded and cached. Language switching (Ctrl+L) triggers a full UI direction change via `TranslationManager`.

**`controllers/`** — `BaseController(QObject)` provides `OperationResult[T]` return type, common signals (`operation_started`, `operation_completed`, `operation_failed`), and logging. All controllers subclass it and communicate results upward via signals rather than return values.

**`services/api_client.py`** — `TRRCMSApiClient` handles JWT auth (auto-refresh), retries, and all HTTP calls to the backend. API URL resolution order: `data/settings.json` → `.env` → default localhost.

**`services/api_worker.py`** — `QThread`-based worker for non-blocking API calls, so the UI never blocks.

**`services/translation_manager.py`** — Singleton `TranslationManager`. Call `tr("key")` anywhere; call `set_language("ar"|"en")` to switch. Translations live in `services/translations/ar.py` and `en.py`.

**`repositories/db_adapter.py`** — `DatabaseAdapter` abstraction; `DatabaseFactory.create()` picks SQLite or PostgreSQL based on `TRRCMS_DB_TYPE`. The `Database` class in `repositories/database.py` is a backward-compat wrapper — new code should use `DatabaseFactory` directly.

**`ui/design_system.py`** — `ScreenScale` (scales pixel values relative to 1512×982 reference), `FormDimensions`, and palette/font helpers. Call `ScreenScale.initialize(screen_geometry)` once at startup.

**`ui/pages/`** — One file per screen. Pages receive a `Database` instance and controllers at construction; they do not call services directly.

**`ui/components/`** — Reusable PyQt5 widgets (buttons, dialogs, map widgets, toast notifications, tables).

### Map / GIS

Maps are rendered via **Leaflet** in a `QWebEngineView`. HTML templates are generated in `services/leaflet_html_generator.py` and related `leaflet_*_template.py` files. The tile server is a local Docker service; `services/tile_server_manager.py` handles detection and fallback to embedded tiles.

### Internationalization

- Default language is Arabic (`ar`) with RTL layout.
- `Ctrl+L` toggles between Arabic and English at runtime.
- All user-visible strings should use `tr("key")` (from `services/translation_manager`). Keys are defined in `services/translations/ar.py` and `services/translations/en.py`.

### RBAC

`services/rbac_service.py` enforces role-based access. Roles that cannot log into the desktop app: `data_collector`, `field_researcher`, `analyst` (see `Roles.NON_LOGIN_ROLES` in `app/config.py`).

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+L | Toggle language (Arabic ↔ English) |
| Ctrl+Q | Logout |
