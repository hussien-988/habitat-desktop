# -*- coding: utf-8 -*-
"""
Template for Leaflet Multi-Select JavaScript.

Allows selecting multiple buildings by clicking on them directly.
Reuses the QWebChannel bridge from _get_selection_js().
"""

MULTISELECT_JS_TEMPLATE = """
        // =========================================================
        // Multi-Select Mode
        // =========================================================

        // Flag for viewport template to skip popups
        window.multiselectMode = true;

        // Store selected buildings
        var selectedBuildings = new Map();
        var selectedLayersGroup = L.featureGroup().addTo(map);

        // Visual styles for selected buildings (light transparent blue)
        var SELECTED_STYLE = {
            color: '#1976D2',
            weight: 4,
            fillColor: '#64B5F6',
            fillOpacity: 0.45,
            className: 'selected-building'
        };

        // Function to create custom pin icon for selected buildings (larger, blue)
        function createSelectedPinIcon() {
            return L.divIcon({
                className: 'building-pin-icon selected-pin',
                html: '<div style="position: relative; width: 36px; height: 52px;">' +
                      '<svg width="36" height="52" viewBox="0 0 32 48" xmlns="http://www.w3.org/2000/svg">' +
                      '<path d="M16 0C9.4 0 4 5.4 4 12c0 10 12 32 12 32s12-22 12-32c0-6.6-5.4-12-12-12z" ' +
                      'fill="#1976D2" stroke="#64B5F6" stroke-width="3"/>' +
                      '<circle cx="16" cy="12" r="6" fill="#64B5F6"/>' +
                      '<text x="16" y="16" text-anchor="middle" fill="white" font-size="11" font-weight="bold">&#10003;</text>' +
                      '</svg></div>',
                iconSize: [36, 52],
                iconAnchor: [18, 52],
                popupAnchor: [0, -52]
            });
        }

        // Toggle building selection
        function toggleBuildingMultiSelect(buildingId, layer, feature) {
            if (selectedBuildings.has(buildingId)) {
                deselectBuildingMulti(buildingId);
            } else {
                selectBuildingMulti(buildingId, layer, feature);
            }

            updateMultiSelectCounter();
            sendMultiSelectedBuildingsToPython();
        }

        // Select a building
        function selectBuildingMulti(buildingId, layer, feature) {
            if (selectedBuildings.has(buildingId)) return;

            selectedBuildings.set(buildingId, {layer: layer, feature: feature});

            // Create highlight layer
            var highlightLayer;
            var geomType = feature.geometry.type;

            if (geomType === 'Point') {
                var latlng = layer.getLatLng();
                highlightLayer = L.marker(latlng, {
                    icon: createSelectedPinIcon(),
                    interactive: false
                });
            } else if (geomType === 'Polygon' || geomType === 'MultiPolygon') {
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
        function deselectBuildingMulti(buildingId) {
            if (!selectedBuildings.has(buildingId)) return;

            var selection = selectedBuildings.get(buildingId);
            if (selection.highlightLayer) {
                selectedLayersGroup.removeLayer(selection.highlightLayer);
            }
            selectedBuildings.delete(buildingId);
        }

        // Clear all selections
        function clearAllSelections() {
            selectedLayersGroup.clearLayers();
            selectedBuildings.clear();
            updateMultiSelectCounter();
            sendMultiSelectedBuildingsToPython();
        }

        window.clearAllSelections = clearAllSelections;

        // Helper: execute callback when bridge is ready (reuses bridge from _get_selection_js)
        function withBridge(callback) {
            if (typeof bridgeReady !== 'undefined' && bridgeReady && typeof bridge !== 'undefined' && bridge) {
                callback(bridge);
            } else {
                var retryCount = 0;
                var retryInterval = setInterval(function() {
                    retryCount++;
                    if (typeof bridgeReady !== 'undefined' && bridgeReady && typeof bridge !== 'undefined' && bridge) {
                        clearInterval(retryInterval);
                        callback(bridge);
                    } else if (retryCount > 100) {
                        clearInterval(retryInterval);
                        console.error('Bridge not ready for multiselect after 5s');
                    }
                }, 50);
            }
        }

        // Update selection counter via bridge
        function updateMultiSelectCounter() {
            var count = selectedBuildings.size;
            withBridge(function(b) {
                if (b.updateSelectionCount) b.updateSelectionCount(count);
            });
        }

        // Send selected buildings list to Python via bridge
        function sendMultiSelectedBuildingsToPython() {
            var buildingIds = Array.from(selectedBuildings.keys());
            withBridge(function(b) {
                if (b.onBuildingsSelected) b.onBuildingsSelected(JSON.stringify(buildingIds));
            });
        }

        // Attach multi-select click handler to a building layer
        // Exported to window so viewport template can call it for dynamic buildings
        function attachMultiselectHandler(layer) {
            if (!layer.feature || !layer.feature.properties) return;

            var buildingId = layer.feature.properties.building_id;
            if (!buildingId) return;

            // Unbind any popup to prevent it from showing
            layer.unbindPopup();

            // Add click handler for toggle selection
            layer.on('click', function(e) {
                L.DomEvent.stopPropagation(e);
                toggleBuildingMultiSelect(buildingId, layer, layer.feature);
                return false;
            });

            // Hover effects
            layer.on('mouseover', function(e) {
                var geomType = layer.feature.geometry.type;
                if (geomType !== 'Point') {
                    this.setStyle({
                        fillOpacity: 0.8,
                        weight: 3,
                        color: selectedBuildings.has(buildingId) ? '#2196F3' : '#00BFFF'
                    });
                }
                map.getContainer().style.cursor = 'pointer';
            });

            layer.on('mouseout', function(e) {
                if (!selectedBuildings.has(buildingId)) {
                    // Reset to original style
                    var parentLayer = typeof currentBuildingsLayer !== 'undefined' ? currentBuildingsLayer : buildingsLayer;
                    if (parentLayer && typeof parentLayer.resetStyle === 'function') {
                        parentLayer.resetStyle(this);
                    }
                }
                map.getContainer().style.cursor = '';
            });
        }

        window.attachMultiselectHandler = attachMultiselectHandler;

        // Attach handlers to initial buildings layer
        if (typeof buildingsLayer !== 'undefined' && buildingsLayer) {
            buildingsLayer.eachLayer(function(layer) {
                attachMultiselectHandler(layer);
            });
            console.log('Multi-select handlers attached to initial buildings');
        }

        // Also attach to clustered markers (point markers added via markers cluster group)
        if (typeof markers !== 'undefined' && markers) {
            markers.eachLayer(function(layer) {
                attachMultiselectHandler(layer);
            });
            console.log('Multi-select handlers attached to clustered markers');
        }

        console.log('Multi-Select Mode initialized');
"""
