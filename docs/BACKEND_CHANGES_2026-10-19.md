# Backend changes required by Desktop v2 (Issues Report 19-10-2026)

> للفريق: هذا الملف موجّه لـ Claude Code عندكم. افتحوه داخل ريبو `TRRCMS-Backend` واطلبوا منه تنفيذه كما هو. التعديلات في الديسكتوب جاهزة وتنتظر هذه التعديلات.

**Audience:** Claude Code working in the `TRRCMS-Backend` repository (ASP.NET Core, Clean Architecture: WebAPI / Application (MediatR, FluentValidation) / Infrastructure (EF Core) / Domain).

**Context:** The TRRCMS Desktop app (PyQt5) fixed two client-reported issues on its side. Both need a matching backend change. The desktop changes are already done and **backward compatible**: they work against the current backend (the new fields are simply absent or ignored) and light up once this is deployed. Deploy order does not matter.

Implement exactly the two changes below. Do not rename existing fields or change existing behaviour beyond what is described.

---

## Change 1 — Empty property unit: allow a household size of 0 (Issues Report item 9A)

### Problem
A property unit (مقسم) can be empty, so the number of occupants is 0. The desktop has no way to save that: the backend rejects `householdSize: 0` with `HouseholdSize_AtLeast1`.

The domain already models this case:
- `Household.IsEmptyProperty` and `Household.EmptyPropertyJustification` exist (`src/TRRCMS.Domain/Entities/HouseHold.cs`).
- `Household.Create(..., isEmptyProperty, emptyPropertyJustification)` accepts them.
- `HouseholdDto` already returns `isEmptyProperty` and `emptyPropertyJustification`.

Today only tablet (.uhc) imports set the flag.

### What the desktop now does
The household step has a checkbox **"المقسم فارغ (لا يوجد شاغلين)"**. When it is ticked, every count is forced to 0, and the desktop sends on **create** and **update** of a survey household:

```json
{
  "householdSize": 0,
  "maleCount": 0, "femaleCount": 0,
  "adultCount": 0, "childCount": 0, "elderlyCount": 0, "disabledCount": 0,
  "isEmptyProperty": true,
  "emptyPropertyJustification": null
}
```

- When the box is not ticked, the desktop sends `"isEmptyProperty": false` with the usual counts (`householdSize` >= 1).
- `emptyPropertyJustification` is only round-tripped. The desktop sends back whatever the household already had (for example the justification from a tablet import), or `null`. The office user is not asked for a justification.

Endpoints used by the desktop. These are the ones that must change:
- `POST /api/v1/Surveys/{surveyId}/households` → `CreateHouseholdInSurveyCommand`
- `PUT  /api/v1/Surveys/{surveyId}/households/{householdId}` → `UpdateHouseholdInSurveyCommand`

### Required backend changes
1. **Commands.** Add two properties to each command:
   - `src/TRRCMS.Application/Surveys/Commands/CreateHouseholdInSurvey/CreateHouseholdInSurveyCommand.cs`: `bool IsEmptyProperty` (default `false`) and `string? EmptyPropertyJustification`.
   - `src/TRRCMS.Application/Surveys/Commands/UpdateHouseholdInSurvey/UpdateHouseholdInSurveyCommand.cs`: `bool? IsEmptyProperty` (`null` = keep current) and `string? EmptyPropertyJustification`.

2. **Validators.** Edit `CreateHouseholdInSurveyCommandValidator.cs` and `UpdateHouseholdInSurveyCommandValidator.cs`.
   - When `IsEmptyProperty == true`:
     - `HouseholdSize` must be exactly `0`. On update, this applies when it is provided.
     - Every provided count (male, female, adult, child, elderly, disabled) must be `0`.
     - Add a localized message for a violation, e.g. `EmptyProperty_CountsMustBeZero`, in both `src/TRRCMS.Application/Resources/ValidationMessages.resx` and `ValidationMessages.ar.resx`.
     - Arabic text: `عند تحديد المقسم كفارغ يجب أن تكون جميع الأعداد صفراً`.
   - When `IsEmptyProperty` is `false` or `null`, keep the current rules unchanged (`HouseholdSize` > 0 and <= 50, the sum checks, and so on). The existing size rule must only apply when the unit is not empty.
   - `EmptyPropertyJustification`: optional, max length 2000. The justification stays mandatory for tablet imports, as `DataConsistencyValidator` already enforces; do not change that.

3. **Create handler.** In `CreateHouseholdInSurveyCommandHandler.cs`, pass `isEmptyProperty: request.IsEmptyProperty` and `emptyPropertyJustification: request.EmptyPropertyJustification` to `Household.Create(...)`.

4. **Update handler.** In `UpdateHouseholdInSurveyCommandHandler.cs`, when `request.IsEmptyProperty.HasValue`, apply it through a new domain method on `Household`, for example:
   ```csharp
   public void SetEmptyProperty(bool isEmptyProperty, string? justification, Guid modifiedByUserId)
   {
       IsEmptyProperty = isEmptyProperty;
       EmptyPropertyJustification = isEmptyProperty && !string.IsNullOrWhiteSpace(justification)
           ? justification.Trim()
           : null;
       MarkAsModified(modifiedByUserId);
   }
   ```
   - Unticking (`false`) clears the justification.
   - If `IsEmptyProperty` is true and `EmptyPropertyJustification` is `null`, keep the existing justification rather than wiping it. Only overwrite it when a non-empty value is sent.

5. **Doc comment.** Update the `HouseHold.cs` comment that says *"Set only by tablet (.uhc) imports; read-only on the desktop"*. The flag is now also set from the desktop.

6. **Optional (not used by the desktop).** Apply the same rule to the generic `CreateHouseholdCommand` / `UpdateHouseholdCommand` (`src/TRRCMS.Application/Household/Commands/...`) for consistency.

### Acceptance criteria
- `POST .../households` with `householdSize: 0`, all counts 0 and `isEmptyProperty: true` → **201**. The returned `HouseholdDto` has `isEmptyProperty: true`.
- The same request with `isEmptyProperty: false` (or the field omitted) → **400** `HouseholdSize_AtLeast1`, unchanged behaviour.
- `isEmptyProperty: true` with `householdSize: 2` or any non-zero count → **400** with the new message.
- `PUT` an imported empty household (tablet, with a justification), sending `isEmptyProperty: true` and `emptyPropertyJustification` equal to the stored value with edited `notes` → **200**. The flag and justification are kept.
- `PUT` with `isEmptyProperty: false` and `householdSize: 3` (with matching counts) → **200**. The flag is false and the justification is null.
- An existing request without the new fields behaves exactly as before.

---

## Change 2 — Import packages list: building locations and "assigned by" name (Issues Report item 7)

### Problem
On the desktop "حزم الاستيراد" (import packages) page, each package card shows `مواقع المباني` (building locations) and is always `—`. The client also wants the name of **the person who assigned the building to the field collector** (the supervisor who created the `BuildingAssignment`). The collector's own name is already shown from `collectorName`.

Root causes found:
1. **Locations.** `GetImportPackagesQueryHandler` fills `ImportPackageDto.Buildings` from `ImportService.ReadBuildingSummariesFromFileAsync` (`src/TRRCMS.Infrastructure/Services/ImportService.cs`), which reads only the `*_name` columns of the `.uhc` `buildings` table. Real tablet packages leave those columns **NULL** but fill the codes. Verified on a real package in `src/TRRCMS.WebAPI/archives/2026/05/ac5353eb3bd64c958c7159774d9beed7.uhc`: `governorate_code='02', district_code='00', sub_district_code='00', community_code='001', neighborhood_code='143'`, with every `*_name` NULL.
2. **Assigned by.** The data exists (`BuildingAssignment.AssignedByUserId`, `src/TRRCMS.Domain/Entities/BuildingAssignment.cs`) but is not exposed in the import package DTO.

### What the desktop now reads
From each item of `ImportPackageDto.buildings[]` (`ImportPackageBuildingDto`):
- Location: the first non-empty of `neighborhoodName`, `communityName`, `subDistrictName`, `districtName`, `governorateName`. This was already the case; nothing changes in the contract.
- **New:** `assignedByName` (string, nullable). The desktop shows the distinct names of all buildings in the package as `أسند المبنى: <names>`, or `—` when absent.

### Required backend changes
1. **DTO.** In `src/TRRCMS.Application/Import/Dtos/ImportPackageDto.cs`, add `public string? AssignedByName { get; set; }` to `ImportPackageBuildingDto`. It serialises as `assignedByName`.

2. **Read the identifiers from the package.** Extend `ReadBuildingSummariesFromFileAsync` to also read, when the columns exist (use the existing `ColumnOrNull` pattern):
   - `building_id`: the 17-digit building code, e.g. `02000000114378454`.
   - `governorate_code`, `district_code`, `sub_district_code`, `community_code`, `neighborhood_code`.

   Carry them on the summary, either as extra properties on `ImportPackageBuildingDto` (`BuildingCode`, `GovernorateCode`, ...; the desktop ignores unknown fields) or on an internal record. Note that the summaries are cached for 30 minutes by `ReadBuildingSummariesAsync`, so cache the raw file data only, not the resolved names.

3. **Resolve location names.** In `src/TRRCMS.Application/Import/Queries/GetImportPackages/GetImportPackagesQueryHandler.cs`, for each building whose `*_name` values are empty but whose codes are present, fill the names with the existing `IAdministrativeNameResolver.ResolveAsync(gov, dist, subDist, comm, neigh)` (`src/TRRCMS.Infrastructure/Services/AdministrativeNameResolver.cs`).
   - Map the resolver's `string.Empty` results to `null`.
   - Memoise by the code tuple within the request: many packages share neighbourhoods.
   - Names already present in the file win.

4. **Resolve "assigned by".** In the same handler, for each building:
   - Find the `Building` whose `BuildingId` (17-digit code) equals the file's `building_id`.
   - Find its `BuildingAssignment` with `FieldCollectorId == collectorId`, where `collectorId` comes from the existing `ResolveCollectorId(package)`.
   - Include completed and inactive assignments, because the assignment can be closed after the sync. If several match, take the latest `AssignedDate`.
   - Map `AssignedByUserId` to a display name with the same rule already used for `CollectorName`: `FullNameArabic`, else `FullNameEnglish`, else `Username`.
   - Set `AssignedByName`, or leave it `null` when there is no assignment or no `AssignedByUserId`.
   - Avoid N+1 queries: collect every building code and user id for the page first, then load buildings, assignments and users in batched queries. Reuse `_userRepository.GetByIdsAsync`, which is already used for collectors.

5. Keep the current error handling. A missing package file or an unreadable package must still not fail the whole list; the handler already catches and logs.

### Acceptance criteria
- `GET` the import packages list for the real package above → each `buildings[]` item has a non-null `neighborhoodName` (or another level's name) resolved from the codes.
- For a building that was assigned to the exporting collector by a supervisor, `buildings[].assignedByName` equals the supervisor's Arabic full name.
- For a building with no matching assignment, `assignedByName` is `null`.
- Packages whose files contain the `*_name` columns keep showing those names.
- The number of DB queries for one page does not grow per building (batched).

---

## FYI — no change requested (Issues Report item 8)

Tablet packages put the claim notes into `claims.claim_description`. The import stores that text as the relation's `ContractDetails`, a field the desktop claim dialog keeps hidden, so the notes looked empty. The desktop now shows `contractDetails` in the Notes field when `notes` is empty.

When the user saves, the desktop sends `PATCH /api/v1/Surveys/{surveyId}/relations/{relationId}` with `notes: "<text>"` and `contractDetails: null`, so the text moves into `Notes`. Please only confirm that `contractDetails: null` in that PATCH is acceptable, meaning it either clears or keeps `ContractDetails`. The text is preserved in `Notes` either way.
