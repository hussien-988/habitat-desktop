# -*- coding: utf-8 -*-
"""
Dashboard statistics service.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta

from repositories.database import Database
from repositories.building_repository import BuildingRepository
from repositories.claim_repository import ClaimRepository
from repositories.person_repository import PersonRepository
from utils.logger import get_logger

logger = get_logger(__name__)


class DashboardService:
    """Service for dashboard statistics and KPIs."""

    def __init__(self, db: Database):
        self.db = db
        self.building_repo = BuildingRepository(db)
        self.claim_repo = ClaimRepository(db)
        self.person_repo = PersonRepository(db)

    def get_overview_stats(self) -> Dict[str, Any]:
        """Get main KPI statistics."""
        building_stats = self.building_repo.get_statistics()
        claim_stats = self.claim_repo.get_statistics()

        return {
            "total_buildings": building_stats.get("total", 0),
            "total_units": building_stats.get("total_units", 0),
            "total_claims": claim_stats.get("total", 0),
            "total_persons": self.person_repo.count(),
            "pending_claims": claim_stats.get("pending_review", 0),
            "claims_with_conflicts": claim_stats.get("with_conflicts", 0),
            "recent_claims": claim_stats.get("recent", 0),
        }

    def get_buildings_by_status(self) -> Dict[str, int]:
        """Get building counts by status."""
        stats = self.building_repo.get_statistics()
        return stats.get("by_status", {})

    def get_buildings_by_type(self) -> Dict[str, int]:
        """Get building counts by type."""
        stats = self.building_repo.get_statistics()
        return stats.get("by_type", {})

    def get_buildings_by_neighborhood(self) -> Dict[str, int]:
        """Get building counts by neighborhood (top 10)."""
        stats = self.building_repo.get_statistics()
        return stats.get("by_neighborhood", {})

    def get_claims_by_status(self) -> Dict[str, int]:
        """Get claim counts by status."""
        stats = self.claim_repo.get_statistics()
        return stats.get("by_status", {})

    def get_recent_activity(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent activity log."""
        # Simulated recent activity for prototype
        activities = []

        # Get recent claims
        claims = self.claim_repo.get_all(limit=5)
        for claim in claims:
            activities.append({
                "type": "claim",
                "action": "created",
                "description": f"Claim {claim.claim_id} created",
                "description_ar": f"تم إنشاء المطالبة {claim.claim_id}",
                "timestamp": claim.created_at.isoformat() if claim.created_at else "",
                "user": claim.created_by or "system"
            })

        # Get recent imports
        rows = self.db.fetch_all(
            "SELECT * FROM import_history ORDER BY import_date DESC LIMIT 5"
        )
        for row in rows:
            activities.append({
                "type": "import",
                "action": "completed",
                "description": f"Import {row['import_id']}: {row['imported_records']} records",
                "description_ar": f"استيراد {row['import_id']}: {row['imported_records']} سجل",
                "timestamp": row["import_date"],
                "user": row["imported_by"]
            })

        # Sort by timestamp
        activities.sort(
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )

        return activities[:limit]

    def get_import_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent import history."""
        rows = self.db.fetch_all(
            "SELECT * FROM import_history ORDER BY import_date DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in rows]

    def get_data_quality_metrics(self) -> Dict[str, Any]:
        """Get data quality metrics."""
        # Buildings with coordinates
        result = self.db.fetch_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 ELSE 0 END) as with_coords
            FROM buildings
        """)

        buildings_total = result["total"] if result else 0
        buildings_with_coords = result["with_coords"] if result else 0

        # Persons with national ID
        result = self.db.fetch_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN national_id IS NOT NULL AND national_id != '' THEN 1 ELSE 0 END) as with_id
            FROM persons
        """)

        persons_total = result["total"] if result else 0
        persons_with_id = result["with_id"] if result else 0

        return {
            "buildings_with_coordinates": {
                "count": buildings_with_coords,
                "total": buildings_total,
                "percentage": round(buildings_with_coords / buildings_total * 100, 1) if buildings_total > 0 else 0
            },
            "persons_with_national_id": {
                "count": persons_with_id,
                "total": persons_total,
                "percentage": round(persons_with_id / persons_total * 100, 1) if persons_total > 0 else 0
            }
        }

    def get_chart_data(self, chart_type: str) -> Dict[str, Any]:
        """Get data formatted for charts."""
        if chart_type == "buildings_by_status":
            data = self.get_buildings_by_status()
            return {
                "labels": list(data.keys()),
                "values": list(data.values()),
                "colors": ["#28a745", "#ffc107", "#fd7e14", "#dc3545"]
            }

        elif chart_type == "buildings_by_type":
            data = self.get_buildings_by_type()
            return {
                "labels": list(data.keys()),
                "values": list(data.values()),
                "colors": ["#0072BC", "#17a2b8", "#6c757d"]
            }

        elif chart_type == "claims_by_status":
            data = self.get_claims_by_status()
            return {
                "labels": list(data.keys()),
                "values": list(data.values()),
                "colors": ["#6c757d", "#007bff", "#17a2b8", "#ffc107", "#28a745", "#dc3545"]
            }

        elif chart_type == "buildings_by_neighborhood":
            data = self.get_buildings_by_neighborhood()
            return {
                "labels": list(data.keys()),
                "values": list(data.values()),
                "colors": ["#0072BC"] * len(data)
            }

        return {}
