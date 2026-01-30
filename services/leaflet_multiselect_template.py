# -*- coding: utf-8 -*-
"""
Template for Leaflet Multi-Select JavaScript.

Allows selecting multiple buildings by clicking on them directly.
Works alongside polygon selection mode.
"""

MULTISELECT_JS_TEMPLATE = """
        // Multi-Select Mode JavaScript
        // Allows clicking on buildings to select/deselect them

        // QWebChannel setup for multi-select
        var multiselectBridge = null;

        if (typeof QWebChannel !== 'undefined') {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                multiselectBridge = channel.objects.buildingBridge || channel.objects.bridge;
                console.log('✅ QWebChannel initialized for multi-select');
            });
        }

        // Store selected buildings
        var selectedBuildings = new Map();  // building_id -> {layer, feature}
        var selectedLayersGroup = L.featureGroup().addTo(map);

        // Visual styles for selected buildings
        var SELECTED_STYLE = {
            color: '#FF6B00',        // Orange border
            weight: 4,
            fillColor: '#FF6B00',
            fillOpacity: 0.5,
            className: 'selected-building'
        };

        var SELECTED_POINT_STYLE = {
            radius: 12,
            color: '#FF6B00',
            weight: 3,
            fillColor: '#FFD700',
            fillOpacity: 0.8
        };

        // Function to create custom pin icon for selected buildings
        function createSelectedPinIcon() {
            return L.divIcon({
                className: 'building-pin-icon selected-pin',
                html: '<div style="position: relative; width: 32px; height: 48px;">' +
                      '<svg width="32" height="48" viewBox="0 0 32 48" xmlns="http://www.w3.org/2000/svg">' +
                      '<path d="M16 0C9.4 0 4 5.4 4 12c0 10 12 32 12 32s12-22 12-32c0-6.6-5.4-12-12-12z" ' +
                      'fill="#FF6B00" stroke="#FFD700" stroke-width="3"/>' +
                      '<circle cx="16" cy="12" r="5" fill="#FFD700"/>' +
                      '<text x="16" y="16" text-anchor="middle" fill="white" font-size="12" font-weight="bold">✓</text>' +
                      '</svg></div>',
                iconSize: [32, 48],
                iconAnchor: [16, 48],
                popupAnchor: [0, -48]
            });
        }

        // Toggle building selection
        function toggleBuildingSelection(buildingId, layer, feature) {
            if (selectedBuildings.has(buildingId)) {
                // Deselect
                deselectBuilding(buildingId);
                console.log('🔽 Deselected building:', buildingId);
            } else {
                // Select
                selectBuilding(buildingId, layer, feature);
                console.log('🔼 Selected building:', buildingId);
            }

            // Update counter
            updateSelectionCounter();

            // Send updated list to Python
            sendSelectedBuildingsToPython();
        }

        // Select a building
        function selectBuilding(buildingId, layer, feature) {
            if (selectedBuildings.has(buildingId)) return;

            // Store selection
            selectedBuildings.set(buildingId, {layer: layer, feature: feature});

            // Create highlight layer
            var highlightLayer;
            var geomType = feature.geometry.type;

            if (geomType === 'Point') {
                // For points: create a highlighted marker
                var latlng = layer.getLatLng();
                highlightLayer = L.marker(latlng, {
                    icon: createSelectedPinIcon(),
                    interactive: false  // Don't interfere with original layer clicks
                });
            } else if (geomType === 'Polygon' || geomType === 'MultiPolygon') {
                // For polygons: create highlighted polygon overlay
                highlightLayer = L.geoJSON(feature, {
                    style: SELECTED_STYLE,
                    interactive: false
                });
            }

            if (highlightLayer) {
                selectedLayersGroup.addLayer(highlightLayer);
                selectedBuildings.get(buildingId).highlightLayer = highlightLayer;
            }
        }

        // Deselect a building
        function deselectBuilding(buildingId) {
            if (!selectedBuildings.has(buildingId)) return;

            var selection = selectedBuildings.get(buildingId);

            // Remove highlight layer
            if (selection.highlightLayer) {
                selectedLayersGroup.removeLayer(selection.highlightLayer);
            }

            // Remove from selection map
            selectedBuildings.delete(buildingId);
        }

        // Clear all selections
        function clearAllSelections() {
            console.log('🗑️ Clearing all selections');
            selectedLayersGroup.clearLayers();
            selectedBuildings.clear();
            updateSelectionCounter();
            sendSelectedBuildingsToPython();
        }

        // Expose to window for Python calls
        window.clearAllSelections = clearAllSelections;

        // Update selection counter display
        function updateSelectionCounter() {
            var count = selectedBuildings.size;

            if (multiselectBridge && multiselectBridge.updateSelectionCount) {
                multiselectBridge.updateSelectionCount(count);
            }

            console.log('📊 Selection count:', count);
        }

        // Send selected buildings list to Python
        function sendSelectedBuildingsToPython() {
            var buildingIds = Array.from(selectedBuildings.keys());

            if (multiselectBridge && multiselectBridge.onBuildingsSelected) {
                multiselectBridge.onBuildingsSelected(JSON.stringify(buildingIds));
                console.log('📤 Sent selected buildings to Python:', buildingIds);
            }
        }

        // Enable multi-select mode on building layers
        // This modifies the existing buildings layer to support multi-select
        if (typeof buildingsLayer !== 'undefined' && buildingsLayer) {
            buildingsLayer.eachLayer(function(layer) {
                if (!layer.feature || !layer.feature.properties) return;

                var buildingId = layer.feature.properties.building_id;
                if (!buildingId) return;

                // Add click handler for multi-select
                layer.on('click', function(e) {
                    // Prevent popup from opening when selecting
                    L.DomEvent.stopPropagation(e);

                    toggleBuildingSelection(buildingId, layer, layer.feature);

                    // Prevent default click behavior
                    return false;
                });

                // Update hover effect to show selectable
                layer.on('mouseover', function(e) {
                    var geomType = layer.feature.geometry.type;

                    if (geomType !== 'Point') {
                        this.setStyle({
                            fillOpacity: 0.8,
                            weight: 3,
                            color: selectedBuildings.has(buildingId) ? '#FF6B00' : '#00BFFF'
                        });
                    }

                    // Update cursor
                    map.getContainer().style.cursor = 'pointer';
                });

                layer.on('mouseout', function(e) {
                    if (!selectedBuildings.has(buildingId)) {
                        if (typeof buildingsLayer.resetStyle === 'function') {
                            buildingsLayer.resetStyle(this);
                        }
                    }

                    map.getContainer().style.cursor = '';
                });
            });

            console.log('✅ Multi-select mode enabled on buildings layer');
        }

        // Log multi-select setup
        console.log('═══════════════════════════════════════');
        console.log('📍 Multi-Select Mode Initialized');
        console.log('  - Click on buildings to select/deselect');
        console.log('  - Selected buildings will be highlighted in orange');
        console.log('  - Use "Clear All" button to deselect all');
        console.log('═══════════════════════════════════════');
"""
