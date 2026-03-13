# -*- coding: utf-8 -*-
"""
Test script for sync status simulation.
Usage:
    python test_sync.py list                    - List all assignments
    python test_sync.py sync <assignment_id>    - Set to "transferring"
    python test_sync.py complete <assignment_id> - Set to "transferred"
    python test_sync.py fail <assignment_id>    - Set to "failed"
    python test_sync.py reset <assignment_id>   - Reset to "not_transferred"
    python test_sync.py cancel <assignment_id>  - Set to "cancelled"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from services.api_client import TRRCMSApiClient, ApiConfig


STATUS_MAP = {
    "sync": "transferring",
    "complete": "transferred",
    "fail": "failed",
    "reset": "not_transferred",
    "cancel": "cancelled",
}

STATUS_LABELS = {
    "0": "في الانتظار",
    "1": "قيد المزامنة",
    "2": "تمت المزامنة",
    "3": "فشلت المزامنة",
    "4": "قيد الإعادة",
    "5": "ملغى",
    "not_transferred": "في الانتظار",
    "pending": "في الانتظار",
    "transferring": "قيد المزامنة",
    "in_progress": "قيد المزامنة",
    "transferred": "تمت المزامنة",
    "completed": "تمت المزامنة",
    "failed": "فشلت المزامنة",
    "cancelled": "ملغى",
}


def get_client():
    config = ApiConfig()
    client = TRRCMSApiClient(config)
    print(f"API: {config.base_url}")
    client.login(config.username, config.password)
    print("Login OK\n")
    return client


def list_assignments(client):
    response = client.get_all_assignments(page=1, page_size=50)
    items = (
        response if isinstance(response, list)
        else response.get("items", []) if isinstance(response, dict)
        else []
    )

    if not items:
        print("No assignments found.")
        return

    print(f"{'#':<4} {'ID':<38} {'Building':<20} {'Collector':<20} {'Status'}")
    print("-" * 110)

    for i, a in enumerate(items, 1):
        aid = a.get("id", "")
        building = a.get("buildingCode", a.get("buildingId", ""))[:18]
        collector = (
            a.get("fieldCollectorName")
            or a.get("fieldCollectorNameAr")
            or ""
        )[:18]
        status_raw = str(a.get("transferStatus", a.get("transferStatusName", "")))
        status_label = STATUS_LABELS.get(status_raw.lower(), status_raw)
        print(f"{i:<4} {aid:<38} {building:<20} {collector:<20} {status_label}")


def change_status(client, assignment_id, new_status):
    print(f"Changing {assignment_id[:8]}... -> {new_status}")
    try:
        result = client.update_assignment_transfer_status(
            assignment_id=assignment_id,
            transfer_status=new_status,
            device_id="test-device"
        )
        print(f"OK! Response: {result}")
    except Exception as e:
        print(f"Error: {e}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()
    client = get_client()

    if command == "list":
        list_assignments(client)
    elif command in STATUS_MAP:
        if len(sys.argv) < 3:
            print(f"Usage: python test_sync.py {command} <assignment_id>")
            return
        assignment_id = sys.argv[2]
        change_status(client, assignment_id, STATUS_MAP[command])
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
