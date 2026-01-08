# -*- coding: utf-8 -*-
"""
Map Viewer Dialog - Display building location on map.

Simple dialog to view a location on an interactive map.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt5.QtCore import Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView

from app.config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class MapViewerDialog(QDialog):
    """Dialog for viewing a location on a map."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        title: str = "عرض الموقع",
        zoom: int = 17,
        parent=None
    ):
        super().__init__(parent)
        self.latitude = latitude
        self.longitude = longitude
        self.zoom = zoom

        self.setWindowTitle(title)
        self.setMinimumSize(700, 500)
        self.resize(800, 600)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Coordinates display
        coords_label = QLabel(f"الإحداثيات: {self.latitude:.6f}, {self.longitude:.6f}")
        coords_label.setStyleSheet(f"""
            color: {Config.TEXT_LIGHT};
            font-size: 10pt;
            padding: 8px;
            background-color: #F8FAFC;
            border-radius: 4px;
        """)
        layout.addWidget(coords_label)

        # Web view for map
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(400)
        layout.addWidget(self.web_view)

        # Load map
        self._load_map()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # Open in browser button
        browser_btn = QPushButton("فتح في المتصفح")
        browser_btn.clicked.connect(self._open_in_browser)
        btn_layout.addWidget(browser_btn)

        # Close button
        close_btn = QPushButton("إغلاق")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Config.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: 600;
            }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_map(self):
        """Load the map with marker."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
    </style>
</head>
<body>
    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([{self.latitude}, {self.longitude}], {self.zoom});

        // Add OpenStreetMap tiles
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);

        // Add satellite layer
        var satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: 'Tiles &copy; Esri'
        }});

        // Layer control
        var baseLayers = {{
            "خريطة": L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png'),
            "صور جوية": satellite
        }};
        L.control.layers(baseLayers).addTo(map);

        // Add marker
        var marker = L.marker([{self.latitude}, {self.longitude}]).addTo(map);
        marker.bindPopup('<b>موقع المبنى</b><br>العرض: {self.latitude:.6f}<br>الطول: {self.longitude:.6f}').openPopup();

        // Add circle to highlight area
        L.circle([{self.latitude}, {self.longitude}], {{
            color: '#2563EB',
            fillColor: '#3B82F6',
            fillOpacity: 0.2,
            radius: 50
        }}).addTo(map);
    </script>
</body>
</html>
"""
        self.web_view.setHtml(html)

    def _open_in_browser(self):
        """Open location in default browser."""
        import webbrowser
        url = f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        webbrowser.open(url)
