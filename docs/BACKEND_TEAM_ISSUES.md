# Backend Team Issues

Issues rooted in the backend API, surfaced by the TRRCMS Desktop app. These are documented here instead of being worked around in the frontend.

---

## BE-001 — `PUT /api/v1/Buildings/{id}` ignores `buildingGeometryWkt` (point), leaving it stale

**Status:** Open
**Reported:** 2026-05-24
**Severity:** High — moved buildings render at their old location (or appear "missing") in any client that draws from the WKT.

### Summary
A building stores its point in two separate fields: `latitude`/`longitude` AND `buildingGeometryWkt`. When a building is updated via `PUT /api/v1/Buildings/{id}` (full update), the backend persists the new `latitude`/`longitude` but does **not** update `buildingGeometryWkt` — even when a consistent `POINT` WKT is included in the request body. The two fields drift apart and stay inconsistent.

### How to reproduce
1. Update a building's location (e.g. via the QGIS plugin "edit building" flow, plugin v1.8.0+), sending a body that includes consistent values:
   ```json
   {
     "buildingId": "816a834e-a8e9-4e98-9e97-cc5765bec4ad",
     "latitude": 36.20135120538788,
     "longitude": 37.16512240479676,
     "buildingGeometryWkt": "POINT(37.16512240479676 36.20135120538788)"
   }
   ```
2. Read the building back via `POST /api/v2/buildings/map` (or any read endpoint).

### Expected
`buildingGeometryWkt` reflects the new point: `POINT (37.16512... 36.20135...)`.

### Actual (evidence, building 99999)
```
"latitude": 36.2013512,                              // updated ✅
"longitude": 37.1651224,                             // updated ✅
"buildingGeometryWkt": "POINT (37.1246654 36.1937879)" // STALE ❌ (a previous location)
```
The request body carried the correct WKT (confirmed in the QGIS plugin log), but the backend dropped it.

### Impact
The Desktop map renders building markers from `buildingGeometryWkt` (it takes priority over `latitude`/`longitude` in `services/geojson_converter.py`). With a stale WKT, a relocated building shows at its old position and appears missing at its new position (e.g. in the "add claim" building picker).

### Suggested fix (one of)
- On `PUT /api/v1/Buildings/{id}`, when `latitude`/`longitude` change for a point building, regenerate `buildingGeometryWkt = POINT(lng lat)` server-side; **or**
- Accept and persist a `POINT` `buildingGeometryWkt` from the request body (currently `geometryWkt` appears reserved for POLYGON footprints only, per the `/Buildings/{id}/geometry` endpoint contract).

Either keeps the two representations in sync for all clients.
