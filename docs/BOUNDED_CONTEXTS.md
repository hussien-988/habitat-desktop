# Bounded Contexts Documentation

This document defines the bounded contexts in the Habitat Desktop application following Domain-Driven Design (DDD) principles.

## Overview

The application is organized into 8 bounded contexts, each representing a distinct domain area with clear boundaries and responsibilities.

---

## 1. Claim Management Context

**Purpose**: Managing tenure rights claims and their lifecycle

**Core Entities**:
- `Claim` - Main claim/case entity
- `ClaimHistory` - Audit trail of claim changes
- `ClaimConflict` - Detected conflicts between claims

**Services**:
- `WorkflowService` - Claim state transitions
- `ConflictResolution` - Resolving claim conflicts

**UI Components**:
- `ui/pages/claims_page.py`
- `ui/components/claim_list_card.py`

**Responsibilities**:
- Create and manage claims
- Track claim lifecycle (Draft → Submitted → Under Review → etc.)
- Detect and resolve conflicts
- Generate claim reports

---

## 2. Building & Property Management Context

**Purpose**: Managing buildings and property units

**Core Entities**:
- `Building` - Building entity with hierarchical ID
- `PropertyUnit` - Individual units within buildings

**Repositories**:
- `BuildingRepository`
- `UnitRepository`

**Services**:
- `BuildingAssignmentService` - Assign buildings to field teams

**UI Components**:
- `ui/pages/building_details_page.py`
- `ui/pages/units_page.py`
- `ui/components/building_map_widget.py`

**Responsibilities**:
- Register and manage buildings
- Manage property units
- Hierarchical building ID generation (17-digit format)
- Building assignments for field work

---

## 3. Person & Household Management Context

**Purpose**: Managing persons and household information

**Core Entities**:
- `Person` - Individual person entity
- `Household` - Household/occupancy information
- `PersonUnitRelation` - Relations between persons and property units

**Repositories**:
- `PersonRepository`
- `HouseholdRepository`
- `RelationRepository`

**Services**:
- `MatchingService` - Duplicate detection for persons

**UI Components**:
- `ui/pages/persons_page.py`
- `ui/pages/households_page.py`

**Responsibilities**:
- Register persons and their details
- Manage household composition
- Track person-property relationships
- Detect duplicate persons

---

## 4. Document & Evidence Management Context

**Purpose**: Managing documents and evidence supporting claims

**Core Entities**:
- `Document` - Document metadata
- `Evidence` - Evidence linking documents to claims
- `Attachment` - File attachments with SHA-256 deduplication

**Services**:
- `DocumentVersionService` - Version control for documents

**UI Components**:
- `ui/components/document_viewer.py`
- `ui/components/dialogs/document_upload_dialog.py`

**Responsibilities**:
- Store and manage documents
- Link evidence to claims
- Document versioning
- File deduplication (SHA-256)
- Document verification workflow

---

## 5. GIS/Spatial Operations Context

**Purpose**: Geographic information and spatial operations

**Core Services**:
- `PostGISService` - Spatial queries (buffer, intersection, proximity)
- `MapService` - Map rendering and interaction
- `GISServerService` - Tile server management

**UI Components**:
- `ui/pages/map_page.py`
- `ui/components/map_picker_dialog.py`
- `ui/components/map_viewer_dialog.py`

**Responsibilities**:
- Spatial queries on buildings/units
- Map visualization with PostGIS data
- Building location selection
- Proximity-based duplicate detection
- GeoJSON export

---

## 6. Import/Export Management Context

**Purpose**: Data import/export and synchronization

**Core Services**:
- `ImportService` - Import UHC containers
- `UHCContainerService` - Handle UHC file format
- `ExportManager` - Export to CSV/Excel/PDF/GeoJSON
- `SyncServerService` - Local network synchronization

**UI Components**:
- `ui/pages/import_wizard_page.py`
- `ui/wizards/import/` - Import wizard framework

**Repositories**:
- `ImportHistoryRepository`
- `StagingRepository` - Temporary staging for validation

**Responsibilities**:
- Import field data from tablets (UHC format)
- Validate imported data
- Stage data before commit
- Export data in multiple formats
- Synchronize with mobile devices

---

## 7. User & Security Management Context

**Purpose**: User authentication, authorization, and security

**Core Entities**:
- `User` - User accounts
- `SecuritySettings` - System security configuration

**Services**:
- `AuthService` - Authentication with bcrypt
- `RBACService` - Role-based access control
- `SecurityService` - Password hashing, account lockout
- `SessionManagerService` - Session management

**Responsibilities**:
- User authentication (bcrypt)
- Role-based permissions
- Account lockout after failed attempts
- Password policy enforcement
- Session management
- Audit logging

---

## 8. Reporting & Analytics Context

**Purpose**: Report generation and data analytics

**Core Services**:
- `ReportService` - Report generation
- `PDFReportService` - PDF report with Arabic support
- `DashboardService` - Dashboard data aggregation

**UI Components**:
- `ui/pages/reports_page.py`
- `ui/pages/dashboard_page.py`

**Responsibilities**:
- Generate PDF reports with QR codes
- Arabic text rendering in reports
- Dashboard analytics
- Export statistics
- Custom report templates

---

## Context Boundaries

Each context maintains clear boundaries:

1. **Anti-Corruption Layer**: Data adapters between contexts
2. **Shared Kernel**: Common models (e.g., `VocabularyTerm`)
3. **Published Language**: API contracts between contexts

## Context Integration

Contexts communicate through:
- **Services**: Primary integration point
- **Events**: (To be implemented) Domain events for async communication
- **Repositories**: Data access abstraction

---

## Notes

- Each context has clear ownership of its domain entities
- Business logic stays within the appropriate context
- UI components are grouped by their primary context
- Cross-context operations go through services, not direct repository access
