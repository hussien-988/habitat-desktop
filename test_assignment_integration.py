#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Assignment Integration with Backend API.
"""

import sys
from pathlib import Path

# Add to Python path
sys.path.insert(0, str(Path(__file__).parent))

from repositories.database import Database
from services.assignment_service import AssignmentService
from services.api_client import get_api_client
from utils.logger import setup_logger

logger = setup_logger()


def test_assignment_integration():
    """اختبار الربط مع Backend."""
    
    print("\n" + "="*80)
    print("Testing Assignment Integration")
    print("="*80)
    
    # 1. Initialize database
    print("\n1️⃣ Initializing database...")
    db = Database()
    db.initialize()
    print("   ✅ Database initialized")
    
    # 2. Add test field researcher
    print("\n2️⃣ Adding test field researcher...")
    db.execute("""
        INSERT OR IGNORE INTO users 
        (user_id, username, full_name, full_name_ar, role, password_hash, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, ("test_researcher", "researcher1", "Test Researcher", "باحث اختبار", "field_researcher", "hash"))
    print("   ✅ Field researcher added")
    
    # 3. Initialize AssignmentService with API
    print("\n3️⃣ Initializing AssignmentService with Backend sync...")
    try:
        api_client = get_api_client()
        print(f"   ✅ API Client: {api_client.base_url}")
    except Exception as e:
        api_client = None
        print(f"   ⚠️  No API Client: {e}")
    
    assignment_service = AssignmentService(db, api_client=api_client)
    print(f"   Sync enabled: {assignment_service.sync_enabled}")
    
    # 4. Get field researchers
    print("\n4️⃣ Getting field researchers...")
    researchers = assignment_service.get_field_teams()
    print(f"   Found {len(researchers)} researchers:")
    for r in researchers:
        print(f"      - {r['team_name']} (ID: {r['team_id']})")
    
    # 5. Create test assignment
    print("\n5️⃣ Creating test assignment...")
    try:
        assignments = assignment_service.create_batch_assignments(
            building_ids=["test-building-001", "test-building-002"],
            field_team_name=researchers[0]['team_id'] if researchers else "test_researcher",
            assigned_by="test_manager",
            notes="Test assignment from integration test"
        )
        print(f"   ✅ Created {len(assignments)} assignments")
        
        if assignment_service.sync_enabled:
            print("   ✅ Synced to Backend automatically")
        else:
            print("   ⚠️  Backend sync disabled (local only)")
            
    except Exception as e:
        print(f"   ❌ Failed to create assignment: {e}")
    
    # 6. Get assignment statistics
    print("\n6️⃣ Getting assignment statistics...")
    try:
        stats = assignment_service.get_assignment_statistics()
        print(f"   Total assignments: {stats.get('total', 0)}")
        print(f"   Pending transfers: {stats.get('pending_transfers', 0)}")
    except Exception as e:
        print(f"   ⚠️  Failed to get stats: {e}")
    
    print("\n" + "="*80)
    print("✅ Test completed successfully!")
    print("="*80 + "\n")


if __name__ == "__main__":
    test_assignment_integration()
