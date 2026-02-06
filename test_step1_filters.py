#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Script: Step 1 Filter Integration with Backend API
========================================================

Tests UC-012 Step 1 filter functionality:
1. Filter by governorate
2. Filter by subdistrict
3. Filter by survey status
4. Combined filters
5. Search with filters
"""

import sys
from pathlib import Path

# Add trrcms to path
trrcms_path = Path(__file__).parent / "trrcms"
sys.path.insert(0, str(trrcms_path))

from services.api_client import get_api_client, ApiConfig
from controllers.building_controller import BuildingController
from utils.logger import setup_logger

logger = setup_logger()


def test_filter_api():
    """Test filter-based API search."""
    print("\n" + "=" * 80)
    print("🧪 TEST: Step 1 Filter Integration with Backend API")
    print("=" * 80)

    try:
        # Initialize API client
        print("\n1️⃣ Connecting to Backend API...")
        api_client = get_api_client()
        print("   ✅ Connected!")

        # Initialize BuildingController
        controller = BuildingController(use_api=True)
        controller.switch_to_api()

        # Test 1: Filter by governorate only
        print("\n2️⃣ TEST: Filter by governorate (حلب - 01)")
        result = controller.search_for_assignment_by_filters(
            governorate_code="01",
            has_active_assignment=False
        )
        if result.success:
            print(f"   ✅ SUCCESS: Found {len(result.data)} buildings in Aleppo")
            if result.data:
                sample = result.data[0]
                print(f"   📝 Sample: {sample.building_id} - {sample.governorate_name_ar}")
        else:
            print(f"   ❌ FAILED: {result.message}")

        # Test 2: Filter by survey status
        print("\n3️⃣ TEST: Filter by survey status (not_surveyed)")
        result = controller.search_for_assignment_by_filters(
            survey_status="not_surveyed",
            has_active_assignment=False
        )
        if result.success:
            print(f"   ✅ SUCCESS: Found {len(result.data)} unsurveyed buildings")
        else:
            print(f"   ❌ FAILED: {result.message}")

        # Test 3: Combined filters
        print("\n4️⃣ TEST: Combined filters (Aleppo + not_surveyed)")
        result = controller.search_for_assignment_by_filters(
            governorate_code="01",
            survey_status="not_surveyed",
            has_active_assignment=False,
            page=1,
            page_size=100
        )
        if result.success:
            print(f"   ✅ SUCCESS: Found {len(result.data)} buildings")
            print(f"   📊 These are unassigned, unsurveyed buildings in Aleppo")
        else:
            print(f"   ❌ FAILED: {result.message}")

        # Test 4: Filter with subdistrict
        print("\n5️⃣ TEST: Filter by subdistrict (if available)")
        result = controller.search_for_assignment_by_filters(
            governorate_code="01",
            subdistrict_code="0101",  # Example: Aleppo center
            has_active_assignment=False
        )
        if result.success:
            print(f"   ✅ SUCCESS: Found {len(result.data)} buildings in subdistrict")
        else:
            print(f"   ⚠️ Note: {result.message}")

        # Test 5: Performance comparison
        print("\n6️⃣ TEST: Performance check")
        import time

        # API-based search
        start = time.time()
        result = controller.search_for_assignment_by_filters(
            governorate_code="01",
            has_active_assignment=False,
            page_size=500
        )
        api_time = time.time() - start

        if result.success:
            print(f"   ✅ API Search: {len(result.data)} buildings in {api_time:.2f}s")
            print(f"   📊 Performance: {'Fast' if api_time < 2 else 'Acceptable' if api_time < 5 else 'Slow'}")

        print("\n" + "=" * 80)
        print("✅ All tests completed!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


def test_ui_workflow():
    """Test UI workflow simulation."""
    print("\n" + "=" * 80)
    print("🎨 UI WORKFLOW SIMULATION")
    print("=" * 80)

    print("\n📝 Simulating user actions:")
    print("   1. User selects governorate: حلب (01)")
    print("   2. User selects survey status: لم يتم المسح (not_surveyed)")
    print("   3. Filter change triggers → _on_filter_changed()")
    print("   4. Calls → _load_buildings_from_api()")
    print("   5. Calls → building_controller.search_for_assignment_by_filters()")
    print("   6. Calls → api_client.get_buildings_for_assignment()")
    print("   7. Backend returns filtered buildings")
    print("   8. UI displays results")

    print("\n✅ Expected result:")
    print("   - Only buildings in Aleppo that are not surveyed")
    print("   - Only buildings without active assignments")
    print("   - Fast response (< 2 seconds)")

    print("\n📊 Manual testing steps:")
    print("   1. Run main.py")
    print("   2. Navigate to: إدارة المسح الميداني → تعيين مباني للفرق الميدانية")
    print("   3. Select filters:")
    print("      - المحافظة: حلب")
    print("      - حالة المسح: لم يتم المسح")
    print("   4. Check console for API call logs")
    print("   5. Verify buildings appear in suggestions list")
    print("   6. Try search: type building ID → should filter API results")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("\n🚀 Starting Step 1 Filter Tests...\n")

    # Test 1: API functionality
    test_filter_api()

    # Test 2: UI workflow explanation
    test_ui_workflow()

    print("\n✅ Testing complete! Check logs above for results.\n")
