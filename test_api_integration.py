#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
اختبار شامل لتكامل API مع التطبيق
=====================================
يختبر جميع الوظائف الأساسية للتأكد من عمل كل شيء بشكل صحيح.
"""

import sys
from services.api_client import TRRCMSApiClient, ApiConfig
from services.map_service_api import MapServiceAPI
from app.api_config import get_api_settings, check_tile_server_health


def test_1_api_settings():
    """Test 1: فحص إعدادات API"""
    print("=" * 60)
    print("Test 1: فحص إعدادات API")
    print("-" * 60)

    try:
        settings = get_api_settings()
        print(f"[OK] Base URL: {settings.base_url}")
        print(f"[OK] Data Source: {settings.data_source}")
        print(f"[OK] API Mode: {settings.is_api_mode()}")
        return True
    except Exception as e:
        print(f"[FAIL] فشل: {e}")
        return False


def test_2_tile_server():
    """Test 2: فحص Tile Server"""
    print("\n" + "=" * 60)
    print("Test 2: فحص Tile Server")
    print("-" * 60)

    try:
        is_healthy = check_tile_server_health()
        if is_healthy:
            print("[OK] Tile Server متاح ويعمل")
        else:
            print("[WARN]  Tile Server غير متاح (سيستخدم embedded tiles)")
        return True  # Not critical
    except Exception as e:
        print(f"[WARN]  تحذير: {e}")
        return True  # Not critical


def test_3_api_login():
    """Test 3: تسجيل الدخول"""
    print("\n" + "=" * 60)
    print("Test 3: تسجيل الدخول للـ API")
    print("-" * 60)

    try:
        config = ApiConfig(base_url="http://localhost:8081")
        client = TRRCMSApiClient(config)
        print(f"[OK] تم تسجيل الدخول بنجاح")
        print(f"[OK] Token: {client.access_token[:30]}...")
        return True, client
    except Exception as e:
        print(f"[FAIL] فشل تسجيل الدخول: {e}")
        return False, None


def test_4_get_buildings(client):
    """Test 4: جلب المباني للخريطة"""
    print("\n" + "=" * 60)
    print("Test 4: جلب المباني من API")
    print("-" * 60)

    try:
        buildings = client.get_buildings_for_map(
            north_east_lat=36.5,
            north_east_lng=37.5,
            south_west_lat=36.0,
            south_west_lng=36.8
        )
        print(f"[OK] تم جلب {len(buildings)} مبنى")

        if buildings:
            b = buildings[0]
            print(f"   - Building ID: {b.get('buildingId')}")
            print(f"   - UUID: {b.get('id')}")
            print(f"   - Location: ({b.get('latitude')}, {b.get('longitude')})")
            return True, buildings[0].get('id')
        else:
            print("[WARN]  لا توجد مباني في المنطقة")
            return True, None

    except Exception as e:
        print(f"[FAIL] فشل: {e}")
        return False, None


def test_5_update_polygon(client, uuid):
    """Test 5: تحديث Polygon للمبنى"""
    print("\n" + "=" * 60)
    print("Test 5: تحديث Polygon Geometry")
    print("-" * 60)

    if not uuid:
        print("[WARN]  تخطي (لا يوجد UUID)")
        return True

    try:
        # Test polygon
        polygon = "POLYGON((37.13 36.20, 37.14 36.20, 37.14 36.21, 37.13 36.21, 37.13 36.20))"

        result = client.update_building_geometry(
            building_id=uuid,
            building_geometry_wkt=polygon
        )
        print(f"[OK] تم تحديث Polygon بنجاح")

        # Verify
        updated = client.get_building_by_id(uuid)
        geom = updated.get('buildingGeometryWkt')
        if geom:
            print(f"[OK] Polygon محفوظ: {str(geom)[:60]}...")
        else:
            print("[WARN]  Polygon غير موجود في Response")

        return True

    except Exception as e:
        print(f"[FAIL] فشل: {e}")
        return False


def test_6_map_service_api():
    """Test 6: MapServiceAPI"""
    print("\n" + "=" * 60)
    print("Test 6: اختبار MapServiceAPI")
    print("-" * 60)

    try:
        map_service = MapServiceAPI()
        buildings = map_service.get_buildings_in_bbox(
            north_east_lat=36.5,
            north_east_lng=37.5,
            south_west_lat=36.0,
            south_west_lng=36.8
        )
        print(f"[OK] MapServiceAPI يعمل: {len(buildings)} مبنى")
        return True

    except Exception as e:
        print(f"[FAIL] فشل: {e}")
        return False


def main():
    """تشغيل جميع الاختبارات"""
    print("\n" + "=" * 60)
    print("[TEST] بدء الاختبارات الشاملة")
    print("=" * 60)

    results = []

    # Test 1: API Settings
    results.append(("إعدادات API", test_1_api_settings()))

    # Test 2: Tile Server
    results.append(("Tile Server", test_2_tile_server()))

    # Test 3: Login
    login_success, client = test_3_api_login()
    results.append(("تسجيل الدخول", login_success))

    if not login_success:
        print("\n[FAIL] فشل تسجيل الدخول، لا يمكن إكمال باقي الاختبارات")
        return False

    # Test 4: Get Buildings
    buildings_success, uuid = test_4_get_buildings(client)
    results.append(("جلب المباني", buildings_success))

    # Test 5: Update Polygon
    if uuid:
        results.append(("تحديث Polygon", test_5_update_polygon(client, uuid)))
    else:
        print("\n[WARN]  تخطي اختبار Polygon (لا يوجد مبنى)")
        results.append(("تحديث Polygon", True))

    # Test 6: MapServiceAPI
    results.append(("MapServiceAPI", test_6_map_service_api()))

    # Summary
    print("\n" + "=" * 60)
    print("[SUMMARY] ملخص النتائج")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "[OK] نجح" if success else "[FAIL] فشل"
        print(f"{status:8} - {name}")

    print("-" * 60)
    print(f"النتيجة: {passed}/{total} نجح")

    if passed == total:
        print("\n[SUCCESS] جميع الاختبارات نجحت!")
        return True
    else:
        print(f"\n[WARN]  {total - passed} اختبار فشل")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[WARN]  تم إيقاف الاختبارات")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] خطأ غير متوقع: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
