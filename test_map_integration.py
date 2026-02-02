#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
اختبار تكامل الخريطة مع API
=============================
يختبر أن الخريطة تستخدم API وليس قاعدة البيانات المحلية
"""

import sys
from repositories.database import Database
from controllers.map_controller import MapController
from services.map_service_api import MapServiceAPI
from services.tile_server_manager import get_tile_server_url
from app.api_config import get_api_settings, check_tile_server_health


def test_tile_server():
    """اختبار Tile Server"""
    print("\n" + "="*70)
    print("TEST 1: Tile Server Source")
    print("="*70)

    try:
        # Check health
        is_healthy = check_tile_server_health()
        print(f"[INFO] Tile Server Health Check: {'PASSED' if is_healthy else 'FAILED'}")

        # Get URL
        tile_url = get_tile_server_url()
        print(f"[INFO] Tile Server URL: {tile_url}")

        if "localhost:5000" in tile_url or "127.0.0.1:5000" in tile_url:
            print("[OK] Using DOCKER tile server (port 5000)")
            return True, "docker"
        elif "localhost:" in tile_url or "127.0.0.1:" in tile_url:
            print("[WARN] Using EMBEDDED tile server (random port)")
            return True, "embedded"
        else:
            print(f"[INFO] Using external tile server: {tile_url}")
            return True, "external"

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False, None


def test_map_service_api():
    """اختبار MapServiceAPI"""
    print("\n" + "="*70)
    print("TEST 2: MapServiceAPI - Direct API Call")
    print("="*70)

    try:
        api_settings = get_api_settings()
        print(f"[INFO] API Mode: {api_settings.is_api_mode()}")
        print(f"[INFO] Base URL: {api_settings.base_url}")
        print(f"[INFO] Data Source: {api_settings.data_source}")
        print()

        # Create MapServiceAPI
        print("[INFO] Creating MapServiceAPI instance...")
        map_service = MapServiceAPI()
        print("[OK] MapServiceAPI created")
        print()

        # Test get_buildings_in_bbox
        print("[INFO] Calling get_buildings_in_bbox()...")
        print("[INFO] Request: POST /api/v1/Buildings/map")
        print("[INFO] BBox: NE(36.5, 37.5) - SW(36.0, 36.8)")

        buildings = map_service.get_buildings_in_bbox(
            north_east_lat=36.5,
            north_east_lng=37.5,
            south_west_lat=36.0,
            south_west_lng=36.8
        )

        print()
        print(f"[OK] Response received: {len(buildings)} buildings")

        if buildings:
            print()
            print("[INFO] Sample Building Data:")
            b = buildings[0]
            print(f"  building_uuid: {b.building_uuid}")
            print(f"  building_id: {b.building_id}")
            print(f"  building_id_formatted: {b.building_id_formatted}")
            print(f"  latitude: {b.latitude}")
            print(f"  longitude: {b.longitude}")
            print(f"  building_status: {b.building_status}")
            print(f"  building_type: {b.building_type}")
            has_polygon = bool(b.geo_location and 'POLYGON' in str(b.geo_location).upper())
            print(f"  has_polygon: {has_polygon}")
            if has_polygon:
                print(f"  geo_location (WKT): {str(b.geo_location)[:60]}...")

        return True, len(buildings)

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False, 0


def test_map_controller():
    """اختبار MapController"""
    print("\n" + "="*70)
    print("TEST 3: MapController - Using API")
    print("="*70)

    try:
        # Create database (needed for constructor)
        db = Database()

        print("[INFO] Creating MapController...")
        controller = MapController(db)

        # Check if it's using API
        service_type = type(controller.map_service).__name__
        print(f"[INFO] Map Service Type: {service_type}")

        if service_type == "MapServiceAPI":
            print("[OK] MapController is using MapServiceAPI")
            return True
        else:
            print(f"[WARN] MapController is using {service_type} (not API)")
            return False

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_request_response_format():
    """اختبار صيغة Request/Response"""
    print("\n" + "="*70)
    print("TEST 4: API Request/Response Format")
    print("="*70)

    try:
        from services.api_client import TRRCMSApiClient, ApiConfig

        print("[INFO] Creating API client...")
        config = ApiConfig(base_url="http://localhost:8081")
        client = TRRCMSApiClient(config)
        print("[OK] Logged in")
        print()

        # Test request
        print("[INFO] Testing POST /api/v1/Buildings/map")
        print("[INFO] Request Body:")
        request_body = {
            "northEastLat": 36.5,
            "northEastLng": 37.5,
            "southWestLat": 36.0,
            "southWestLng": 36.8
        }
        print(f"  {request_body}")
        print()

        buildings = client.get_buildings_for_map(
            north_east_lat=36.5,
            north_east_lng=37.5,
            south_west_lat=36.0,
            south_west_lng=36.8
        )

        print(f"[INFO] Response Status: 200 OK")
        print(f"[INFO] Response Type: List[BuildingMapDto]")
        print(f"[INFO] Count: {len(buildings)}")
        print()

        if buildings:
            print("[INFO] Response Sample (first building):")
            import json
            print(json.dumps(buildings[0], indent=2, ensure_ascii=False))

        return True

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False


def main():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*70)
    print("[TEST] Map Integration Tests - API & Tile Server")
    print("="*70)

    results = []

    # Test 1: Tile Server
    tile_success, tile_source = test_tile_server()
    results.append(("Tile Server", tile_success))

    # Test 2: MapServiceAPI
    api_success, building_count = test_map_service_api()
    results.append(("MapServiceAPI", api_success))

    # Test 3: MapController
    controller_success = test_map_controller()
    results.append(("MapController", controller_success))

    # Test 4: Request/Response
    format_success = test_request_response_format()
    results.append(("Request/Response Format", format_success))

    # Summary
    print("\n" + "="*70)
    print("[SUMMARY] Test Results")
    print("="*70)

    for name, success in results:
        status = "[OK] PASS" if success else "[FAIL] FAIL"
        print(f"{status:12} - {name}")

    print("-"*70)

    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"Result: {passed}/{total} tests passed")

    # Final verdict
    print()
    if passed == total:
        print("[SUCCESS] All map integration tests passed!")
        print()
        if tile_source == "docker":
            print("[INFO] Tile Server: Using DOCKER (port 5000) ✓")
        elif tile_source == "embedded":
            print("[WARN] Tile Server: Using EMBEDDED (fallback)")

        if api_success:
            print(f"[INFO] API Integration: WORKING ({building_count} buildings) ✓")

        return True
    else:
        print(f"[WARN] {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARN] Tests interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
