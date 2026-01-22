# -*- coding: utf-8 -*-
"""Template for Leaflet drawing JavaScript - يتم استيراده من leaflet_html_generator.py"""

DRAWING_JS_TEMPLATE = """
        // Drawing layer for new shapes
        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        // Drawing controls
        console.log('Checking for Leaflet.draw library...');
        console.log('L.Control.Draw:', typeof L.Control.Draw);
        console.log('L.Draw:', typeof L.Draw);
        console.log('Drawing mode: __DRAWING_MODE__');

        if (typeof L.Control.Draw !== 'undefined') {
            console.log('✅ Leaflet.draw library loaded successfully');

            // تحديد الأدوات المفعلة بناءً على الوضع
            var enableMarker = __ENABLE_MARKER__;
            var enablePolygon = __ENABLE_POLYGON__;

            var drawControl = new L.Control.Draw({
                position: 'topright',
                draw: {
                    polyline: false,
                    rectangle: false,
                    circle: false,
                    circlemarker: false,
                    marker: enableMarker ? {
                        icon: L.icon({
                            iconUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjUiIGhlaWdodD0iNDEiIHZpZXdCb3g9IjAgMCAyNSA0MSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTIuNSAwQzUuNiAwIDAgNS42IDAgMTIuNWMwIDEuOC40IDMuNSAxLjIgNS4xTDEyLjUgNDEgMjMuOCAxNy42Yy44LTEuNiAxLjItMy4zIDEuMi01LjFDMjUgNS42IDE5LjQgMCAxMi41IDB6IiBmaWxsPSIjMDA3MkJDIi8+PGNpcmNsZSBjeD0iMTIuNSIgY3k9IjEyLjUiIHI9IjUiIGZpbGw9IndoaXRlIi8+PC9zdmc+',
                            iconSize: [25, 41],
                            iconAnchor: [12, 41]
                        })
                    } : false,
                    polygon: enablePolygon ? {
                        allowIntersection: false,
                        showArea: true,
                        shapeOptions: {
                            color: '#0072BC',
                            weight: 3,
                            fillOpacity: 0.4
                        }
                    } : false
                },
                edit: {
                    featureGroup: drawnItems,
                    remove: true
                }
            });
            map.addControl(drawControl);

            // Handle drawing created
            map.on(L.Draw.Event.CREATED, function(e) {
                var type = e.layerType;
                var layer = e.layer;

                drawnItems.addLayer(layer);

                // Get geometry
                var geometry = null;
                if (type === 'marker') {
                    var latlng = layer.getLatLng();
                    geometry = {
                        type: 'Point',
                        coordinates: [latlng.lng, latlng.lat]
                    };
                } else if (type === 'polygon') {
                    var latlngs = layer.getLatLngs()[0];
                    var coordinates = latlngs.map(function(ll) {
                        return [ll.lng, ll.lat];
                    });
                    // Close the polygon
                    coordinates.push(coordinates[0]);
                    geometry = {
                        type: 'Polygon',
                        coordinates: [coordinates]
                    };
                }

                console.log('Shape created:', type, geometry);

                // Send to Python via QWebChannel
                if (bridge && bridge.shapeDrawn) {
                    bridge.shapeDrawn(JSON.stringify(geometry));
                } else if (bridge && bridge.geometryDrawn) {
                    bridge.geometryDrawn(JSON.stringify(geometry));
                } else {
                    console.warn('Bridge method for drawing not found');
                }
            });

            // Handle editing
            map.on(L.Draw.Event.EDITED, function(e) {
                var layers = e.layers;
                console.log('Shapes edited:', layers.getLayers().length);
            });

            // Handle deletion
            map.on(L.Draw.Event.DELETED, function(e) {
                var layers = e.layers;
                console.log('Shapes deleted:', layers.getLayers().length);
            });
        } else {
            console.warn('⚠️ Leaflet.draw library not loaded. Using fallback: click to add marker');

            // Fallback: Simple click-to-add marker mode
            var currentMarker = null;

            map.on('click', function(e) {
                // Remove previous marker
                if (currentMarker) {
                    map.removeLayer(currentMarker);
                }

                // Add new marker
                currentMarker = L.marker(e.latlng, {
                    icon: L.icon({
                        iconUrl: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjUiIGhlaWdodD0iNDEiIHZpZXdCb3g9IjAgMCAyNSA0MSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTIuNSAwQzUuNiAwIDAgNS42IDAgMTIuNWMwIDEuOC40IDMuNSAxLjIgNS4xTDEyLjUgNDEgMjMuOCAxNy42Yy44LTEuNiAxLjItMy4zIDEuMi01LjFDMjUgNS42IDE5LjQgMCAxMi41IDB6IiBmaWxsPSIjRkYwMDAwIi8+PGNpcmNsZSBjeD0iMTIuNSIgY3k9IjEyLjUiIHI9IjUiIGZpbGw9IndoaXRlIi8+PC9zdmc+',
                        iconSize: [25, 41],
                        iconAnchor: [12, 41]
                    }),
                    draggable: false
                }).addTo(map);

                drawnItems.addLayer(currentMarker);

                // Create geometry
                var geometry = {
                    type: 'Point',
                    coordinates: [e.latlng.lng, e.latlng.lat]
                };

                console.log('Point created (fallback mode):', geometry);

                // Send to Python via QWebChannel
                if (bridge && bridge.shapeDrawn) {
                    bridge.shapeDrawn(JSON.stringify(geometry));
                } else if (bridge && bridge.geometryDrawn) {
                    bridge.geometryDrawn(JSON.stringify(geometry));
                } else {
                    console.warn('Bridge method for drawing not found');
                }
            });

            // Add instructions
            var instructions = L.control({position: 'topright'});
            instructions.onAdd = function(map) {
                var div = L.DomUtil.create('div', 'drawing-instructions');
                div.innerHTML = '<div style="background: white; padding: 10px; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.2); font-size: 12px; direction: rtl;">📍 اضغط على الخريطة لإضافة نقطة</div>';
                return div;
            };
            instructions.addTo(map);
        }
"""
