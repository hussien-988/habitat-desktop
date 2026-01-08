# TRRCMS Implementation Assumptions

This document records key assumptions made during implementation where requirements needed clarification.

## Database & Storage

### Document Storage
Documents are stored in `trrcms/data/attachments/` folder with SHA-256 hash as filename to enable deduplication.

### Document Versioning
Historical versions are kept in a `document_versions` table rather than overwriting. Each edit creates a new version entry.

### Claim History
Claim history is stored at the claim level (snapshot of entire claim state) rather than field-level change tracking.

---

## Duplicate Detection & Resolution

### Property Duplicates
Property duplicates are detected strictly by key matching:
- Buildings: identical `building_id`
- Units: identical `building_id + unit_code`

No fuzzy matching or similarity scores are used.

### Person Duplicates
Person duplicates are detected strictly by identical `national_id` values. No name similarity matching is implemented.

### Merge Strategy
When merging records, the "master" record selected by the user is preserved, and all references are updated to point to the master. Duplicate records are then deleted.

### Keep-Separate Prevention
Records marked as "keep separate" are tracked in the `duplicate_resolutions` table to prevent re-detection.

---

## Authentication & Security

### Authentication
Local SQLite-based authentication (no external OAuth/SSO).

### Security Settings
Security settings use a single "default" row in `security_settings` table. All users share the same security policy.

### Password Policy
Password validation is implemented in `SecurityService.validate_password()` but enforcement is left to the authentication service.

### Session Timeout
Session timeout value is stored in settings but actual session expiry logic is handled by the authentication service.

### Audit Log Scope
The audit log captures security-related events (settings changes, login events) but not all CRUD operations. Entity-specific changes are tracked in history tables (claim_history, document_versions).

---

## Vocabulary Management

### Vocabulary Persistence
Vocabulary terms are stored in a database table (`vocabulary_terms`) rather than in-memory constants. This allows runtime editing without restarting the application.

### Deprecation vs Deletion
Terms cannot be deleted if they are in use. Instead, they are marked as "deprecated" which hides them from new selections but preserves existing data references.

### Vocabulary Versioning
Version numbers are incremented automatically on each update. Full version history with effective dates is stored.

### Import File Format
Import accepts CSV or JSON files with columns: `code`, `label`, `label_ar`.

---

## User & Role Management

### System Roles
Roles are predefined system roles that cannot be created or deleted via UI. The five roles (Administrator, Data Manager, Office Clerk, Field Supervisor, Analyst) are system-defined. Only role assignment to users is supported.

### Permissions
Per-role permissions are predefined and hardcoded in the application based on role. A full permissions matrix editor is not implemented.

### Account Status
Users can have three statuses: Active (نشط), Locked (مقفل - temporary due to failed logins), or Disabled (معطل - permanent admin action).

---

## Field Team Management

### Field Teams
Field teams are defined in a static list within the application. A full team management CRUD is not implemented.

### Tablet Detection
Tablet device detection is simulated. In production, this would use LAN scanning or device registration.

### Data Transfer
Data transfer to tablets is simulated with status updates (not_transferred → transferring → transferred). Actual LAN/sync implementation would be handled by a separate sync service.

### Assignment Lifecycle
Building assignments have a simple lifecycle: pending → assigned → completed/cancelled.

### Single Active Assignment
Each building can only have one active assignment at a time. Previous assignments must be completed or cancelled before a new assignment can be created.

---

## Building Management

### Building ID Generation
Building ID is auto-generated from administrative hierarchy codes + building number in format: GG-DD-SS-CCC-NNN-BBBBB (17 characters with dashes).

### Default Administrative Codes
Default governorate is "Aleppo" (01). Subdistrict and community default to "01" and "001" respectively.

### Coordinate Entry
GPS coordinates are entered via numeric spinboxes with Aleppo region bounds validation.

### Building Validation
Building validation includes checking required administrative codes, building ID format, coordinate bounds, and duplicate building_id check.

---

## GIS & Map Integration

### UHC Files
Simulated as SQLite containers with JSON manifest.

### Map Integration
Leaflet fallback is used by default. QGIS mode requires separate installation.

### Coordinates
Demo data uses random points within Aleppo city bounds (36.15°-36.25°N, 37.10°-37.20°E).

---

## Internationalization

### Arabic Font
Falls back to system fonts if Noto Sans Arabic is unavailable.

### Default Language
Arabic (RTL) is the default language.

---

*Last updated: 2026-01-08*
