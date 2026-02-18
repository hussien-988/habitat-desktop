# -*- coding: utf-8 -*-
"""
Advanced Dashboard Service
==========================
Implements comprehensive dashboard and analytics as per FSD requirements.

Features:
- Real-time statistics and KPIs
- Claims status tracking by region
- Building registration progress
- Field team performance metrics
- Data quality indicators
- Trend analysis and charts
- Export to various formats
- Configurable dashboard widgets
- Multi-level filtering (governorate, district, subdistrict)
- Date range filtering
- Comparison reports
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict

from repositories.database import Database
from repositories.building_repository import BuildingRepository
from repositories.claim_repository import ClaimRepository
from repositories.person_repository import PersonRepository
from utils.logger import get_logger

logger = get_logger(__name__)


# ==================== Data Classes and Enums ====================

class MetricType(Enum):
    """Types of dashboard metrics."""
    COUNT = "count"
    SUM = "sum"
    AVERAGE = "average"
    PERCENTAGE = "percentage"
    RATE = "rate"
    TREND = "trend"


class ChartType(Enum):
    """Types of dashboard charts."""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    DONUT = "donut"
    AREA = "area"
    STACKED_BAR = "stacked_bar"
    HEATMAP = "heatmap"
    MAP = "map"


class TimeGranularity(Enum):
    """Time granularity for trends."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class DashboardScope(Enum):
    """Dashboard scope level."""
    NATIONAL = "national"
    GOVERNORATE = "governorate"
    DISTRICT = "district"
    SUBDISTRICT = "subdistrict"
    COMMUNITY = "community"


@dataclass
class DashboardFilter:
    """Filters for dashboard queries."""
    governorate_code: Optional[str] = None
    district_code: Optional[str] = None
    subdistrict_code: Optional[str] = None
    community_code: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    claim_status: Optional[str] = None
    building_type: Optional[str] = None
    field_team_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                if isinstance(value, date):
                    result[key] = value.isoformat()
                else:
                    result[key] = value
        return result


@dataclass
class KPIMetric:
    """Key Performance Indicator metric."""
    name: str
    name_ar: str
    value: Any
    previous_value: Optional[Any] = None
    unit: str = ""
    trend_direction: str = ""  # up, down, stable
    trend_percentage: float = 0.0
    target: Optional[Any] = None
    status: str = "normal"  # good, warning, critical, normal

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChartData:
    """Data structure for chart rendering."""
    chart_type: ChartType
    title: str
    title_ar: str
    labels: List[str]
    datasets: List[Dict[str, Any]]
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chart_type": self.chart_type.value,
            "title": self.title,
            "title_ar": self.title_ar,
            "labels": self.labels,
            "datasets": self.datasets,
            "options": self.options
        }


@dataclass
class RegionSummary:
    """Summary statistics for a region."""
    region_code: str
    region_name: str
    region_name_ar: str
    total_buildings: int = 0
    total_claims: int = 0
    pending_claims: int = 0
    approved_claims: int = 0
    rejected_claims: int = 0
    in_progress_claims: int = 0
    completion_rate: float = 0.0
    data_quality_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FieldTeamMetrics:
    """Performance metrics for field teams."""
    team_id: str
    team_name: str
    assigned_buildings: int = 0
    completed_buildings: int = 0
    pending_buildings: int = 0
    completion_rate: float = 0.0
    avg_completion_time_hours: float = 0.0
    data_quality_score: float = 0.0
    claims_submitted: int = 0
    claims_approved_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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

    # ==================== Advanced KPI Methods ====================

    def get_kpi_summary(self, filters: Optional[DashboardFilter] = None) -> List[KPIMetric]:
        """Get summary KPIs for dashboard header."""
        kpis = []

        # Total Buildings
        building_stats = self.building_repo.get_statistics()
        total_buildings = building_stats.get("total", 0)

        kpis.append(KPIMetric(
            name="Total Buildings",
            name_ar="إجمالي المباني",
            value=total_buildings,
            unit="buildings"
        ))

        # Total Claims
        claim_stats = self.claim_repo.get_statistics()
        total_claims = claim_stats.get("total", 0)

        kpis.append(KPIMetric(
            name="Total Claims",
            name_ar="إجمالي المطالبات",
            value=total_claims,
            unit="claims"
        ))

        # Pending Claims
        pending_claims = claim_stats.get("pending_review", 0)
        kpis.append(KPIMetric(
            name="Pending Claims",
            name_ar="المطالبات المعلقة",
            value=pending_claims,
            unit="claims",
            status="warning" if pending_claims > 100 else "normal"
        ))

        # Approval Rate
        by_status = claim_stats.get("by_status", {})
        approved = by_status.get("approved", 0)
        approval_rate = (approved / total_claims * 100) if total_claims > 0 else 0

        kpis.append(KPIMetric(
            name="Approval Rate",
            name_ar="معدل الموافقة",
            value=round(approval_rate, 1),
            unit="%",
            target=80,
            status="good" if approval_rate >= 80 else "warning" if approval_rate >= 60 else "critical"
        ))

        # Data Quality Score
        dq_metrics = self.get_data_quality_metrics()
        dq_score = dq_metrics.get("buildings_with_coordinates", {}).get("percentage", 0)
        kpis.append(KPIMetric(
            name="Data Quality",
            name_ar="جودة البيانات",
            value=round(dq_score, 1),
            unit="%",
            target=95,
            status="good" if dq_score >= 95 else "warning" if dq_score >= 80 else "critical"
        ))

        # Total Persons
        persons_count = self.person_repo.count()
        kpis.append(KPIMetric(
            name="Total Persons",
            name_ar="إجمالي الأشخاص",
            value=persons_count,
            unit="persons"
        ))

        return kpis

    # ==================== Trend Analysis ====================

    def get_claims_trend(
        self,
        granularity: TimeGranularity = TimeGranularity.DAILY,
        days: int = 30,
        filters: Optional[DashboardFilter] = None
    ) -> ChartData:
        """Get claims trend over time."""
        # Determine date grouping
        if granularity == TimeGranularity.DAILY:
            date_trunc = "date(created_at)"
        elif granularity == TimeGranularity.WEEKLY:
            date_trunc = "strftime('%Y-W%W', created_at)"
        elif granularity == TimeGranularity.MONTHLY:
            date_trunc = "strftime('%Y-%m', created_at)"
        else:
            date_trunc = "date(created_at)"

        rows = self.db.fetch_all(f"""
            SELECT
                {date_trunc} as period,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN status = 'pending' OR status IS NULL THEN 1 ELSE 0 END) as pending
            FROM claims
            WHERE created_at >= date('now', '-{days} days')
            GROUP BY {date_trunc}
            ORDER BY period
        """)

        labels = []
        total_data = []
        approved_data = []
        rejected_data = []
        pending_data = []

        for row in rows:
            labels.append(row['period'])
            total_data.append(row['total'])
            approved_data.append(row['approved'] or 0)
            rejected_data.append(row['rejected'] or 0)
            pending_data.append(row['pending'] or 0)

        return ChartData(
            chart_type=ChartType.LINE,
            title="Claims Trend",
            title_ar="اتجاه المطالبات",
            labels=labels,
            datasets=[
                {
                    "label": "الإجمالي",
                    "data": total_data,
                    "borderColor": "#007BFF",
                    "fill": False
                },
                {
                    "label": "موافق عليه",
                    "data": approved_data,
                    "borderColor": "#28A745",
                    "fill": False
                },
                {
                    "label": "مرفوض",
                    "data": rejected_data,
                    "borderColor": "#DC3545",
                    "fill": False
                },
                {
                    "label": "معلق",
                    "data": pending_data,
                    "borderColor": "#FFC107",
                    "fill": False
                }
            ]
        )

    def get_buildings_trend(
        self,
        days: int = 30,
        granularity: TimeGranularity = TimeGranularity.DAILY
    ) -> ChartData:
        """Get buildings registration trend over time."""
        if granularity == TimeGranularity.DAILY:
            date_trunc = "date(created_at)"
        elif granularity == TimeGranularity.WEEKLY:
            date_trunc = "strftime('%Y-W%W', created_at)"
        else:
            date_trunc = "strftime('%Y-%m', created_at)"

        rows = self.db.fetch_all(f"""
            SELECT
                {date_trunc} as period,
                COUNT(*) as count
            FROM buildings
            WHERE created_at >= date('now', '-{days} days')
            GROUP BY {date_trunc}
            ORDER BY period
        """)

        labels = [row['period'] for row in rows]
        data = [row['count'] for row in rows]

        return ChartData(
            chart_type=ChartType.AREA,
            title="Buildings Registration Trend",
            title_ar="اتجاه تسجيل المباني",
            labels=labels,
            datasets=[{
                "label": "المباني المسجلة",
                "data": data,
                "backgroundColor": "rgba(0, 123, 255, 0.3)",
                "borderColor": "#007BFF",
                "fill": True
            }]
        )

    # ==================== Regional Analysis ====================

    def get_region_summary(
        self,
        scope: DashboardScope = DashboardScope.GOVERNORATE,
        filters: Optional[DashboardFilter] = None
    ) -> List[RegionSummary]:
        """Get summary by region."""
        # Determine grouping column
        if scope == DashboardScope.GOVERNORATE:
            group_col = "governorate_code"
        elif scope == DashboardScope.DISTRICT:
            group_col = "district_code"
        elif scope == DashboardScope.SUBDISTRICT:
            group_col = "subdistrict_code"
        else:
            group_col = "community_code"

        rows = self.db.fetch_all(f"""
            SELECT
                b.{group_col} as region_code,
                COUNT(DISTINCT b.building_id) as total_buildings,
                COUNT(c.claim_id) as total_claims,
                SUM(CASE WHEN c.status = 'pending' OR c.status IS NULL THEN 1 ELSE 0 END) as pending_claims,
                SUM(CASE WHEN c.status = 'approved' THEN 1 ELSE 0 END) as approved_claims,
                SUM(CASE WHEN c.status = 'rejected' THEN 1 ELSE 0 END) as rejected_claims,
                SUM(CASE WHEN c.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_claims
            FROM buildings b
            LEFT JOIN claims c ON b.building_id = c.building_id
            WHERE b.{group_col} IS NOT NULL
            GROUP BY b.{group_col}
            ORDER BY total_buildings DESC
        """)

        summaries = []
        for row in rows:
            total = row['total_claims'] or 0
            completed = (row['approved_claims'] or 0) + (row['rejected_claims'] or 0)
            completion_rate = (completed / total * 100) if total > 0 else 0

            summaries.append(RegionSummary(
                region_code=row['region_code'] or "Unknown",
                region_name=f"Region {row['region_code']}",
                region_name_ar=f"منطقة {row['region_code']}",
                total_buildings=row['total_buildings'] or 0,
                total_claims=total,
                pending_claims=row['pending_claims'] or 0,
                approved_claims=row['approved_claims'] or 0,
                rejected_claims=row['rejected_claims'] or 0,
                in_progress_claims=row['in_progress_claims'] or 0,
                completion_rate=round(completion_rate, 1)
            ))

        return summaries

    # ==================== Field Team Performance ====================

    def get_field_team_metrics(
        self,
        filters: Optional[DashboardFilter] = None
    ) -> List[FieldTeamMetrics]:
        """Get performance metrics for all field teams."""
        try:
            rows = self.db.fetch_all("""
                SELECT
                    fa.assigned_to as team_id,
                    COUNT(*) as assigned_buildings,
                    SUM(CASE WHEN fa.status = 'completed' THEN 1 ELSE 0 END) as completed_buildings,
                    SUM(CASE WHEN fa.status = 'pending' OR fa.status IS NULL THEN 1 ELSE 0 END) as pending_buildings,
                    AVG(CASE
                        WHEN fa.status = 'completed' AND fa.completed_at IS NOT NULL
                        THEN julianday(fa.completed_at) - julianday(fa.assigned_at)
                        ELSE NULL
                    END) * 24 as avg_completion_hours
                FROM field_assignments fa
                WHERE fa.assigned_to IS NOT NULL
                GROUP BY fa.assigned_to
                ORDER BY completed_buildings DESC
            """)

            metrics = []
            for row in rows:
                assigned = row['assigned_buildings'] or 0
                completed = row['completed_buildings'] or 0
                completion_rate = (completed / assigned * 100) if assigned > 0 else 0

                metrics.append(FieldTeamMetrics(
                    team_id=row['team_id'],
                    team_name=f"Team {row['team_id']}",
                    assigned_buildings=assigned,
                    completed_buildings=completed,
                    pending_buildings=row['pending_buildings'] or 0,
                    completion_rate=round(completion_rate, 1),
                    avg_completion_time_hours=round(row['avg_completion_hours'] or 0, 1)
                ))

            return metrics

        except Exception as e:
            logger.error(f"Error getting field team metrics: {e}")
            return []

    def get_field_team_comparison_chart(
        self,
        filters: Optional[DashboardFilter] = None
    ) -> ChartData:
        """Get chart data comparing field team performance."""
        metrics = self.get_field_team_metrics(filters)

        labels = [m.team_name for m in metrics[:10]]
        completed = [m.completed_buildings for m in metrics[:10]]
        pending = [m.pending_buildings for m in metrics[:10]]

        return ChartData(
            chart_type=ChartType.STACKED_BAR,
            title="Field Team Performance",
            title_ar="أداء الفرق الميدانية",
            labels=labels,
            datasets=[
                {
                    "label": "مكتمل",
                    "data": completed,
                    "backgroundColor": "#28A745"
                },
                {
                    "label": "معلق",
                    "data": pending,
                    "backgroundColor": "#FFC107"
                }
            ]
        )

    # ==================== Registration Progress ====================

    def get_buildings_registration_progress(
        self,
        filters: Optional[DashboardFilter] = None
    ) -> Dict[str, Any]:
        """Get building registration progress."""
        # Total buildings
        result = self.db.fetch_one("SELECT COUNT(*) as total FROM buildings")
        total = result["total"] if result else 0

        # Buildings with claims
        result = self.db.fetch_one("""
            SELECT COUNT(DISTINCT building_id) as count FROM claims
        """)
        with_claims = result["count"] if result else 0

        # Buildings with approved claims
        result = self.db.fetch_one("""
            SELECT COUNT(DISTINCT building_id) as count FROM claims WHERE status = 'approved'
        """)
        approved = result["count"] if result else 0

        # Buildings with coordinates
        result = self.db.fetch_one("""
            SELECT COUNT(*) as count FROM buildings
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """)
        with_coords = result["count"] if result else 0

        return {
            "total_buildings": total,
            "buildings_with_claims": with_claims,
            "buildings_with_claims_percentage": round(with_claims / total * 100, 1) if total > 0 else 0,
            "buildings_approved": approved,
            "buildings_approved_percentage": round(approved / total * 100, 1) if total > 0 else 0,
            "buildings_with_coordinates": with_coords,
            "buildings_with_coordinates_percentage": round(with_coords / total * 100, 1) if total > 0 else 0,
            "progress_stages": [
                {"stage": "مسجل", "stage_ar": "مسجل", "count": total, "percentage": 100},
                {"stage": "مع مطالبات", "stage_ar": "مع مطالبات", "count": with_claims, "percentage": round(with_claims / total * 100, 1) if total > 0 else 0},
                {"stage": "موافق عليه", "stage_ar": "موافق عليه", "count": approved, "percentage": round(approved / total * 100, 1) if total > 0 else 0}
            ]
        }

    # ==================== Claims Donut Chart ====================

    def get_claims_status_donut(self, filters: Optional[DashboardFilter] = None) -> ChartData:
        """Get claims breakdown by status as donut chart."""
        stats = self.claim_repo.get_statistics()
        by_status = stats.get("by_status", {})

        colors = {
            'pending': '#FFC107',
            'approved': '#28A745',
            'rejected': '#DC3545',
            'in_progress': '#17A2B8',
            'under_review': '#6C757D'
        }

        status_labels = {
            'pending': 'معلق',
            'approved': 'موافق عليه',
            'rejected': 'مرفوض',
            'in_progress': 'قيد التنفيذ',
            'under_review': 'قيد المراجعة'
        }

        labels = []
        data = []
        background_colors = []

        for status, count in by_status.items():
            labels.append(status_labels.get(status, status))
            data.append(count)
            background_colors.append(colors.get(status, '#6C757D'))

        return ChartData(
            chart_type=ChartType.DONUT,
            title="Claims by Status",
            title_ar="المطالبات حسب الحالة",
            labels=labels,
            datasets=[{
                "data": data,
                "backgroundColor": background_colors
            }]
        )

    # ==================== Export ====================

    def export_dashboard_data(
        self,
        format: str = "json",
        filters: Optional[DashboardFilter] = None
    ) -> str:
        """Export dashboard data to various formats."""
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "filters": filters.to_dict() if filters else {},
            "kpis": [kpi.to_dict() for kpi in self.get_kpi_summary(filters)],
            "claims_by_status": self.get_claims_status_donut(filters).to_dict(),
            "claims_trend": self.get_claims_trend(filters=filters).to_dict(),
            "buildings_progress": self.get_buildings_registration_progress(filters),
            "regional_summary": [s.to_dict() for s in self.get_region_summary(filters=filters)],
            "field_team_metrics": [m.to_dict() for m in self.get_field_team_metrics(filters)],
            "data_quality": self.get_data_quality_metrics()
        }

        if format == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            return json.dumps(data, ensure_ascii=False)

    # ==================== Available Widgets ====================

    def get_available_widgets(self) -> List[Dict[str, Any]]:
        """Get list of available dashboard widgets."""
        return [
            {
                "widget_id": "kpi_summary",
                "name": "KPI Summary",
                "name_ar": "ملخص مؤشرات الأداء",
                "description": "Key performance indicators overview",
                "type": "kpi_cards",
                "default_size": {"width": 12, "height": 1}
            },
            {
                "widget_id": "claims_status_donut",
                "name": "Claims by Status",
                "name_ar": "المطالبات حسب الحالة",
                "description": "Donut chart of claims distribution by status",
                "type": "chart",
                "chart_type": "donut",
                "default_size": {"width": 4, "height": 2}
            },
            {
                "widget_id": "claims_trend",
                "name": "Claims Trend",
                "name_ar": "اتجاه المطالبات",
                "description": "Line chart showing claims over time",
                "type": "chart",
                "chart_type": "line",
                "default_size": {"width": 8, "height": 2}
            },
            {
                "widget_id": "buildings_by_type",
                "name": "Buildings by Type",
                "name_ar": "المباني حسب النوع",
                "description": "Bar chart of buildings by type",
                "type": "chart",
                "chart_type": "bar",
                "default_size": {"width": 6, "height": 2}
            },
            {
                "widget_id": "regional_map",
                "name": "Regional Map",
                "name_ar": "خريطة المناطق",
                "description": "Geographic distribution of data",
                "type": "map",
                "default_size": {"width": 6, "height": 3}
            },
            {
                "widget_id": "field_team_performance",
                "name": "Field Team Performance",
                "name_ar": "أداء الفرق الميدانية",
                "description": "Comparison of field team metrics",
                "type": "chart",
                "chart_type": "stacked_bar",
                "default_size": {"width": 6, "height": 2}
            },
            {
                "widget_id": "data_quality_gauge",
                "name": "Data Quality",
                "name_ar": "جودة البيانات",
                "description": "Data quality score gauge",
                "type": "gauge",
                "default_size": {"width": 3, "height": 2}
            },
            {
                "widget_id": "recent_activity",
                "name": "Recent Activity",
                "name_ar": "النشاط الأخير",
                "description": "Recent system activity feed",
                "type": "activity_feed",
                "default_size": {"width": 3, "height": 2}
            },
            {
                "widget_id": "regional_table",
                "name": "Regional Summary Table",
                "name_ar": "جدول ملخص المناطق",
                "description": "Tabular summary by region",
                "type": "table",
                "default_size": {"width": 12, "height": 3}
            }
        ]
