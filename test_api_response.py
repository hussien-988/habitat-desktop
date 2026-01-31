# -*- coding: utf-8 -*-
"""Quick test script to see what the API returns for buildings."""

import json
import ssl
import urllib.request
import urllib.error

# First login to get token
API_BASE = "https://localhost:7204/api"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# Login
login_data = json.dumps({"username": "admin", "password": "admin123"}).encode("utf-8")
login_req = urllib.request.Request(
    f"{API_BASE}/Auth/login",
    data=login_data,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(login_req, timeout=30, context=ssl_ctx) as resp:
        login_response = json.loads(resp.read().decode("utf-8"))
        print("Login response keys:", list(login_response.keys()))
        token = login_response.get("token") or login_response.get("accessToken") or login_response.get("access_token")
        print(f"Token obtained: {bool(token)}")
except Exception as e:
    print(f"Login failed: {e}")
    exit(1)

# Get buildings
buildings_req = urllib.request.Request(
    f"{API_BASE}/Buildings",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    },
    method="GET"
)

try:
    with urllib.request.urlopen(buildings_req, timeout=30, context=ssl_ctx) as resp:
        buildings_response = json.loads(resp.read().decode("utf-8"))

        print(f"\nResponse type: {type(buildings_response)}")

        if isinstance(buildings_response, dict):
            print(f"Response keys: {list(buildings_response.keys())}")
            # Check for wrapped data
            if "data" in buildings_response:
                buildings_response = buildings_response["data"]
            elif "buildings" in buildings_response:
                buildings_response = buildings_response["buildings"]

        if isinstance(buildings_response, list):
            print(f"\nNumber of buildings: {len(buildings_response)}")

            if buildings_response:
                print("\n=== First 3 buildings ===")
                for i, bld in enumerate(buildings_response[:3]):
                    print(f"\nBuilding {i+1}:")
                    print(f"  Keys: {list(bld.keys())}")
                    print(f"  buildingType: {bld.get('buildingType')}")
                    print(f"  building_type: {bld.get('building_type')}")
                    print(f"  BuildingType: {bld.get('BuildingType')}")
                    print(f"  type: {bld.get('type')}")
                    print(f"  Full item: {json.dumps(bld, indent=2, ensure_ascii=False)[:500]}...")
except Exception as e:
    print(f"Get buildings failed: {e}")
