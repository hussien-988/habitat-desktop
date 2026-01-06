# TRRCMS Implementation Assumptions

This document records assumptions made during implementation where requirements were unclear.

## PATCH 1: UC-006 - Update Existing Claim

### A1: Document Versioning
**Assumption**: "Document versioning" (no replacement) means we keep historical versions in a `document_versions` table rather than overwriting. Each edit creates a new version entry.

### A2: Claim History Granularity
**Assumption**: Claim history is stored at the claim level (snapshot of entire claim state) rather than field-level change tracking. This simplifies implementation while still meeting audit requirements.

### A3: Modification Reason
**Assumption**: The "reason for modification" field (UC-006 S08) is stored in the claim_history table alongside each historical snapshot.

### A4: Document Storage
**Assumption**: Documents are stored in `trrcms/data/attachments/` folder with SHA-256 hash as filename to enable deduplication per FR-D-9.

### A5: Edit Permissions
**Assumption**: Both Data Manager and Municipality Clerk roles can edit claims as per UC-006 actor definition.

---

## PATCH 2: UC-007 - Resolve Duplicate Properties

### A6: Property Duplicate Detection
**Assumption**: Property duplicates are detected strictly by key matching (identical `building_id` for buildings, identical `building_id + unit_code` for units) as specified in UC-007. No fuzzy matching or similarity scores are used for property detection.

### A7: Merge Strategy
**Assumption**: When merging property records, the "master" record selected by the user is preserved, and all references (units, claims, relations) are updated to point to the master. The duplicate records are then deleted.

### A8: Keep-Separate Prevention
**Assumption**: Records marked as "keep separate" are tracked in the `duplicate_resolutions` table to prevent them from re-appearing in the duplicate queue. However, this is advisory only - if the underlying data changes, they may be re-detected.

### A9: Escalation Queue
**Assumption**: Escalated cases are stored with status="escalated" in the resolutions table. A senior review queue is not fully implemented but can be queried from this table.

---

## PATCH 2+3: UC-008 - Resolve Person Duplicates

### A10: Person Duplicate Detection
**Assumption**: Person duplicates are detected strictly by identical `national_id` values as specified in UC-008. No name similarity matching is implemented (as spec explicitly states "no similarity scores").

### A11: Person Merge References
**Assumption**: When merging persons, all references in `person_unit_relations`, `claims.person_ids`, and household records are updated to the master person ID.

---

## PATCH 4: UC-010 - Vocabulary Management

### A12: Vocabulary Persistence
**Assumption**: Vocabulary terms are stored in a database table (`vocabulary_terms`) rather than in-memory constants. This allows runtime editing without restarting the application.

### A13: Deprecation vs Deletion
**Assumption**: Terms cannot be deleted if they are in use (per UC-010 spec). Instead, they are marked as "deprecated" which hides them from new selections but preserves existing data references.

### A14: Vocabulary Versioning
**Assumption**: Version numbers are incremented automatically on each update. Full version history with effective dates is stored but simplified version management is implemented (no overlapping date range validation).

### A15: Import File Format
**Assumption**: Import accepts CSV or JSON files with columns/fields: `code` (or `term_code`), `label` (or `term_label`), `label_ar` (or `term_label_ar`).

---

## PATCH 5: UC-011 - Security Settings + Audit Log

### A16: Security Settings Singleton
**Assumption**: Security settings use a single "default" row in `security_settings` table rather than multiple profiles. All users share the same security policy.

### A17: Password Policy Enforcement
**Assumption**: Password validation is implemented in `SecurityService.validate_password()` but enforcement is left to the authentication service. The security settings only define the policy, not enforce it directly.

### A18: Audit Log Scope
**Assumption**: The audit log captures security-related events (settings changes, login events) but not all CRUD operations on claims/buildings/etc. Those are tracked in entity-specific history tables (claim_history, document_versions).

### A19: Session Timeout Implementation
**Assumption**: Session timeout value is stored in settings but actual session expiry logic is deferred to authentication service. The UI displays the setting but does not implement automatic logout.

### A20: Audit Log Retention
**Assumption**: No automatic purging of audit logs is implemented. All entries are retained indefinitely per compliance requirements.

---

## PATCH 6: UC-012 - Assign Buildings to Field Teams

### A21: Field Team Management
**Assumption**: Field teams are defined in a static list within the application. A full team management CRUD is not implemented. Teams can be added by modifying the `get_field_teams()` method.

### A22: Tablet Detection
**Assumption**: Tablet device detection is simulated. In production, this would use LAN scanning or device registration. The current implementation shows a static list of tablets with connection status.

### A23: Transfer Protocol
**Assumption**: Data transfer to tablets is simulated with status updates (not_transferred → transferring → transferred). Actual LAN/sync implementation would use the sync service layer defined in the spec but is out of scope for this desktop-only implementation.

### A24: Assignment Lifecycle
**Assumption**: Building assignments have a simple lifecycle: pending → assigned → completed/cancelled. Transfer status is tracked separately (not_transferred → transferring → transferred/failed).

### A25: Single Active Assignment
**Assumption**: Each building can only have one active assignment at a time. Previous assignments must be completed or cancelled before a new assignment can be created.

---

## PATCH UC-000: Manage Building Data (Add/Edit)

### A26: Building ID Generation
**Assumption**: Building ID is auto-generated from administrative hierarchy codes + building number in format: GG-DD-SS-CCC-NNN-BBBBB (17 characters with dashes). The system displays this generated ID but allows manual building number entry.

### A27: Default Administrative Codes
**Assumption**: Default governorate is "Aleppo" (01) per spec comment. Subdistrict and community default to "01" and "001" respectively as the spec focuses on Aleppo city.

### A28: Coordinate Entry
**Assumption**: GPS coordinates are entered via numeric spinboxes with Aleppo region bounds validation. Map-based entry (clicking on map) is not implemented as spec mentions it would be entered via GIS system integration.

### A29: Building Validation
**Assumption**: Building validation includes checking required administrative codes, building ID format, and coordinate bounds. Duplicate building_id check is performed on save.

---

## PATCH UC-009: User & Role Management

### A30: System Roles (Predefined)
**Assumption**: Roles are predefined system roles per UC-009 spec comment "is_system_role flag (cannot be deleted if true)". The five roles (Admin, Data Manager, Office Clerk, Field Supervisor, Analyst) are hardcoded and cannot be created/deleted via UI. Only role assignment to users is supported.

### A31: Permissions Not Editable
**Assumption**: Per-role permissions are predefined. The spec mentions "permissions (per-module or per-action flags)" but implementing a full permissions matrix is out of scope. Instead, permission checks are hardcoded in the application based on role.

### A32: Account Status Display
**Assumption**: Users can have three statuses displayed: Active (نشط), Locked (مقفل), or Disabled (معطل). Locked is temporary (due to failed logins), Disabled is permanent (admin action).

### A33: Role Information Display
**Assumption**: Since roles cannot be created/edited (A30), the Roles section in admin UI displays role descriptions only as informational reference.

---
*Last updated: 2026-01-02*
