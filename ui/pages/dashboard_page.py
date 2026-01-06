# -*- coding: utf-8 -*-
"""
Dashboard page with KPIs and charts - Professional design.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QScrollArea, QSizePolicy, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from app.config import Config
from repositories.database import Database
from services.dashboard_service import DashboardService
from utils.i18n import I18n
from utils.helpers import format_number
from utils.logger import get_logger

logger = get_logger(__name__)


class StatCard(QFrame):
    """Statistic card widget with professional design."""

    def __init__(self, title: str, value: str, color: str = None, accent_color: str = None, parent=None):
        super().__init__(parent)
        self.accent_color = accent_color or Config.PRIMARY_COLOR
        self._setup_ui(title, value, color)

    def _setup_ui(self, title: str, value: str, color: str):
        """Setup card UI."""
        self.setObjectName("stat-card")
        self.setStyleSheet(f"""
            QFrame#stat-card {{
                background-color: white;
                border-radius: 12px;
                border: none;
            }}
        """)

        # Add subtle shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: {Config.FONT_SIZE_LABEL}pt;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(self.title_label)

        # Value
        self.value_label = QLabel(value)
        value_color = color or Config.TEXT_COLOR
        self.value_label.setStyleSheet(f"""
            color: {value_color};
            font-size: {Config.FONT_SIZE_H1 + 8}pt;
            font-weight: 700;
        """)
        layout.addWidget(self.value_label)

        # Accent bar at bottom
        accent_bar = QFrame()
        accent_bar.setFixedHeight(4)
        accent_bar.setStyleSheet(f"""
            background-color: {self.accent_color};
            border-radius: 2px;
        """)
        layout.addWidget(accent_bar)

    def set_value(self, value: str):
        """Update the value."""
        self.value_label.setText(value)

    def set_title(self, title: str):
        """Update the title."""
        self.title_label.setText(title)


class ChartPlaceholder(QFrame):
    """Placeholder for charts with professional design."""

    def __init__(self, title: str, data: dict = None, parent=None):
        super().__init__(parent)
        self.title = title
        self.data = data or {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup chart placeholder UI."""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 12px;
                border: none;
            }}
        """)
        self.setMinimumHeight(220)

        # Add shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        title_label = QLabel(self.title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {Config.FONT_SIZE_H2}pt;
            color: {Config.TEXT_COLOR};
        """)
        layout.addWidget(title_label)

        # Simple bar representation
        if self.data.get("labels") and self.data.get("values"):
            max_val = max(self.data["values"]) if self.data["values"] else 1
            colors = [Config.PRIMARY_COLOR, Config.SUCCESS_COLOR, Config.WARNING_COLOR,
                      Config.INFO_COLOR, Config.ERROR_COLOR]

            for idx, (label, value) in enumerate(zip(self.data["labels"], self.data["values"])):
                row = QHBoxLayout()
                row.setSpacing(12)

                # Label
                lbl = QLabel(str(label)[:20])
                lbl.setFixedWidth(120)
                lbl.setStyleSheet(f"font-size: {Config.FONT_SIZE_SMALL}pt; color: {Config.TEXT_LIGHT};")
                row.addWidget(lbl)

                # Bar container
                bar_container = QWidget()
                bar_container.setFixedHeight(24)
                bar_container.setStyleSheet("background-color: #F1F5F9; border-radius: 4px;")

                bar_layout = QHBoxLayout(bar_container)
                bar_layout.setContentsMargins(0, 0, 0, 0)
                bar_layout.setSpacing(0)

                # Bar
                bar_width = int((value / max_val) * 100) if max_val > 0 else 0
                bar = QLabel()
                bar.setFixedHeight(24)
                bar.setMinimumWidth(bar_width * 2)
                bar.setMaximumWidth(bar_width * 2)
                bar_color = colors[idx % len(colors)]
                bar.setStyleSheet(f"background-color: {bar_color}; border-radius: 4px;")
                bar_layout.addWidget(bar)
                bar_layout.addStretch()

                row.addWidget(bar_container, 1)

                # Value
                val_lbl = QLabel(str(value))
                val_lbl.setFixedWidth(40)
                val_lbl.setAlignment(Qt.AlignRight)
                val_lbl.setStyleSheet(f"font-size: {Config.FONT_SIZE}pt; font-weight: 600; color: {Config.TEXT_COLOR};")
                row.addWidget(val_lbl)

                layout.addLayout(row)

        layout.addStretch()


class DashboardPage(QWidget):
    """Dashboard page with overview statistics."""

    def __init__(self, db: Database, i18n: I18n, parent=None):
        super().__init__(parent)
        self.db = db
        self.i18n = i18n
        self.dashboard_service = DashboardService(db)

        self._stat_cards = {}
        self._setup_ui()

    def _setup_ui(self):
        """Setup dashboard UI."""
        # Scroll area for responsiveness
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content = QWidget()
        content.setStyleSheet(f"background-color: {Config.BACKGROUND_COLOR};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(28)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel(self.i18n.t("overview"))
        header_label.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H1}pt;
            font-weight: 700;
            color: {Config.TEXT_COLOR};
        """)
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Stats cards row 1
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)

        self._stat_cards["buildings"] = StatCard(
            self.i18n.t("total_buildings"), "0", accent_color=Config.PRIMARY_COLOR
        )
        stats_layout.addWidget(self._stat_cards["buildings"])

        self._stat_cards["units"] = StatCard(
            self.i18n.t("total_units"), "0", accent_color=Config.INFO_COLOR
        )
        stats_layout.addWidget(self._stat_cards["units"])

        self._stat_cards["claims"] = StatCard(
            self.i18n.t("total_claims"), "0", accent_color=Config.SUCCESS_COLOR
        )
        stats_layout.addWidget(self._stat_cards["claims"])

        self._stat_cards["persons"] = StatCard(
            self.i18n.t("total_persons"), "0", accent_color="#8B5CF6"
        )
        stats_layout.addWidget(self._stat_cards["persons"])

        layout.addLayout(stats_layout)

        # Second row - pending and conflicts
        stats_layout2 = QHBoxLayout()
        stats_layout2.setSpacing(20)

        self._stat_cards["pending"] = StatCard(
            self.i18n.t("pending_review"), "0",
            color=Config.WARNING_COLOR, accent_color=Config.WARNING_COLOR
        )
        self._stat_cards["pending"].setMaximumWidth(300)
        stats_layout2.addWidget(self._stat_cards["pending"])

        self._stat_cards["conflicts"] = StatCard(
            self.i18n.t("with_conflicts"), "0",
            color=Config.ERROR_COLOR, accent_color=Config.ERROR_COLOR
        )
        self._stat_cards["conflicts"].setMaximumWidth(300)
        stats_layout2.addWidget(self._stat_cards["conflicts"])

        stats_layout2.addStretch()
        layout.addLayout(stats_layout2)

        # Charts row
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(20)

        self.buildings_by_status_chart = ChartPlaceholder(
            self.i18n.t("buildings_by_status")
        )
        charts_layout.addWidget(self.buildings_by_status_chart)

        self.buildings_by_type_chart = ChartPlaceholder(
            self.i18n.t("buildings_by_type")
        )
        charts_layout.addWidget(self.buildings_by_type_chart)

        layout.addLayout(charts_layout)

        # Recent activity section
        activity_header = QLabel(self.i18n.t("recent_activity"))
        activity_header.setStyleSheet(f"""
            font-size: {Config.FONT_SIZE_H2}pt;
            font-weight: 600;
            color: {Config.TEXT_COLOR};
            margin-top: 8px;
        """)
        layout.addWidget(activity_header)

        self.activity_container = QFrame()
        self.activity_container.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 12px;
                border: none;
            }}
        """)

        # Add shadow to activity container
        activity_shadow = QGraphicsDropShadowEffect()
        activity_shadow.setBlurRadius(20)
        activity_shadow.setColor(QColor(0, 0, 0, 25))
        activity_shadow.setOffset(0, 4)
        self.activity_container.setGraphicsEffect(activity_shadow)

        self.activity_layout = QVBoxLayout(self.activity_container)
        self.activity_layout.setContentsMargins(24, 20, 24, 20)
        self.activity_layout.setSpacing(12)
        layout.addWidget(self.activity_container)

        layout.addStretch()

        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def refresh(self, data=None):
        """Refresh dashboard data."""
        logger.debug("Refreshing dashboard")

        try:
            # Get overview stats
            stats = self.dashboard_service.get_overview_stats()

            # Update stat cards
            self._stat_cards["buildings"].set_value(format_number(stats.get("total_buildings", 0)))
            self._stat_cards["units"].set_value(format_number(stats.get("total_units", 0)))
            self._stat_cards["claims"].set_value(format_number(stats.get("total_claims", 0)))
            self._stat_cards["persons"].set_value(format_number(stats.get("total_persons", 0)))
            self._stat_cards["pending"].set_value(format_number(stats.get("pending_claims", 0)))
            self._stat_cards["conflicts"].set_value(format_number(stats.get("claims_with_conflicts", 0)))

            # Update charts
            status_data = self.dashboard_service.get_chart_data("buildings_by_status")
            self._update_chart(self.buildings_by_status_chart, status_data)

            type_data = self.dashboard_service.get_chart_data("buildings_by_type")
            self._update_chart(self.buildings_by_type_chart, type_data)

            # Update recent activity
            self._update_activity()

        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}")

    def _update_chart(self, chart: ChartPlaceholder, data: dict):
        """Update a chart with new data."""
        chart.data = data

    def _update_activity(self):
        """Update recent activity list."""
        # Clear existing
        while self.activity_layout.count():
            child = self.activity_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        activities = self.dashboard_service.get_recent_activity(5)

        if not activities:
            no_data = QLabel(self.i18n.t("no_data"))
            no_data.setStyleSheet(f"color: {Config.TEXT_LIGHT}; padding: 20px;")
            no_data.setAlignment(Qt.AlignCenter)
            self.activity_layout.addWidget(no_data)
        else:
            for idx, activity in enumerate(activities):
                is_arabic = self.i18n.is_arabic()
                desc = activity.get("description_ar" if is_arabic else "description", "")
                timestamp = activity.get("timestamp", "")[:16]

                row_widget = QFrame()
                if idx < len(activities) - 1:
                    row_widget.setStyleSheet(f"border-bottom: 1px solid #F1F5F9; padding: 8px 0;")
                else:
                    row_widget.setStyleSheet("padding: 8px 0;")

                row = QHBoxLayout(row_widget)
                row.setContentsMargins(0, 8, 0, 8)

                # Activity indicator dot
                dot = QLabel()
                dot.setFixedSize(8, 8)
                dot_color = Config.PRIMARY_COLOR if activity.get("type") == "claim" else Config.SUCCESS_COLOR
                dot.setStyleSheet(f"background-color: {dot_color}; border-radius: 4px;")
                row.addWidget(dot)

                # Description
                desc_label = QLabel(desc)
                desc_label.setStyleSheet(f"color: {Config.TEXT_COLOR}; font-size: {Config.FONT_SIZE}pt;")
                row.addWidget(desc_label)
                row.addStretch()

                # Timestamp
                time_label = QLabel(timestamp)
                time_label.setStyleSheet(f"color: {Config.TEXT_LIGHT}; font-size: {Config.FONT_SIZE_SMALL}pt;")
                row.addWidget(time_label)

                self.activity_layout.addWidget(row_widget)

    def update_language(self, is_arabic: bool):
        """Update labels for language change."""
        self._stat_cards["buildings"].set_title(self.i18n.t("total_buildings"))
        self._stat_cards["units"].set_title(self.i18n.t("total_units"))
        self._stat_cards["claims"].set_title(self.i18n.t("total_claims"))
        self._stat_cards["persons"].set_title(self.i18n.t("total_persons"))
        self._stat_cards["pending"].set_title(self.i18n.t("pending_review"))
        self._stat_cards["conflicts"].set_title(self.i18n.t("with_conflicts"))
