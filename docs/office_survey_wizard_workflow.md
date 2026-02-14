# Office Survey Wizard - Workflow Documentation

## Overview

The Office Survey Wizard (UC-004) is a 6-step sequential wizard for conducting property surveys from the office. It creates a survey record, links a building and unit, registers household demographics, adds persons with their relations to the property, processes tenure claims, and finalizes the survey.

The wizard operates in **API mode** (Backend via HTTP) or **local mode** (SQLite database), determined by `Config.DATA_PROVIDER`.

---

## Architecture

```
OfficeSurveyWizard (office_survey_wizard_refactored.py)
  inherits BaseWizard (framework/base_wizard.py)
    uses StepNavigator (framework/step_navigator.py)
    uses SurveyContext (survey_context.py)

Steps (all inherit BaseStep from framework/base_step.py):
  Step 1: BuildingSelectionStep
  Step 2: UnitSelectionStep
  Step 3: HouseholdStep
  Step 4: OccupancyClaimsStep (Persons + Relations)
  Step 5: ClaimStep (Display claims from API)
  Step 6: ReviewStep (Review + Finalize)

Dialogs:
  PersonDialog (dialogs/person_dialog.py) - Opened from Step 4
```

---

## Step Lifecycle

Each step follows this lifecycle managed by `BaseStep`:

```
initialize()      Called once on first show. Calls setup_ui().
on_show()          Called every time step becomes active. Calls populate_data().
validate()         Called before moving to next step. Returns StepValidationResult.
on_next()          Called after validation passes, before leaving step.
on_hide()          Called when navigating away from step.
collect_data()     Returns dict of current step data from UI widgets.
```

**Navigation rules:**
- Forward: Calls `validate()` then `on_next()`. Blocked if validation fails.
- Backward: Calls `on_hide()` directly. No validation required.

---

## Data Flow

All steps share a single `SurveyContext` instance. Steps write to and read from this context.

```
Step 1 writes: building, building_uuid, survey_id, survey_data
Step 2 reads:  survey_id, building
Step 2 writes: unit, unit_id, unit_linked, is_new_unit
Step 3 reads:  survey_id, unit_id
Step 3 writes: household, household_id, demographic fields
Step 4 reads:  survey_id, household_id, unit_id
Step 4 writes: persons[], relations[], finalize_response
Step 5 reads:  finalize_response (claims data)
Step 6 reads:  all context data for review display
Step 6 writes: finalize_response (if not already set)
```

---

## API Endpoints (Survey Path)

All endpoints are relative to the base URL (e.g., `http://localhost:8080/api`).

### Step 1: Create Survey

```
POST /v1/Surveys/office
Body: {
  "buildingId": "<building_uuid>",
  "surveyDate": "2026-01-15T10:00:00Z",
  "inPersonVisit": true
}
Response: { "id": "<survey_uuid>", ... }
```

### Step 2: Link Unit to Survey

```
POST /v1/Surveys/{surveyId}/property-units/{unitId}/link
Body: (none)
Response: { updated survey data }
```

### Step 3: Create Household

```
POST /v1/Surveys/{surveyId}/households
Body: {
  "propertyUnitId": "<unit_uuid>",
  "headOfHouseholdName": null,
  "householdSize": 5,
  "occupancyType": "residential",
  "occupancyNature": "ownership",
  "adultMales": 1,
  "adultFemales": 1,
  "maleChildrenUnder18": 2,
  "femaleChildrenUnder18": 1,
  "maleElderlyOver65": 0,
  "femaleElderlyOver65": 0,
  "disabledMales": 0,
  "disabledFemales": 0,
  "notes": ""
}
Response: { "id": "<household_uuid>", ... }
```

### Step 4: Person Management (via PersonDialog)

**Create Person:**
```
POST /v1/Surveys/{surveyId}/households/{householdId}/persons
Body: {
  "firstNameArabic": "...",
  "fatherNameArabic": "...",
  "grandfatherNameArabic": "...",
  "familyNameArabic": "...",
  "firstNameEnglish": "...",
  "fatherNameEnglish": "...",
  "grandfatherNameEnglish": "...",
  "familyNameEnglish": "...",
  "dateOfBirth": "1990-01-01",
  "gender": "male",
  "nationality": "IQ",
  "identificationType": "national_id",
  "identificationNumber": "...",
  "phoneNumber": "...",
  "isHeadOfHousehold": true/false,
  "relationType": "owner",
  "contractType": "formal",
  "occupancyStartDate": "2020-01-01"
}
Response: { "id": "<person_uuid>", ... }
```

**Link Person to Unit:**
```
POST /v1/Surveys/{surveyId}/property-units/{unitId}/relations
Body: {
  "personId": "<person_uuid>",
  "relationType": "owner",
  "contractType": "formal",
  "occupancyStartDate": "2020-01-01",
  "evidenceType": "title_deed",
  "hasEvidence": true
}
Response: { "id": "<relation_uuid>", ... }
```

**Fetch Persons (on revisit):**
```
GET /v1/Surveys/{surveyId}/households/{householdId}/persons
Response: [ { person1 }, { person2 }, ... ]
```

### Step 4: Process Claims (automatic after persons added)

```
POST /v1/Surveys/office/{surveyId}/process-claims
Body: {
  "surveyId": "<survey_uuid>",
  "finalNotes": "",
  "durationMinutes": 10,
  "autoCreateClaim": true
}
Response: {
  "claimCreated": true,
  "claimsCreatedCount": 1,
  "createdClaims": [
    {
      "claimNumber": "CLM-2026-00001",
      "fullNameArabic": "...",
      "propertyUnitIdNumber": "...",
      "relationType": "owner",
      "surveyDate": "2026-01-15",
      "hasEvidence": true
    }
  ],
  "claimNotCreatedReason": null
}
```

### Step 6: Finalize Survey Status

```
POST /v1/Surveys/office/{surveyId}/finalize
Body: (none)
Response: { updated survey data with status "finalized" }
```

---

## Idempotency Guards

Each API-calling step has a guard to prevent duplicate records on back-navigation:

| Step | Guard | Context Key | Behavior |
|------|-------|-------------|----------|
| 1 | Survey creation | `survey_id` | Skips `create_office_survey()` if survey_id exists |
| 2 | Unit linking | `unit_linked` | Skips `link_unit_to_survey()` if flag is True |
| 3 | Household creation | `household_id` | Skips `create_household()` if household_id exists |
| 4 | Person fetch | `context.persons` | Skips API fetch if persons already loaded locally |
| 4 | Claim processing | `finalize_response` | Skips `finalize_office_survey()` if response exists |
| 6 | Final status | `finalize_response` | Skips if already processed in Step 4 |

---

## Error Handling

API errors are mapped through `services/error_mapper.py`:

| HTTP Status | User Message | Translation Key |
|-------------|-------------|-----------------|
| 400 | Validation details from response | `error.api.validation` |
| 401 | Session expired, please login | `error.api.unauthorized` |
| 403 | No permission for this action | `error.api.forbidden` |
| 404 | Requested item not found | `error.api.not_found` |
| 409 | Item already exists | `error.api.conflict` |
| 500+ | Server error, try later | `error.api.server` |
| Network | Check internet connection | `error.api.connection` |
| Timeout | Request timed out | `error.api.timeout` |

---

## Frontend Validation

| Step | Validation Rule |
|------|----------------|
| 1 | Building must be selected |
| 2 | Unit must be selected or created |
| 3 | Total household members must be > 0 |
| 3 | Sum of demographic categories must equal total members |
| 4 | At least one person must be added |
| 5 | Claims data must exist (from API response) |
| 6 | All previous steps must be complete |

---

## Authentication

Auth token flows from `MainWindow._api_token` to each step's API service:

```
MainWindow._api_token
  -> BaseStep._set_auth_token()
    -> Iterates over: _api_service, _api_client, _survey_api_service
    -> Calls service.set_access_token(token)
```

This is centralized in `BaseStep` (DRY). Each step calls `self._set_auth_token()` before making API calls.

---

## Draft Persistence

**Save Draft:**
1. Context serialized to dict via `context.to_dict()`
2. Stored in local SQLite via `survey_repo.create(draft_data)`
3. Includes current step index for resume position

**Load Draft:**
1. Draft loaded from SQLite by ID
2. Context restored via `SurveyContext.from_dict(draft_data)`
3. Wizard navigates to saved step index (skips validation)

**Close Behavior:**
- If finalized: Close immediately (no prompt)
- If has data (step >= 1): Prompt save/discard/cancel
- If no data: Close immediately

---

## Console Logging (Debug)

All API requests and responses are printed to console via centralized logging in `api_client.py:_request()`:

```
[API REQ] POST /v1/Surveys/office
[API REQ] Body: { "buildingId": "...", ... }
[API RES] 200 /v1/Surveys/office
[API RES] Body: { "id": "...", ... }

[API ERR] 400 POST /v1/Surveys/{id}/households
[API ERR] Response: { "errors": { ... } }
```

Response bodies longer than 1000 characters are truncated with `...` suffix.

---

## Complete Flow Sequence

```
User opens wizard
  |
  v
Step 1: Select Building
  -> User searches buildings (local DB or API)
  -> User selects a building
  -> on_next(): POST /v1/Surveys/office (create survey)
  -> Context: survey_id stored
  |
  v
Step 2: Select Unit
  -> Units loaded for selected building
  -> User selects existing unit or creates new one
  -> validate(): POST /v1/Surveys/{id}/property-units/{id}/link
  -> Context: unit_linked = True
  |
  v
Step 3: Register Household
  -> User enters demographic data (members count, ages, gender breakdown)
  -> Frontend validation: total_members > 0, sum matches total
  -> validate(): POST /v1/Surveys/{id}/households
  -> Context: household_id stored
  |
  v
Step 4: Add Persons + Process Claims
  -> PersonDialog opens for each person:
     -> Tab 1: Personal info (names, birth, ID)
     -> Tab 2: Contact info
     -> Tab 3: Relation to property (relation type, contract, evidence)
     -> Save: POST .../persons (create) + POST .../relations (link)
  -> After all persons added, user clicks Next:
     -> POST /v1/Surveys/office/{id}/process-claims
     -> Context: finalize_response with created claims
  |
  v
Step 5: View Claims
  -> Display claims from finalize_response (read-only)
  -> Shows claim number, person name, relation type, evidence status
  |
  v
Step 6: Review + Submit
  -> Display full survey summary
  -> User clicks Submit:
     -> POST /v1/Surveys/office/{id}/finalize (status change)
     -> Success popup with claim number
     -> Wizard closes
```
