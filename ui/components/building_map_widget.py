# -*- coding: utf-8 -*-
"""
Building Map Widget - Shared Component for Map Services.

Reusable component that provides interactive building selection map.
Follows DRY and SOLID principles - single source of truth for map functionality.

Usage:
    widget = BuildingMapWidget(db)
    widget.building_selected.connect(on_building_selected)
    widget.show_dialog()
"""

from typing import Optional, Callable
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QUrl

from repositories.database import Database
from repositories.building_repository import BuildingRepository
from models.building import Building
from utils.logger import get_logger

logger = get_logger(__name__)

# Check for WebEngine availability
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None

# Check for WebChannel availability
try:
    from PyQt5.QtWebChannel import QWebChannel
    HAS_WEBCHANNEL = True
except ImportError:
    HAS_WEBCHANNEL = False


class BuildingMapWidget(QObject):
    """
    Shared component for building selection via interactive map.

    Provides:
    - Interactive Leaflet map with building markers
    - Color-coded building status
    - Building selection via popup
    - Reusable across different parts of the application

    Signals:
        building_selected: Emitted when user selects a building (Building object)
    """

    building_selected = pyqtSignal(object)  # Emits Building object

    def __init__(self, db: Database, parent=None):
        """
        Initialize the map widget.

        Args:
            db: Database instance
            parent: Parent QObject
        """
        super().__init__(parent)
        self.db = db
        self.building_repo = BuildingRepository(db)
        self._dialog = None
        self._map_view = None

    def show_dialog(self) -> Optional[Building]:
        """
        Show the map selection dialog.

        Returns:
            Selected Building object, or None if cancelled
        """
        if not HAS_WEBENGINE:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                None,
                "غير متوفر",
                "البحث على الخريطة غير متوفر (يتطلب PyQtWebEngine)"
            )
            return None

        # Create dialog if not exists (reuse for performance)
        if self._dialog is None:
            self._dialog = self._create_dialog()

        # Load/reload map
        self._load_map()

        # Show dialog (modal)
        result = self._dialog.exec_()

        # Return selected building if accepted
        if result == QDialog.Accepted and hasattr(self, '_selected_building'):
            return self._selected_building
        return None

    def _create_dialog(self) -> QDialog:
        """Create the map dialog UI."""
        dialog = QDialog()
        dialog.setModal(True)
        dialog.setWindowTitle("بحث على الخريطة - اختر مبنى من الخريطة")
        dialog.resize(900, 600)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Title
        title = QLabel("🗺️ اضغط على علامة مبنى لاختياره")
        title.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2C3E50;
                padding: 8px;
                background-color: #E8F4F8;
                border-radius: 6px;
            }
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Map view
        if HAS_WEBENGINE:
            self._map_view = QWebEngineView(dialog)

            # Enable hardware acceleration
            settings = self._map_view.settings()
            settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)

            # Setup WebChannel for JS-Python communication
            if HAS_WEBCHANNEL:
                self._setup_webchannel()

            layout.addWidget(self._map_view, stretch=1)
        else:
            placeholder = QLabel("🗺️ الخريطة غير متاحة (QtWebEngine غير مثبت)")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("padding: 40px; color: #999;")
            layout.addWidget(placeholder)

        # Close button
        close_btn = QPushButton("إغلاق")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(dialog.reject)
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #E74C3C;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #C0392B; }
        """)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        return dialog

    def _setup_webchannel(self):
        """Setup WebChannel for JavaScript-Python communication."""
        class MapBridge(QObject):
            """Bridge for map selection events."""

            def __init__(self, parent_widget):
                super().__init__()
                self.parent_widget = parent_widget

            @pyqtSlot(str)
            def selectBuilding(self, building_id: str):
                """Called from JavaScript when user selects a building."""
                self.parent_widget._on_building_selected_from_map(building_id)

        self._bridge = MapBridge(self)
        self._channel = QWebChannel(self._map_view.page())
        self._channel.registerObject('buildingBridge', self._bridge)
        self._map_view.page().setWebChannel(self._channel)

    def _load_map(self):
        """Load the interactive map with building markers."""
        if not self._map_view:
            return

        from services.tile_server_manager import get_tile_server_url

        tile_server_url = get_tile_server_url()
        if not tile_server_url.endswith('/'):
            tile_server_url += '/'

        # Get buildings with coordinates
        buildings = self.building_repo.get_all(limit=200)
        markers_js = self._generate_markers_js(buildings)

        # Generate HTML
        html = self._generate_map_html(tile_server_url, markers_js)

        # Load HTML
        base_url = QUrl(tile_server_url)
        self._map_view.setHtml(html, base_url)

    def _generate_markers_js(self, buildings) -> str:
        """Generate JavaScript code for building markers."""
        markers_js = ""

        for b in buildings:
            if not (hasattr(b, 'latitude') and b.latitude and hasattr(b, 'longitude') and b.longitude):
                continue

            building_type = getattr(b, 'building_type_display', getattr(b, 'building_type', 'مبنى'))
            building_status = getattr(b, 'building_status', 'unknown')
            status_display = getattr(b, 'building_status_display', building_status)
            marker_color = self._get_marker_color(building_status)

            safe_id = b.building_id.replace('-', '_')

            markers_js += f"""
                var icon_{safe_id} = L.divIcon({{
                    className: 'custom-pin-marker',
                    html: '<div class="pin-marker" style="background-color: {marker_color};"><div class="pin-point"></div></div>',
                    iconSize: [20, 26],
                    iconAnchor: [10, 26],
                    popupAnchor: [0, -28]
                }});

                var popupContent_{safe_id} = `
                    <div style="text-align: center; min-width: 180px;">
                        <div style="font-size: 16px; font-weight: bold; color: #2C3E50; margin-bottom: 8px;">
                            {b.building_id}
                        </div>
                        <div style="font-size: 13px; color: #555; margin-bottom: 4px;">
                            النوع: {building_type}
                        </div>
                        <div style="font-size: 13px; color: {marker_color}; font-weight: bold; margin-bottom: 12px;">
                            الحالة: {status_display}
                        </div>
                        <button onclick="selectBuilding('{b.building_id}')"
                            style="width: 100%; padding: 8px 16px; background-color: #0072BC; color: white;
                                   border: none; border-radius: 6px; cursor: pointer; font-weight: bold;
                                   font-size: 14px;">
                            ✓ اختيار هذا المبنى
                        </button>
                    </div>
                `;

                L.marker([{b.latitude}, {b.longitude}], {{ icon: icon_{safe_id} }})
                    .addTo(map)
                    .bindPopup(popupContent_{safe_id}, {{
                        closeButton: true,
                        maxWidth: 250,
                        className: 'custom-popup'
                    }});
            """

        return markers_js

    def _get_marker_color(self, status: str) -> str:
        """Get marker color based on building status."""
        colors = {
            'intact': '#28A745',
            'standing': '#28A745',
            'damaged': '#FFC107',
            'partially_damaged': '#FF9800',
            'severely_damaged': '#FF5722',
            'destroyed': '#DC3545',
            'demolished': '#DC3545',
            'rubble': '#8B0000'
        }
        return colors.get(status, '#0072BC')

    def _generate_map_html(self, tile_server_url: str, markers_js: str) -> str:
        """Generate the complete map HTML."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="{tile_server_url}/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}

        .custom-pin-marker {{ cursor: pointer; }}
        .pin-marker {{
            width: 20px;
            height: 20px;
            border-radius: 50% 50% 50% 0;
            transform: rotate(-45deg);
            border: 2px solid white;
            box-shadow: 0 2px 6px rgba(0,0,0,0.4);
            position: relative;
            transition: transform 0.2s ease;
        }}
        .pin-marker:hover {{
            transform: rotate(-45deg) scale(1.2);
            box-shadow: 0 3px 10px rgba(0,0,0,0.6);
        }}
        .pin-point {{
            width: 6px;
            height: 6px;
            background: white;
            border-radius: 50%;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }}

        .custom-popup .leaflet-popup-content-wrapper {{
            border-radius: 10px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
            padding: 4px;
        }}
        .custom-popup .leaflet-popup-content {{
            margin: 12px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        .custom-popup button:hover {{
            background-color: #005A94 !important;
            transform: scale(1.02);
            transition: all 0.2s ease;
        }}

        .legend {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: white;
            padding: 12px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            font-size: 12px;
            z-index: 1000;
        }}
        .legend-title {{
            font-weight: bold;
            margin-bottom: 8px;
            color: #2C3E50;
            border-bottom: 1px solid #E1E8ED;
            padding-bottom: 4px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 4px 0;
        }}
        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 50%;
            margin-left: 8px;
            border: 1px solid #DDD;
        }}
    </style>
</head>
<body>
    <div id="map"></div>

    <div class="legend">
        <div class="legend-title">حالة المبنى</div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #28A745;"></span>
            <span>سليم</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #FFC107;"></span>
            <span>متضرر</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #FF9800;"></span>
            <span>متضرر جزئياً</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #FF5722;"></span>
            <span>متضرر بشدة</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #DC3545;"></span>
            <span>مهدم</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background-color: #8B0000;"></span>
            <span>ركام</span>
        </div>
    </div>

    <script src="{tile_server_url}/leaflet.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        var buildingBridge = null;

        new QWebChannel(qt.webChannelTransport, function(channel) {{
            buildingBridge = channel.objects.buildingBridge;
            console.log('QWebChannel initialized');
        }});

        var map = L.map('map', {{
            preferCanvas: true,
            zoomAnimation: true,
            fadeAnimation: false
        }}).setView([36.2, 37.15], 13);

        L.tileLayer('{tile_server_url}/tiles/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 16,
            minZoom: 10,
            maxNativeZoom: 16,
            attribution: 'UN-Habitat Syria',
            updateWhenIdle: false,
            updateWhenZooming: false,
            keepBuffer: 4,
            errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        }}).addTo(map);

        {markers_js}

        function selectBuilding(buildingId) {{
            console.log('Selected building: ' + buildingId);

            var button = event.target;
            button.disabled = true;
            button.innerHTML = '⏳ جاري الاختيار...';
            button.style.backgroundColor = '#6C757D';

            if (buildingBridge) {{
                buildingBridge.selectBuilding(buildingId);
                setTimeout(function() {{
                    map.closePopup();
                }}, 500);
            }} else {{
                console.error('buildingBridge not initialized');
                button.innerHTML = '❌ خطأ في الاتصال';
                button.style.backgroundColor = '#DC3545';
            }}
        }}
    </script>
</body>
</html>
"""

    def _on_building_selected_from_map(self, building_id: str):
        """Handle building selection from map."""
        logger.info(f"Building selected from map: {building_id}")

        # Find building in database
        building = self.building_repo.get_by_id(building_id)

        if building:
            self._selected_building = building
            self.building_selected.emit(building)

            # Close dialog
            if self._dialog:
                self._dialog.accept()
        else:
            logger.error(f"Building not found: {building_id}")
