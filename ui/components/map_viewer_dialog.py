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
from ui.constants.map_constants import MapConstants
from utils.logger import get_logger

logger = get_logger(__name__)


class MapViewerDialog(QDialog):
    """Dialog for viewing a location on a map."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        title: str = "عرض الموقع",
        zoom: int = 20,
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
        """Load the map with marker using OFFLINE tiles."""
        from services.tile_server_manager import get_tile_server_url

        tile_server_url = get_tile_server_url()

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
        .leaflet-container {{ background: {MapConstants.TILE_PANE_BACKGROUND} !important; }}
        .leaflet-tile-pane {{ background: {MapConstants.TILE_PANE_BACKGROUND}; }}
        .leaflet-tile {{ transition: opacity 0.3s ease-in !important; }}
        #map-loading-overlay {{
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: {MapConstants.TILE_PANE_BACKGROUND}; z-index: 9999;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            transition: opacity 0.6s ease-out;
        }}
        #map-loading-overlay.fade-out {{ opacity: 0; pointer-events: none; }}
        .loading-spinner {{
            width: 40px; height: 40px;
            border: 3px solid rgba(255,255,255,0.15); border-top: 3px solid #0072BC;
            border-radius: 50%; animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="map-loading-overlay"><div class="loading-spinner"></div></div>

    <script src="{tile_server_url}/leaflet.js"></script>
    <script>
        var map = L.map('map', {{
            preferCanvas: true,
            fadeAnimation: {'true' if MapConstants.MAP_FADE_ANIMATION else 'false'},
            zoomAnimation: {'true' if MapConstants.MAP_ZOOM_ANIMATION else 'false'},
            zoomAnimationThreshold: {MapConstants.MAP_ZOOM_ANIMATION_THRESHOLD}
        }}).setView([{self.latitude}, {self.longitude}], {self.zoom});

        // Use LOCAL tiles from MBTiles
        var tileLayer = L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 20,
            minZoom: 15,
            attribution: 'UN-Habitat Syria - يعمل بدون اتصال بالإنترنت',
            keepBuffer: {MapConstants.TILE_KEEP_BUFFER},
            updateWhenZooming: {'true' if MapConstants.TILE_UPDATE_WHEN_ZOOMING else 'false'},
            updateWhenIdle: {'true' if MapConstants.TILE_UPDATE_WHEN_IDLE else 'false'},
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        }}).addTo(map);

        // Loading overlay removal
        (function() {{
            var ov = document.getElementById('map-loading-overlay');
            if (!ov) return;
            var done = false;
            function hide() {{
                if (done) return; done = true;
                ov.classList.add('fade-out');
                setTimeout(function() {{ ov.style.display = 'none'; }}, 600);
            }}
            tileLayer.on('load', hide);
            setTimeout(hide, 3000);
        }})();

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
